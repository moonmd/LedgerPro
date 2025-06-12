from .models import (
    User, Organization, Role, Membership,
    Account, Transaction, JournalEntry, AuditLog,
    Customer, Invoice, InvoiceItem, Vendor,
    PlaidItem, StagedBankTransaction, ReconciliationRule,
    Employee, PayRun, Payslip, DeductionType # Added Payroll models
)
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserDetailSerializer, RoleSerializer,
    AccountSerializer, TransactionSerializer, AuditLogSerializer,
    CustomerSerializer, InvoiceSerializer, VendorSerializer,
    PlaidItemSerializer, StagedBankTransactionSerializer, ReconciliationRuleSerializer,
    EmployeeSerializer, PayRunSerializer, PayslipSerializer, DeductionTypeSerializer # Added Payroll serializers
)
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
import logging
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
import csv
import io
from . import plaid_service
from . import reconciliation_service
from . import reporting_service
from . import payroll_service
from . import email_utils # Ensured email_utils is imported
from datetime import date

logger = logging.getLogger(__name__)

# --- Existing User, Role, Mixin, Accounting, Customer, Invoice, Vendor, Plaid, StagedTx, Reconciliation, Reporting Views ---
class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh), 'access': str(refresh.access_token),
            'user': UserDetailSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(request, email=email, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh), 'access': str(refresh.access_token),
                'user': UserDetailSerializer(user).data
            })
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return self.request.user

class RoleListView(generics.ListCreateAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAdminUser]

class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAdminUser]

class OrganizationScopedViewMixin:
    def get_organization(self):
        if not hasattr(self.request.user, 'membership_set'):
             raise PermissionDenied('User has no membership information.')
        membership = self.request.user.membership_set.first()
        if not membership:
            raise PermissionDenied('User is not associated with any organization.')
        return membership.organization
    def get_queryset(self):
        queryset = super().get_queryset()
        organization = self.get_organization()
        if hasattr(self.queryset.model, 'organization'):
            return queryset.filter(organization=organization)
        elif hasattr(self.queryset.model, 'organization_id'):
             return queryset.filter(organization_id=organization.id)
        return queryset
    def perform_create(self, serializer):
        organization = self.get_organization()
        save_kwargs = {'organization': organization}
        if hasattr(serializer.Meta.model, 'created_by') and self.request.user.is_authenticated:
            if 'created_by' in [field.name for field in serializer.Meta.model._meta.fields]:
                 save_kwargs['created_by'] = self.request.user
        if isinstance(serializer, TransactionSerializer):
             serializer.save(organization=organization)
        else:
             serializer.save(**save_kwargs)
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class AccountViewSet(OrganizationScopedViewMixin, generics.ListCreateAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]
class AccountDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]
class TransactionViewSet(OrganizationScopedViewMixin, generics.ListCreateAPIView):
    queryset = Transaction.objects.all().order_by('-date', '-created_at')
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
class TransactionDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    def perform_update(self, serializer):
        serializer.save()
    def perform_destroy(self, instance):
        organization = self.get_organization()
        AuditLog.objects.create(organization=organization,user=self.request.user,action="deleted_transaction",details={'transaction_id': str(instance.id), 'description': instance.description})
        instance.delete()
class AuditLogListView(OrganizationScopedViewMixin, generics.ListAPIView):
    queryset = AuditLog.objects.all().order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
class CustomerViewSet(OrganizationScopedViewMixin, generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
class CustomerDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
class InvoiceViewSet(OrganizationScopedViewMixin, generics.ListCreateAPIView):
    queryset = Invoice.objects.all().select_related('customer').prefetch_related('items')
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return super().get_queryset().order_by('-issue_date')

class InvoiceDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateDestroyAPIView): # send_invoice_email action removed
    queryset = Invoice.objects.all().select_related('customer').prefetch_related('items')
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        AuditLog.objects.create(organization=instance.organization, user=self.request.user,action='deleted_invoice',details={'invoice_id': str(instance.id), 'invoice_number': instance.invoice_number})
        instance.delete()

