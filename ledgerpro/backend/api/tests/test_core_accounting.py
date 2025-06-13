from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date  # timedelta removed (F401)
from ledgerpro.backend.api.models import Organization, Account, Transaction, JournalEntry, User


class CoreAccountingModelTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Test Core Org')
        self.user = User.objects.create_user(email='coretest@example.com', password='password')

        # Chart of Accounts
        self.asset_acc = Account.objects.create(organization=self.organization, name='Bank', type=Account.ASSET)
        self.expense_acc = Account.objects.create(organization=self.organization, name='Office Supplies', type=Account.EXPENSE)
        self.revenue_acc = Account.objects.create(organization=self.organization, name='Sales Revenue', type=Account.REVENUE)
        self.liability_acc = Account.objects.create(organization=self.organization, name='Loans Payable', type=Account.LIABILITY)
        self.equity_acc = Account.objects.create(organization=self.organization, name='Owner Equity', type=Account.EQUITY)

    def test_account_balance_calculation(self):
        # Initial balances should be zero
        self.assertEqual(self.asset_acc.get_balance(), Decimal('0.00'))

        # Create a transaction: Debit Asset, Credit Revenue
        tx1_date = date(2023, 1, 5)
        tx1 = Transaction.objects.create(organization=self.organization, date=tx1_date, description='Initial Sale', created_by=self.user)
        JournalEntry.objects.create(transaction=tx1, account=self.asset_acc, debit_amount=Decimal('1000.00'))
        JournalEntry.objects.create(transaction=tx1, account=self.revenue_acc, credit_amount=Decimal('1000.00'))

        self.assertEqual(self.asset_acc.get_balance(date_to=tx1_date), Decimal('1000.00'))
        self.assertEqual(self.revenue_acc.get_balance(date_to=tx1_date), Decimal('1000.00'))  # Revenue accounts increase with credit

        # Another transaction: Debit Expense, Credit Asset
        tx2_date = date(2023, 1, 10)
        tx2 = Transaction.objects.create(organization=self.organization, date=tx2_date, description='Bought Supplies', created_by=self.user)
        JournalEntry.objects.create(transaction=tx2, account=self.expense_acc, debit_amount=Decimal('50.00'))
        JournalEntry.objects.create(transaction=tx2, account=self.asset_acc, credit_amount=Decimal('50.00'))

        self.assertEqual(self.asset_acc.get_balance(date_to=tx2_date), Decimal('950.00'))  # 1000 - 50
        self.assertEqual(self.expense_acc.get_balance(date_to=tx2_date), Decimal('50.00'))  # Expense accounts increase with debit

        # Test balance as of a date between transactions
        self.assertEqual(self.asset_acc.get_balance(date_to=date(2023, 1, 7)), Decimal('1000.00'))

        # Test balance with no activity up to a date
        self.assertEqual(self.liability_acc.get_balance(date_to=date(2023, 1, 15)), Decimal('0.00'))

    def test_account_period_activity(self):
        # Setup transactions across different periods
        tx_jan5 = Transaction.objects.create(organization=self.organization, date=date(2023, 1, 5), description='Jan Sale', created_by=self.user)
        JournalEntry.objects.create(transaction=tx_jan5, account=self.revenue_acc, credit_amount=Decimal('200.00'))  # Rev: +200
        JournalEntry.objects.create(transaction=tx_jan5, account=self.asset_acc, debit_amount=Decimal('200.00'))  # Asset: +200

        tx_jan15 = Transaction.objects.create(organization=self.organization, date=date(2023, 1, 15), description='Jan Expense', created_by=self.user)
        JournalEntry.objects.create(transaction=tx_jan15, account=self.expense_acc, debit_amount=Decimal('30.00'))  # Exp: +30
        JournalEntry.objects.create(transaction=tx_jan15, account=self.asset_acc, credit_amount=Decimal('30.00'))  # Asset: -30 (Net +170)

        tx_feb5 = Transaction.objects.create(organization=self.organization, date=date(2023, 2, 5), description='Feb Sale', created_by=self.user)
        JournalEntry.objects.create(transaction=tx_feb5, account=self.revenue_acc, credit_amount=Decimal('500.00'))  # Rev: +500
        JournalEntry.objects.create(transaction=tx_feb5, account=self.asset_acc, debit_amount=Decimal('500.00'))  # Asset: +500 (Net +670)

        # Test P&L accounts for January
        jan_start, jan_end = date(2023, 1, 1), date(2023, 1, 31)
        self.assertEqual(self.revenue_acc.get_period_activity(jan_start, jan_end), Decimal('200.00'))
        self.assertEqual(self.expense_acc.get_period_activity(jan_start, jan_end), Decimal('30.00'))

        # Test P&L accounts for February
        feb_start, feb_end = date(2023, 2, 1), date(2023, 2, 28)
        self.assertEqual(self.revenue_acc.get_period_activity(feb_start, feb_end), Decimal('500.00'))
        self.assertEqual(self.expense_acc.get_period_activity(feb_start, feb_end), Decimal('0.00'))  # No expense in Feb

        # Test Asset account activity for January (should be +200 - 30 = 170)
        self.assertEqual(self.asset_acc.get_period_activity(jan_start, jan_end), Decimal('170.00'))

    def test_journal_entry_validation(self):
        tx = Transaction.objects.create(organization=self.organization, date=date.today(), description='Test JE Validation', created_by=self.user)

        # Cannot be both debit and credit
        with self.assertRaises(ValidationError):
            JournalEntry(transaction=tx, account=self.asset_acc, debit_amount=10, credit_amount=10).clean()

        # Cannot have negative amounts
        with self.assertRaises(ValidationError):
            JournalEntry(transaction=tx, account=self.asset_acc, debit_amount=-10).clean()
        with self.assertRaises(ValidationError):
            JournalEntry(transaction=tx, account=self.asset_acc, credit_amount=-10).clean()

        # Must have either debit or credit
        with self.assertRaises(ValidationError):
            JournalEntry(transaction=tx, account=self.asset_acc, debit_amount=0, credit_amount=0).clean()

    def test_transaction_double_entry_validation_in_model_clean(self):
        ''' Test Transaction.clean() method for double-entry integrity. '''
        tx = Transaction(organization=self.organization, date=date.today(), description='Balanced TX', created_by=self.user)
        tx.save()

        JournalEntry.objects.create(transaction=tx, account=self.asset_acc, debit_amount=Decimal('100.00'))
        JournalEntry.objects.create(transaction=tx, account=self.revenue_acc, credit_amount=Decimal('100.00'))

        try:
            tx.clean()
        except ValidationError:
            self.fail('Transaction.clean() raised ValidationError unexpectedly for balanced transaction.')

        tx_unbalanced = Transaction(organization=self.organization, date=date.today(), description='Unbalanced TX', created_by=self.user)
        tx_unbalanced.save()
        JournalEntry.objects.create(transaction=tx_unbalanced, account=self.asset_acc, debit_amount=Decimal('100.00'))
        JournalEntry.objects.create(transaction=tx_unbalanced, account=self.revenue_acc, credit_amount=Decimal('90.00'))

        with self.assertRaisesRegex(ValidationError, 'Debits must equal Credits for the transaction.'):
            tx_unbalanced.clean()
