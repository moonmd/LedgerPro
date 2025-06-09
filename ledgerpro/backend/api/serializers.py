from .models import (
    User, Organization, Membership, Role,
    Account, Transaction, JournalEntry, AuditLog,
    Customer, Invoice, InvoiceItem, Vendor,
    PlaidItem, StagedBankTransaction, ReconciliationRule,
    Employee, PayRun, Payslip, DeductionType, PayslipDeduction # Added Payroll models
)
from django.contrib.auth import get_user_model
from rest_framework import serializers
from decimal import Decimal # Ensure Decimal is imported

# Original serializers (User, Role, etc.)
class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model() # Uses AUTH_USER_MODEL
        fields = ('id', 'email', 'first_name', 'last_name')

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    organization_name = serializers.CharField(write_only=True, required=False, help_text='Required if creating a new organization')

    class Meta:
        model = User # Custom User model
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'organization_name')
        read_only_fields = ('id',)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('User with this email already exists.')
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

class AccountSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = ['id', 'organization', 'name', 'type', 'description', 'is_active', 'balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'balance', 'created_at', 'updated_at']

    def get_balance(self, obj):
        return obj.get_balance()

    def validate(self, data):
        return data

class JournalEntrySerializer(serializers.ModelSerializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())

    class Meta:
        model = JournalEntry
        fields = ['id', 'account', 'debit_amount', 'credit_amount', 'description']

    def validate(self, data):
        return data

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
            raise serializers.ValidationError("A transaction must have at least two journal entries.")
        return journal_entries_data

    def create(self, validated_data):
        journal_entries_data = validated_data.pop('journal_entries_set')

        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            raise serializers.ValidationError("User information is missing or user is not authenticated.")

        membership = request.user.membership_set.first()
        if not membership:
            raise serializers.ValidationError("User is not associated with any organization.")
        organization = membership.organization

        transaction = Transaction.objects.create(
            organization=organization,
            created_by=request.user,
            **validated_data
        )

        total_debits = 0
        total_credits = 0

        try:
            for entry_data in journal_entries_data:
                account_instance = entry_data['account']
                if account_instance.organization != organization:
                    raise serializers.ValidationError(
                        f"Account '{account_instance.name}' (ID: {account_instance.id}) does not belong to organization '{organization.name}'."
                    )
                JournalEntry.objects.create(transaction=transaction, **entry_data)
                total_debits += entry_data.get('debit_amount', Decimal('0.00'))
                total_credits += entry_data.get('credit_amount', Decimal('0.00'))

            if total_debits != total_credits:
                raise serializers.ValidationError(f"Debits ({total_debits}) must equal Credits ({total_credits}) for the transaction.")

        except Exception as e:
            transaction.delete()
            raise serializers.ValidationError(f"Error in journal entries: {str(e)}")

        AuditLog.objects.create(
            organization=organization,
            user=request.user,
            action="created_transaction",
            details={'transaction_id': str(transaction.id), 'description': transaction.description}
        )
        return transaction

    def update(self, instance, validated_data):
        journal_entries_data = validated_data.pop('journal_entries_set', None)

        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            raise serializers.ValidationError("User information is missing or user is not authenticated.")

        organization = instance.organization

        instance.date = validated_data.get('date', instance.date)
        instance.description = validated_data.get('description', instance.description)
        instance.reference_number = validated_data.get('reference_number', instance.reference_number)

        if journal_entries_data is not None:
            instance.journal_entries_set.all().delete()
            total_debits = Decimal('0.00')
            total_credits = Decimal('0.00')
            try:
                for entry_data in journal_entries_data:
                    account_instance = entry_data['account']
                    if account_instance.organization != organization:
                        raise serializers.ValidationError(
                            f"Account '{account_instance.name}' (ID: {account_instance.id}) does not belong to organization '{organization.name}'."
                        )
                    JournalEntry.objects.create(transaction=instance, **entry_data)
                    total_debits += entry_data.get('debit_amount', Decimal('0.00'))
                    total_credits += entry_data.get('credit_amount', Decimal('0.00'))

                if total_debits != total_credits:
                    raise serializers.ValidationError(f"Debits ({total_debits}) must equal Credits ({total_credits}) for the transaction.")
            except Exception as e:
                 raise serializers.ValidationError(f"Error in journal entries: {str(e)}")

        instance.save()

        AuditLog.objects.create(
            organization=organization,
            user=request.user,
            action="updated_transaction",
            details={'transaction_id': str(instance.id), 'description': instance.description}
        )
        return instance

class AuditLogSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)
    organization = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'organization', 'action', 'timestamp', 'details']

# Invoicing Serializers
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
        elif 'quantity' in data and self.instance:
             data['amount'] = data['quantity'] * self.instance.unit_price
        elif 'unit_price' in data and self.instance:
             data['amount'] = self.instance.quantity * data['unit_price']
        elif not self.instance and ('quantity' not in data or 'unit_price' not in data):
            raise serializers.ValidationError("Quantity and Unit Price are required to calculate amount.")
        return data

class InvoiceSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = UserDetailSerializer(read_only=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    items = InvoiceItemSerializer(many=True)
    transaction = TransactionSerializer(read_only=True)

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

    def _get_organization_from_context(self):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            raise serializers.ValidationError("User information is missing or user is not authenticated.")
        membership = request.user.membership_set.first()
        if not membership:
            raise serializers.ValidationError("User is not associated with any organization.")
        return membership.organization

    def validate_customer(self, customer):
        organization = self._get_organization_from_context()
        if customer.organization != organization:
            raise serializers.ValidationError(f"Customer '{customer.name}' does not belong to your organization '{organization.name}'.")
        return customer

    def validate_items(self, items_data):
        if not items_data or len(items_data) == 0:
            raise serializers.ValidationError("An invoice must have at least one line item.")
        return items_data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        organization = self._get_organization_from_context()
        request_user = self.context['request'].user

        subtotal = sum(item_data['quantity'] * item_data['unit_price'] for item_data in items_data)
        total_tax = sum(item_data.get('tax_amount', Decimal('0.00')) for item_data in items_data)
        total_amount = subtotal + total_tax

        invoice = Invoice.objects.create(
            organization=organization,
            created_by=request_user,
            subtotal=subtotal,
            total_tax=total_tax,
            total_amount=total_amount,
            **validated_data
        )

        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)

        AuditLog.objects.create(
            organization=organization,
            user=request_user,
            action='created_invoice',
            details={'invoice_id': str(invoice.id), 'invoice_number': invoice.invoice_number}
        )
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        request_user = self.context['request'].user

        instance.customer = validated_data.get('customer', instance.customer)
        instance.invoice_number = validated_data.get('invoice_number', instance.invoice_number)
        instance.issue_date = validated_data.get('issue_date', instance.issue_date)
        instance.due_date = validated_data.get('due_date', instance.due_date)
        instance.status = validated_data.get('status', instance.status)
        instance.notes = validated_data.get('notes', instance.notes)

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                InvoiceItem.objects.create(invoice=instance, **item_data)

        instance.calculate_totals()

        instance.save()

        AuditLog.objects.create(
            organization=instance.organization,
            user=request_user,
            action='updated_invoice',
            details={'invoice_id': str(instance.id), 'invoice_number': instance.invoice_number}
        )
        return instance

# Vendor Serializer
class VendorSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Vendor
        fields = ['id', 'organization', 'name', 'email', 'phone', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

# Bank Feeds Serializers
class PlaidItemSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    user = UserDetailSerializer(read_only=True)

    class Meta:
        model = PlaidItem
        fields = ['id', 'organization', 'user', 'institution_id', 'institution_name', 'last_successful_sync', 'created_at']
        read_only_fields = fields

class StagedBankTransactionSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    plaid_item = PlaidItemSerializer(read_only=True, allow_null=True)
    linked_transaction = TransactionSerializer(read_only=True, allow_null=True)
    applied_rule = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
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

# Reconciliation Rule Serializer
class ReconciliationRuleSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = UserDetailSerializer(read_only=True)

    class Meta:
        model = ReconciliationRule
        fields = [
            'id', 'organization', 'name', 'conditions', 'actions',
            'priority', 'is_active', 'created_at', 'updated_at', 'created_by'
        ]
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

# Payroll Serializers
class EmployeeSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by = UserDetailSerializer(read_only=True)
    user = UserDetailSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'organization', 'user', 'first_name', 'last_name', 'email',
            'pay_type', 'pay_rate', 'is_active', 'hire_date', 'termination_date',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at', 'created_by', 'user']

class DeductionTypeSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = DeductionType
        fields = ['id', 'organization', 'name', 'tax_treatment', 'is_active']
        read_only_fields = ['id', 'organization']


class PayslipDeductionSerializer(serializers.ModelSerializer):
    deduction_type = DeductionTypeSerializer(read_only=True)
    deduction_type_id = serializers.PrimaryKeyRelatedField(
        queryset=DeductionType.objects.all(), source='deduction_type', write_only=True
    )
    class Meta:
        model = PayslipDeduction
        fields = ['id', 'deduction_type', 'deduction_type_id', 'amount']


class PayslipSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer(read_only=True)
    deductions_applied = PayslipDeductionSerializer(many=True, read_only=True)

    class Meta:
        model = Payslip
        fields = [
            'id', 'pay_run', 'employee', 'gross_pay',
            'total_deductions', 'net_pay', 'notes', 'created_at',
            'deductions_applied'
        ]
        read_only_fields = fields


class PayRunEmployeeInputSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    hours_worked = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    manual_deductions = serializers.ListField(
        child=serializers.DictField(
            children={
                'deduction_type_id': serializers.UUIDField(),
                'amount': serializers.DecimalField(max_digits=19, decimal_places=2)
            }
        ),
        required=False,
        allow_empty=True
    )

class PayRunSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    processed_by = UserDetailSerializer(read_only=True, allow_null=True)
    payslips = PayslipSerializer(many=True, read_only=True)
    employee_inputs_for_processing = PayRunEmployeeInputSerializer(many=True, write_only=True, required=False)


    class Meta:
        model = PayRun
        fields = [
            'id', 'organization', 'pay_period_start_date', 'pay_period_end_date', 'payment_date',
            'status', 'notes', 'created_at', 'processed_by', 'processed_at', 'payslips',
            'employee_inputs_for_processing'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'processed_by', 'processed_at', 'payslips']
        # Status can be updated via actions, not directly usually.
        # Making it read_only here, but process_pay_run_action in view will change it.
        # If direct status updates are needed (e.g. voiding), a specific serializer or field override might be used.
        extra_kwargs = {
            'status': {'read_only': True}
        }
