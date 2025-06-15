from .models import (
    User, Organization, Membership, Role, Account, Transaction, JournalEntry, AuditLog,
    Customer, Invoice, InvoiceItem, Vendor, PlaidItem, StagedBankTransaction,
    ReconciliationRule, Employee, PayRun, Payslip, DeductionType, PayslipDeduction
)
from django.contrib.auth import get_user_model
from rest_framework import serializers
from decimal import Decimal
import logging
from .account_utils import get_or_create_default_account

logger = logging.getLogger(__name__)


# User related serializers (from previous steps)


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'email', 'first_name', 'last_name')


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    organization_name = serializers.CharField(write_only=True, required=False, help_text='Required if creating a new organization')

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'organization_name')
        read_only_fields = ('id',)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email address already exists.')
        return value

    def create(self, validated_data):
        organization_name = validated_data.pop('organization_name', None)
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        if organization_name:
            organization, created = Organization.objects.get_or_create(name=organization_name)
            admin_role, _ = Role.objects.get_or_create(name='Admin', defaults={'description': 'Administrator with full access'})
            Membership.objects.create(user=user, organization=organization, role=admin_role)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})


# Core Accounting serializers (from previous steps)


class AccountSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = ['id', 'organization', 'name', 'type', 'description', 'is_active', 'balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'balance', 'created_at', 'updated_at']

    def get_balance(self, obj):
        return obj.get_balance()


class JournalEntrySerializer(serializers.ModelSerializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())

    class Meta:
        model = JournalEntry
        fields = ['id', 'account', 'debit_amount', 'credit_amount', 'description']


class TransactionSerializer(serializers.ModelSerializer):
    journal_entries_set = JournalEntrySerializer(many=True)
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'organization', 'date', 'description', 'reference_number', 'journal_entries_set', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_by', 'created_at', 'updated_at']

    def validate_journal_entries_set(self, journal_entries_data):
        if not journal_entries_data or len(journal_entries_data) < 2:
            raise serializers.ValidationError('A transaction must have at least two journal entries.')
        return journal_entries_data

    def create(self, validated_data):
        journal_entries_data = validated_data.pop('journal_entries_set')
        request = self.context.get('request')
        organization = request.user.membership_set.first().organization
        transaction = Transaction.objects.create(organization=organization, created_by=request.user, **validated_data)
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')
        try:
            for entry_data in journal_entries_data:
                account = entry_data['account']
                if account.organization != organization:
                    raise serializers.ValidationError(f'Account {account.name} invalid for org.')
                JournalEntry.objects.create(transaction=transaction, **entry_data)
                total_debits += entry_data.get('debit_amount', Decimal('0.00'))
                total_credits += entry_data.get('credit_amount', Decimal('0.00'))
            if total_debits != total_credits:
                raise serializers.ValidationError('Debits must equal Credits.')
        except serializers.ValidationError as e:
            transaction.delete()
            raise e
        AuditLog.objects.create(
            organization=organization,
            user=request.user,
            action='created_transaction',
            details={'transaction_id': str(transaction.id)}
        )
        return transaction


class AuditLogSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)
    organization = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'organization', 'action', 'timestamp', 'details']


class CustomerSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'organization', 'name', 'email', 'phone', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class InvoiceItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'amount', 'tax_amount']
        read_only_fields = ['id', 'amount']

    def validate(self, data):
        if 'quantity' in data and 'unit_price' in data:
            data['amount'] = data['quantity'] * data['unit_price']
        elif self.instance:
            quantity = data.get('quantity', self.instance.quantity)
            unit_price = data.get('unit_price', self.instance.unit_price)
            data['amount'] = quantity * unit_price
        return data


class InvoiceSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = UserDetailSerializer(read_only=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    items = InvoiceItemSerializer(many=True)
    transaction = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'organization', 'customer', 'invoice_number',
            'issue_date', 'due_date', 'status',
            'notes', 'subtotal', 'total_tax', 'total_amount',
            'items', 'transaction',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organization', 'subtotal', 'total_tax', 'total_amount',
            'transaction', 'created_by', 'created_at', 'updated_at'
        ]

    def _create_invoice_gl_transaction(self, invoice: Invoice, user):
        organization = invoice.organization
        accounts_receivable_acc = get_or_create_default_account(
            organization, Account.ASSET, 'Accounts Receivable', 'Accounts Receivable (Default)', 'accounts receivable'
        )
        sales_revenue_acc = get_or_create_default_account(
            organization, Account.REVENUE, 'Sales Revenue', 'Sales Revenue (Default)', 'sales revenue'
        )
        sales_tax_payable_acc = None
        if invoice.total_tax > Decimal('0.00'):
            sales_tax_payable_acc = get_or_create_default_account(
                organization, Account.LIABILITY, 'Sales Tax Payable', 'Sales Tax Payable (Default)', 'sales tax payable'
            )
        gl_transaction = Transaction.objects.create(
            organization=organization, date=invoice.issue_date,
            description=f'Invoice {invoice.invoice_number} to {invoice.customer.name}', created_by=user
        )
        JournalEntry.objects.create(
            transaction=gl_transaction, account=accounts_receivable_acc,
            debit_amount=invoice.total_amount, description=f'A/R for Invoice {invoice.invoice_number}'
        )
        JournalEntry.objects.create(
            transaction=gl_transaction, account=sales_revenue_acc,
            credit_amount=invoice.subtotal, description=f'Sales revenue for Invoice {invoice.invoice_number}'
        )
        if sales_tax_payable_acc and invoice.total_tax > Decimal('0.00'):
            JournalEntry.objects.create(
                transaction=gl_transaction, account=sales_tax_payable_acc,
                credit_amount=invoice.total_tax, description=f'Sales tax for Invoice {invoice.invoice_number}'
            )
        current_debits = sum(je.debit_amount for je in gl_transaction.journal_entries_set.all())
        current_credits = sum(je.credit_amount for je in gl_transaction.journal_entries_set.all())
        if current_debits != current_credits:
            logger.error(f'GL Transaction for Invoice {invoice.id} unbalanced! Debits: {current_debits}, Credits: {current_credits}. Deleting GL transaction.')
            gl_transaction.delete()
            raise serializers.ValidationError('Failed to create a balanced GL transaction for the invoice.')
        return gl_transaction

    def validate_customer(self, customer):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            membership = request.user.membership_set.first()
            if membership and customer.organization != membership.organization:
                raise serializers.ValidationError(f"Customer '{customer.name}' does not belong to your organization.")
        return customer

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        membership = request.user.membership_set.first()
        if not membership:
            raise serializers.ValidationError('User is not associated with any organization.')
        organization = membership.organization
        subtotal = sum(item['quantity'] * item['unit_price'] for item in items_data)
        total_tax = sum(item.get('tax_amount', Decimal('0.00')) for item in items_data)
        total_amount = subtotal + total_tax
        invoice = Invoice.objects.create(
            organization=organization, created_by=request.user,
            subtotal=subtotal, total_tax=total_tax, total_amount=total_amount,
            **validated_data
        )
        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)
        if invoice.status == Invoice.SENT:
            try:
                gl_transaction = self._create_invoice_gl_transaction(invoice, request.user)
                invoice.transaction = gl_transaction
                invoice.save(update_fields=['transaction'])
            except serializers.ValidationError as e:
                invoice.delete()
                raise e
            except Exception as e:
                invoice.delete()
                logger.error(f'Unexpected error creating GL for invoice {invoice.id}: {e}')
                raise serializers.ValidationError(f'Failed to create GL transaction for invoice: {str(e)}')
        AuditLog.objects.create(
            organization=organization,
            user=request.user,
            action='created_invoice',
            details={'invoice_id': str(invoice.id), 'invoice_number': invoice.invoice_number, 'status': invoice.status}
        )
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        original_status = instance.status
        new_status = validated_data.get('status', original_status)
        instance.customer = validated_data.get('customer', instance.customer)
        instance.invoice_number = validated_data.get('invoice_number', instance.invoice_number)
        instance.issue_date = validated_data.get('issue_date', instance.issue_date)
        instance.due_date = validated_data.get('due_date', instance.due_date)
        instance.status = new_status
        instance.notes = validated_data.get('notes', instance.notes)
        if items_data is not None:
            instance.items.all().delete()
            current_subtotal = Decimal('0.00')
            current_total_tax = Decimal('0.00')
            for item_data in items_data:
                item_data['amount'] = item_data['quantity'] * item_data['unit_price']
                current_subtotal += item_data['amount']
                current_total_tax += item_data.get('tax_amount', Decimal('0.00'))
                InvoiceItem.objects.create(invoice=instance, **item_data)
            instance.subtotal = current_subtotal
            instance.total_tax = current_total_tax
            instance.total_amount = current_subtotal + current_total_tax
        else:
            instance.calculate_totals()
        instance.save()
        if original_status == Invoice.DRAFT and new_status == Invoice.SENT:
            if not instance.transaction:
                try:
                    gl_transaction = self._create_invoice_gl_transaction(instance, self.context['request'].user)
                    instance.transaction = gl_transaction
                    instance.save(update_fields=['transaction'])
                except Exception as e:
                    logger.error(f'Failed to create GL transaction for invoice {instance.id} on status change to SENT: {e}')
                    pass
        AuditLog.objects.create(
            organization=instance.organization, user=self.context['request'].user, action='updated_invoice',
            details={'invoice_id': str(instance.id), 'invoice_number': instance.invoice_number, 'new_status': new_status}
        )
        return instance


class VendorSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Vendor
        fields = ['id', 'organization', 'name', 'email', 'phone', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']


class PlaidItemSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    user = UserDetailSerializer(read_only=True)

    class Meta:
        model = PlaidItem
        fields = ['id', 'organization', 'user', 'institution_id', 'institution_name', 'last_successful_sync', 'created_at']


# Moved ReconciliationRuleSerializer before StagedBankTransactionSerializer


class ReconciliationRuleSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = UserDetailSerializer(read_only=True)

    class Meta:
        model = ReconciliationRule
        fields = ['id', 'organization', 'name', 'conditions', 'actions', 'priority', 'is_active', 'created_at', 'updated_at', 'created_by']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at', 'created_by']

    def validate_conditions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Conditions must be a list.')
        for cond in value:
            if not all(k in cond for k in ['field', 'operator', 'value']):
                raise serializers.ValidationError('Each condition must have field, operator, and value.')
        return value

    def validate_actions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Actions must be a list.')
        for act in value:
            if 'action_type' not in act:
                raise serializers.ValidationError('Each action must have an action_type.')
        return value


class StagedBankTransactionSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    plaid_item = PlaidItemSerializer(read_only=True, allow_null=True)
    linked_transaction = TransactionSerializer(read_only=True, allow_null=True)
    applied_rule = ReconciliationRuleSerializer(read_only=True, allow_null=True)
    suggested_matches = serializers.JSONField(read_only=True, allow_null=True)

    class Meta:
        model = StagedBankTransaction
        fields = [
            'id', 'organization', 'plaid_item', 'transaction_id_source',
            'account_id_source', 'account_name_source',
            'date', 'posted_date', 'name', 'merchant_name', 'amount', 'currency_code',
            'category_source', 'status_source', 'reconciliation_status',
            'linked_transaction', 'applied_rule', 'suggested_matches',
            'imported_at', 'source'
        ]
        read_only_fields = ['id', 'organization', 'plaid_item', 'imported_at', 'raw_data', 'applied_rule', 'suggested_matches']

# Payroll Serializers


class EmployeeSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = UserDetailSerializer(read_only=True)
    user = UserDetailSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Employee
        fields = ['id', 'organization', 'user', 'first_name', 'last_name', 'email', 'pay_type', 'pay_rate', 'is_active', 'hire_date', 'termination_date', 'created_at', 'updated_at', 'created_by']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at', 'created_by', 'user']


class DeductionTypeSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DeductionType
        fields = ['id', 'organization', 'name', 'tax_treatment', 'is_active']
        read_only_fields = ['id', 'organization']


class PayslipDeductionSerializer(serializers.ModelSerializer):
    deduction_type = DeductionTypeSerializer(read_only=True)
    deduction_type_id = serializers.PrimaryKeyRelatedField(queryset=DeductionType.objects.all(), source='deduction_type', write_only=True)

    class Meta:
        model = PayslipDeduction
        fields = ['id', 'deduction_type', 'deduction_type_id', 'amount']


class PayslipSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)
    deductions_applied = PayslipDeductionSerializer(many=True, read_only=True)

    class Meta:
        model = Payslip
        fields = ['id', 'pay_run', 'employee', 'gross_pay', 'total_deductions', 'net_pay', 'notes', 'created_at', 'deductions_applied']
        read_only_fields = fields


class ManualDeductionInputSerializer(serializers.Serializer):
    deduction_type_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=19, decimal_places=2, required=True)


class PayRunEmployeeInputSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    hours_worked = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    manual_deductions = ManualDeductionInputSerializer(many=True, required=False, allow_empty=True)


class PayRunSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    processed_by = UserDetailSerializer(read_only=True, allow_null=True)
    payslips = PayslipSerializer(many=True, read_only=True)
    employee_inputs_for_processing = PayRunEmployeeInputSerializer(many=True, write_only=True, required=False)
    gl_transaction = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PayRun
        fields = [
            'id', 'organization', 'pay_period_start_date', 'pay_period_end_date', 'payment_date',
            'status', 'notes', 'created_at', 'processed_by', 'processed_at',
            'payslips', 'gl_transaction',
            'employee_inputs_for_processing'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'processed_by', 'processed_at', 'payslips', 'status', 'gl_transaction']
        extra_kwargs = {'status': {'read_only': True}}
