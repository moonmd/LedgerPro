from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.db.models import Sum, Q, F
from django.core.exceptions import ValidationError
import uuid
from decimal import Decimal # Added for get_period_activity

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Role(models.Model):
    # Predefined roles, e.g., Admin, Accountant, Sales Manager, ReadOnly
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizations = models.ManyToManyField(
        Organization,
        through='Membership',
        related_name='users'
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()
    def __str__(self):
        return self.email

class Membership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    date_joined = models.DateField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'organization')
    def __str__(self):
        return f'{self.user.email} in {self.organization.name} as {self.role.name if self.role else "No Role"}'

class Account(models.Model):
    ASSET = 'ASSET'
    LIABILITY = 'LIABILITY'
    EQUITY = 'EQUITY'
    REVENUE = 'REVENUE'
    EXPENSE = 'EXPENSE'
    ACCOUNT_TYPE_CHOICES = [
        (ASSET, 'Asset'), (LIABILITY, 'Liability'), (EQUITY, 'Equity'),
        (REVENUE, 'Revenue'), (EXPENSE, 'Expense'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('organization', 'name', 'type')
    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'
    def get_balance(self, date_to=None):
        debit_sum = self.journal_entries.filter(
            Q(transaction__date__lte=date_to) if date_to else Q()
        ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
        credit_sum = self.journal_entries.filter(
            Q(transaction__date__lte=date_to) if date_to else Q()
        ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
        if self.type in [self.ASSET, self.EXPENSE]:
            return debit_sum - credit_sum
        else:
            return credit_sum - debit_sum
    def get_period_activity(self, date_from, date_to):
        if not (date_from and date_to):
            raise ValueError('Both date_from and date_to are required for period activity.')
        debits_in_period = self.journal_entries.filter(
            transaction__date__gte=date_from, transaction__date__lte=date_to
        ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
        credits_in_period = self.journal_entries.filter(
            transaction__date__gte=date_from, transaction__date__lte=date_to
        ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
        if self.type == self.REVENUE:
            return credits_in_period - debits_in_period
        elif self.type == self.EXPENSE:
            return debits_in_period - credits_in_period
        elif self.type == self.ASSET:
            return debits_in_period - credits_in_period
        elif self.type in [self.LIABILITY, self.EQUITY]:
            return credits_in_period - debits_in_period
        return Decimal('0.00')

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField()
    description = models.TextField()
    reference_number = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_transactions')
    def __str__(self):
        return f'Transaction {self.id} on {self.date} for {self.organization.name}'
    def clean(self):
        super().clean()
        if hasattr(self, 'journal_entries_set'):
            entries = self.journal_entries_set.all()
            if entries.exists():
                total_debits = entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                total_credits = entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
                if total_debits != total_credits:
                    raise ValidationError('Debits must equal Credits for the transaction.')
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='journal_entries_set')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_entries')
    debit_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    credit_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    description = models.CharField(max_length=255, blank=True, null=True)
    class Meta:
        verbose_name_plural = 'Journal Entries'
    def __str__(self):
        if self.debit_amount > 0:
            return f'DEBIT {self.account.name}: {self.debit_amount}'
        return f'CREDIT {self.account.name}: {self.credit_amount}'
    def clean(self):
        super().clean()
        if self.debit_amount < Decimal('0.00') or self.credit_amount < Decimal('0.00'):
            raise ValidationError('Debit and Credit amounts cannot be negative.')
        if self.debit_amount > Decimal('0.00') and self.credit_amount > Decimal('0.00'):
            raise ValidationError('A journal entry line cannot be both a debit and a credit.')
        if self.debit_amount == Decimal('0.00') and self.credit_amount == Decimal('0.00'):
            raise ValidationError('Either debit or credit amount must be provided.')
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, null=True)
    def __str__(self):
        return f'{self.action} by {self.user.email if self.user else "System"} at {self.timestamp}'

class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('organization', 'name')
        ordering = ['name']
    def __str__(self):
        return self.name

class Invoice(models.Model):
    DRAFT = 'DRAFT'
    SENT = 'SENT'
    PAID = 'PAID'
    VOID = 'VOID'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'), (SENT, 'Sent'), (PAID, 'Paid'), (VOID, 'Void'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invoices')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    invoice_number = models.CharField(max_length=50)
    issue_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True, null=True)
    subtotal = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    total_tax = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    transaction = models.OneToOneField(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_origin'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    class Meta:
        unique_together = ('organization', 'invoice_number')
        ordering = ['-issue_date', '-invoice_number']
    def __str__(self):
        return f'Invoice {self.invoice_number} for {self.customer.name}'
    def calculate_totals(self):
        items = self.items.all()
        self.subtotal = sum(item.amount for item in items if item.amount is not None)
        self.total_tax = sum(item.tax_amount for item in items if item.tax_amount is not None)
        self.total_amount = self.subtotal + self.total_tax

class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=19, decimal_places=2)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))
    def save(self, *args, **kwargs):
        if self.quantity is not None and self.unit_price is not None:
            self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    def __str__(self):
        return f'{self.description} (Qty: {self.quantity})'