# NEW VIEW FOR SENDING INVOICE EMAIL
class InvoiceSendEmailView(OrganizationScopedViewMixin, generics.GenericAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        invoice = self.get_object()
        if invoice.status == Invoice.PAID or invoice.status == Invoice.VOID:
            return Response({'error': f'Invoice in {invoice.status} status cannot be sent.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            email_sent_successfully = email_utils.send_invoice_email(invoice)
            if email_sent_successfully:
                if invoice.status == Invoice.DRAFT:
                    invoice.status = Invoice.SENT
                    invoice.save(update_fields=['status'])

                AuditLog.objects.create(
                    organization=invoice.organization,
                    user=request.user,
                    action='sent_invoice_email',
                    details={'invoice_id': str(invoice.id), 'invoice_number': invoice.invoice_number, 'customer_email': invoice.customer.email}
                )
                return Response({'message': 'Invoice sent successfully.'}, status=status.HTTP_200_OK)
            else:
                if not invoice.customer.email:
                    return Response({'error': f'Cannot send email: Customer {invoice.customer.name} has no email address.'}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'error': 'Failed to send invoice email. Possible configuration issue or SendGrid error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception(f'Error in InvoiceSendEmailView for invoice {invoice.id}: {e}')
            return Response({'error': 'An unexpected error occurred while sending the email.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VendorViewSet(OrganizationScopedViewMixin, generics.ListCreateAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
class VendorDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
class PlaidCreateLinkTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):
        user = request.user
        membership = user.membership_set.first()
        if not membership: return Response({'error': 'User not associated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)
        organization = membership.organization
        try:
            link_token = plaid_service.create_link_token(str(user.id), organization)
            if link_token:
                return Response({'link_token': link_token})
            else:
                return Response({'error': 'Failed to initialize Plaid link. Please check configuration or try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception(f'Unexpected critical error in PlaidCreateLinkTokenView for user {user.id}, org {organization.name}:')
            return Response({'error': 'An unexpected server error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class PlaidExchangePublicTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):
        public_token = request.data.get('public_token')
        institution_id = request.data.get('institution_id')
        institution_name = request.data.get('institution_name')
        if not public_token: return Response({'error': 'Public token not provided.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        membership = user.membership_set.first()
        if not membership: return Response({'error': 'User not associated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)
        organization = membership.organization
        plaid_item = plaid_service.exchange_public_token(public_token, user, organization, institution_id, institution_name)
        if plaid_item: return Response(PlaidItemSerializer(plaid_item).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Failed to exchange public token.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class PlaidFetchTransactionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):
        plaid_item_id = request.data.get('plaid_item_id')
        if not plaid_item_id: return Response({'error': 'Plaid Item ID not provided.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            organization = request.user.membership_set.first().organization
            plaid_item = PlaidItem.objects.get(id=plaid_item_id, organization=organization)
        except PlaidItem.DoesNotExist: return Response({'error': 'Plaid item not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError: return Response({'error': 'User organization context not found.'}, status=status.HTTP_400_BAD_REQUEST)
        count = plaid_service.fetch_plaid_transactions(plaid_item)
        if count >= 0: return Response({'message': f'{count} new transactions fetched successfully.'})
        return Response({'error': 'Failed to fetch transactions from Plaid.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class StagedBankTransactionListView(OrganizationScopedViewMixin, generics.ListAPIView):
    queryset = StagedBankTransaction.objects.all().order_by('-date')
    serializer_class = StagedBankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
class ManualBankStatementImportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    def post(self, request, *args, **kwargs):
        file_obj = request.data.get('file')
        if not file_obj: return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            decoded_file = file_obj.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            imported_count = 0; failed_rows = []
            membership = request.user.membership_set.first()
            if not membership: return Response({'error': 'User not associated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)
            organization = membership.organization
            for i, row in enumerate(reader):
                try:
                    tx_id_source = f"csv_import_{organization.id}_{row.get('Date')}_{row.get('Description', row.get('Name'))}_{row.get('Amount')}_{i}"
                    _, created = StagedBankTransaction.objects.update_or_create(
                        organization=organization, transaction_id_source=tx_id_source,
                        defaults={'date': row['Date'], 'name': row.get('Description', row.get('Name', 'N/A')),'amount': row['Amount'], 'currency_code': row.get('Currency', 'USD'), 'source': 'CSV', 'raw_data': dict(row) })
                    if created: imported_count += 1
                except Exception as e_row: failed_rows.append({'row': i+1, 'error': str(e_row), 'data': row})
            if failed_rows: return Response({'message': f'{imported_count} transactions imported. Some rows failed.','imported_count': imported_count, 'failed_rows': failed_rows}, status=status.HTTP_207_MULTI_STATUS)
            return Response({'message': f'{imported_count} transactions imported successfully.'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'Error processing manual bank statement import: {e}')
            return Response({'error': f'Failed to process file: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ReconciliationRuleViewSet(OrganizationScopedViewMixin, generics.ListCreateAPIView):
    queryset = ReconciliationRule.objects.all()
    serializer_class = ReconciliationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    def perform_create(self, serializer): serializer.save(organization=self.get_organization(), created_by=self.request.user)
class ReconciliationRuleDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ReconciliationRule.objects.all()
    serializer_class = ReconciliationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
class ApplyReconciliationRulesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, *args, **kwargs):
        membership = request.user.membership_set.first()
        if not membership: return Response({'error': 'User not associated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)
        organization = membership.organization
        applied_count = reconciliation_service.run_reconciliation_rules_for_organization(organization, request.user)
        return Response({'message': f'{applied_count} reconciliation rules applied successfully.'})
class StagedBankTransactionDetailView(OrganizationScopedViewMixin, generics.RetrieveUpdateAPIView):
    queryset = StagedBankTransaction.objects.all()
    serializer_class = StagedBankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

class StagedBankTransactionSuggestMatchesView(OrganizationScopedViewMixin, generics.GenericAPIView):
    queryset = StagedBankTransaction.objects.all()
    serializer_class = StagedBankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        staged_tx = self.get_object()
        suggestions = reconciliation_service.find_suggested_matches(staged_tx)
        return Response(suggestions)

class StagedBankTransactionMatchView(OrganizationScopedViewMixin, generics.GenericAPIView):
    queryset = StagedBankTransaction.objects.all()
    serializer_class = StagedBankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        staged_tx = self.get_object()
        ledger_pro_tx_id = request.data.get('ledger_pro_transaction_id')
        if staged_tx.reconciliation_status != StagedBankTransaction.RECON_UNMATCHED:
            return Response({'error': 'Transaction already reconciled or processed.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_tx = Transaction.objects.get(id=ledger_pro_tx_id, organization=staged_tx.organization)
            staged_tx.linked_transaction = target_tx
            staged_tx.reconciliation_status = StagedBankTransaction.RECON_MATCHED
            staged_tx.save(update_fields=['linked_transaction', 'reconciliation_status'])
            AuditLog.objects.create(organization=staged_tx.organization, user=request.user, action='matched_bank_transaction', details={'staged_tx_id': str(staged_tx.id), 'ledger_tx_id': str(target_tx.id)})
            return Response(StagedBankTransactionSerializer(staged_tx).data)
        except Transaction.DoesNotExist:
            return Response({'error': 'Target LedgerPro transaction not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f'Error matching staged tx {staged_tx.id} to tx {ledger_pro_tx_id}: {e}')
            return Response({'error': 'Failed to match transaction.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StagedBankTransactionCreateLedgerView(OrganizationScopedViewMixin, generics.GenericAPIView):
    queryset = StagedBankTransaction.objects.all()
    serializer_class = StagedBankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        staged_tx = self.get_object()
        if staged_tx.reconciliation_status != StagedBankTransaction.RECON_UNMATCHED:
            return Response({'error': 'Transaction already reconciled or processed.'}, status=status.HTTP_400_BAD_REQUEST)
        staged_tx.reconciliation_status = StagedBankTransaction.RECON_CREATED_TRANSACTION
        staged_tx.save(update_fields=['reconciliation_status'])
        AuditLog.objects.create(organization=staged_tx.organization, user=request.user, action='created_ledger_tx_from_bank_tx', details={'staged_tx_id': str(staged_tx.id)})
        logger.info(f'User initiated creation of LedgerPro transaction from staged_tx {staged_tx.id}')
        return Response(StagedBankTransactionSerializer(staged_tx).data)
    @action(detail=True, methods=['get'], url_path='suggest-matches')
    def suggest_matches(self, request, pk=None):
        staged_tx = self.get_object()
        suggestions = reconciliation_service.find_suggested_matches(staged_tx)
        return Response(suggestions)
    @action(detail=True, methods=['post'], url_path='match-to-transaction')
    def match_to_transaction(self, request, pk=None):
        staged_tx = self.get_object()
        ledger_pro_tx_id = request.data.get('ledger_pro_transaction_id')
        if staged_tx.reconciliation_status != StagedBankTransaction.RECON_UNMATCHED: return Response({'error': 'Transaction already reconciled or processed.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_tx = Transaction.objects.get(id=ledger_pro_tx_id, organization=staged_tx.organization)
            staged_tx.linked_transaction = target_tx
            staged_tx.reconciliation_status = StagedBankTransaction.RECON_MATCHED
            staged_tx.save(update_fields=['linked_transaction', 'reconciliation_status'])
            AuditLog.objects.create(organization=staged_tx.organization, user=request.user, action='matched_bank_transaction', details={'staged_tx_id': str(staged_tx.id), 'ledger_tx_id': str(target_tx.id)})
            return Response(StagedBankTransactionSerializer(staged_tx).data)
        except Transaction.DoesNotExist: return Response({'error': 'Target LedgerPro transaction not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f'Error matching staged tx {staged_tx.id} to tx {ledger_pro_tx_id}: {e}')
            return Response({'error': 'Failed to match transaction.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=True, methods=['post'], url_path='create-ledger-transaction')
    def create_ledger_transaction(self, request, pk=None):
        staged_tx = self.get_object()
        if staged_tx.reconciliation_status != StagedBankTransaction.RECON_UNMATCHED: return Response({'error': 'Transaction already reconciled or processed.'}, status=status.HTTP_400_BAD_REQUEST)
        staged_tx.reconciliation_status = StagedBankTransaction.RECON_CREATED_TRANSACTION
        staged_tx.save(update_fields=['reconciliation_status'])
        AuditLog.objects.create(organization=staged_tx.organization, user=request.user, action='created_ledger_tx_from_bank_tx', details={'staged_tx_id': str(staged_tx.id)})
        logger.info(f'User initiated creation of LedgerPro transaction from staged_tx {staged_tx.id}')
        return Response(StagedBankTransactionSerializer(staged_tx).data)
class ProfitAndLossView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, *args, **kwargs):
        membership = request.user.membership_set.first()
        if not membership: return Response({'error': 'User not associated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)
        organization = membership.organization
        try:
            date_from_str = request.query_params.get('date_from')
            date_to_str = request.query_params.get('date_to')
            if not date_from_str or not date_to_str: return Response({'error': 'date_from and date_to query parameters are required.'}, status=status.HTTP_400_BAD_REQUEST)
            date_from = date.fromisoformat(date_from_str)
            date_to = date.fromisoformat(date_to_str)
        except ValueError: return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            report_data = reporting_service.get_profit_and_loss_data(organization, date_from, date_to)
            return Response(report_data)
        except ValueError as ve: return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error generating P&L report for org {organization.id}: {e}')
            return Response({'error': f'Failed to generate report: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class BalanceSheetView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, *args, **kwargs):
        membership = request.user.membership_set.first()
        if not membership: return Response({'error': 'User not associated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)
        organization = membership.organization
        try:
            as_of_date_str = request.query_params.get('as_of_date', date.today().isoformat())
            as_of_date = date.fromisoformat(as_of_date_str)
        except ValueError: return Response({'error': 'Invalid date format for as_of_date. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            report_data = reporting_service.get_balance_sheet_data(organization, as_of_date)
            return Response(report_data)
        except ValueError as ve: return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error generating Balance Sheet report for org {organization.id}: {e}')
            return Response({'error': f'Failed to generate report: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Payroll Views
class EmployeeViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization(), created_by=self.request.user)

class DeductionTypeViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    queryset = DeductionType.objects.all()
    serializer_class = DeductionTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())


class PayRunViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    queryset = PayRun.objects.all().prefetch_related('payslips', 'payslips__employee', 'payslips__deductions_applied__deduction_type')
    serializer_class = PayRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().order_by('-payment_date')

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())

    @action(detail=True, methods=['post'], url_path='process')
    def process_pay_run_action(self, request, pk=None):
        pay_run = self.get_object()
        employee_inputs_data = request.data.get('employee_inputs_for_processing', [])

        try:
            processed_pay_run = payroll_service.process_pay_run(pay_run, employee_inputs_data, request.user)
            return Response(PayRunSerializer(processed_pay_run, context=self.get_serializer_context()).data)
        except ValueError as ve:
            logger.warning(f'Validation error processing pay run {pay_run.id}: {ve}')
            return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error processing pay run {pay_run.id}: {e}')
            return Response({'error': 'Failed to process pay run.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PayslipListView(OrganizationScopedViewMixin, generics.ListAPIView):
    serializer_class = PayslipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Payslip.objects.filter(pay_run__organization=self.get_organization())
        employee_id_param = self.request.query_params.get('employee_id')
        if employee_id_param:
            qs = qs.filter(employee_id=employee_id_param)
        return qs.order_by('-pay_run__payment_date')


class PayslipDetailView(OrganizationScopedViewMixin, generics.RetrieveAPIView):
    serializer_class = PayslipSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
         return Payslip.objects.filter(pay_run__organization=self.get_organization())