class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='vendors')
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('organization', 'name')
        ordering = ['name']
    def __str__(self):
        return self.name

class PlaidItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='plaid_items')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text='User who linked this item')
    access_token = models.CharField(max_length=255, unique=True)
    item_id = models.CharField(max_length=255, unique=True)
    institution_id = models.CharField(max_length=255, blank=True, null=True)
    institution_name = models.CharField(max_length=255, blank=True, null=True)
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    sync_cursor = models.CharField(max_length=255, blank=True, null=True, help_text='Cursor for Plaid transactions sync')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f'{self.institution_name} for {self.organization.name} (Item ID: {self.item_id})'

class StagedBankTransaction(models.Model):
    PENDING = 'PENDING'
    POSTED = 'POSTED'
    STATUS_CHOICES = [ (PENDING, 'Pending'), (POSTED, 'Posted'), ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='staged_bank_transactions')
    plaid_item = models.ForeignKey(PlaidItem, on_delete=models.CASCADE, null=True, blank=True, related_name='staged_transactions', help_text='Associated Plaid item if imported via Plaid')
    transaction_id_source = models.CharField(max_length=255, unique=True, help_text='Unique ID from Plaid or bank statement line')
    account_id_source = models.CharField(max_length=255, blank=True, null=True, help_text='Account ID from Plaid or bank')
    account_name_source = models.CharField(max_length=255, blank=True, null=True, help_text='Account name/mask from Plaid or bank')
    date = models.DateField(help_text='Transaction date')
    posted_date = models.DateField(null=True, blank=True, help_text='Date transaction was posted')
    name = models.TextField(help_text='Transaction name or description from bank')
    merchant_name = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2, help_text='Positive for credits, negative for debits from bank perspective')
    currency_code = models.CharField(max_length=3, default='USD')
    category_source = models.CharField(max_length=255, blank=True, null=True, help_text='Category from Plaid or bank')
    status_source = models.CharField(max_length=50, default=POSTED, choices=STATUS_CHOICES, help_text='Status from bank/Plaid')
    RECON_UNMATCHED = 'UNMATCHED'
    RECON_MATCHED = 'MATCHED'
    RECON_RULE_APPLIED = 'RULE_APPLIED'
    RECON_CREATED_TRANSACTION = 'CREATED_TRANSACTION'
    RECON_STATUS_CHOICES = [
        (RECON_UNMATCHED, 'Unmatched'), (RECON_MATCHED, 'Matched to Existing'),
        (RECON_RULE_APPLIED, 'Rule Applied'), (RECON_CREATED_TRANSACTION, 'New Transaction Created'),
    ]
    reconciliation_status = models.CharField(max_length=30, choices=RECON_STATUS_CHOICES, default=RECON_UNMATCHED)
    linked_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_bank_transactions')
    applied_rule = models.ForeignKey('ReconciliationRule', on_delete=models.SET_NULL, null=True, blank=True, related_name='applied_to_transactions')
    raw_data = models.JSONField(null=True, blank=True, help_text='Raw data from Plaid or CSV for auditing/debugging')
    imported_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=10, choices=[('PLAID', 'Plaid'), ('CSV', 'CSV'), ('QBO', 'QBO')], default='PLAID')
    class Meta:
        ordering = ['-date', '-imported_at']
        unique_together = ('organization', 'transaction_id_source')
    def __str__(self):
        return f'{self.name} ({self.amount} {self.currency_code}) on {self.date}'

class ReconciliationRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='reconciliation_rules')
    name = models.CharField(max_length=255, help_text='User-defined name for the rule')
    conditions = models.JSONField(help_text='List of conditions for the rule to apply')
    actions = models.JSONField(help_text='Actions to perform if rule matches')
    priority = models.IntegerField(default=0, help_text='Rules with lower numbers are processed first')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_recon_rules')
    class Meta:
        ordering = ['organization', 'priority', 'name']
    def __str__(self):
        return f'{self.name} for {self.organization.name}'

# Payroll Models (ST-106)

class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='employees')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profile', help_text='Link to system user if employee has login access')

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)

    SALARY = 'SALARY'
    HOURLY = 'HOURLY'
    PAY_TYPE_CHOICES = [
        (SALARY, 'Salary'),
        (HOURLY, 'Hourly'),
    ]
    pay_type = models.CharField(max_length=10, choices=PAY_TYPE_CHOICES)
    pay_rate = models.DecimalField(max_digits=19, decimal_places=2, help_text='Annual salary or hourly rate')

    is_active = models.BooleanField(default=True)
    hire_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_employees')

    class Meta:
        unique_together = ('organization', 'email')
        ordering = ['organization', 'last_name', 'first_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.organization.name})'


class PayRun(models.Model):
    '''Represents a payroll cycle for a group of employees.'''
    DRAFT = 'DRAFT'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    VOIDED = 'VOIDED'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (VOIDED, 'Voided'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='pay_runs')
    pay_period_start_date = models.DateField()
    pay_period_end_date = models.DateField()
    payment_date = models.DateField(help_text='Date employees will be paid')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_pay_runs')
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['organization', '-payment_date']

    def __str__(self):
        return f'PayRun for {self.organization.name} ({self.pay_period_start_date} to {self.pay_period_end_date})'


class DeductionType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='deduction_types')
    name = models.CharField(max_length=100)
    PRE_TAX = 'PRE_TAX'
    POST_TAX = 'POST_TAX'
    TAX_TYPE_CHOICES = [
        (PRE_TAX, 'Pre-tax'),
        (POST_TAX, 'Post-tax'),
    ]
    tax_treatment = models.CharField(max_length=10, choices=TAX_TYPE_CHOICES, default=POST_TAX)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('organization', 'name')
    def __str__(self):
        return f'{self.name} ({self.get_tax_treatment_display()})'


class Payslip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pay_run = models.ForeignKey(PayRun, on_delete=models.CASCADE, related_name='payslips')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='payslips')

    gross_pay = models.DecimalField(max_digits=19, decimal_places=2)

    total_deductions = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'))

    net_pay = models.DecimalField(max_digits=19, decimal_places=2)

    notes = models.TextField(blank=True, null=True, help_text='e.g., hours worked if hourly')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('pay_run', 'employee')
        ordering = ['pay_run', 'employee__last_name']

    def __str__(self):
        return f'Payslip for {self.employee} - PayRun {self.pay_run.id}'

class PayslipDeduction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='deductions_applied')
    deduction_type = models.ForeignKey(DeductionType, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=19, decimal_places=2)

    def __str__(self):
        return f'{self.deduction_type.name}: {self.amount} for {self.payslip.employee}'
