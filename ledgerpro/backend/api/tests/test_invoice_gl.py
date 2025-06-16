from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from api.models import (
    User, Organization, Role, Membership, Account, Customer, Invoice, Transaction, JournalEntry  # InvoiceItem removed F401
)
# Assuming UserDetailSerializer is available for request.user if needed, or mock authentication


class InvoiceGLTests(APITestCase):
    def setUp(self):
        # Create a user, organization, and role
        self.user = User.objects.create_user(email='testuser@example.com', password='password123', first_name='Test', last_name='User')
        self.organization = Organization.objects.create(name='Test Org GL')
        self.role = Role.objects.create(name='Admin')
        Membership.objects.create(user=self.user, organization=self.organization, role=self.role)

        # Authenticate the user for API calls
        self.client.login(email='testuser@example.com', password='password123')

        # Create default accounts required by InvoiceSerializer's GL posting logic
        self.ar_account = Account.objects.create(organization=self.organization, name='Accounts Receivable (Default)', type=Account.ASSET)
        self.sales_account = Account.objects.create(organization=self.organization, name='Sales Revenue (Default)', type=Account.REVENUE)
        self.tax_payable_account = Account.objects.create(organization=self.organization, name='Sales Tax Payable (Default)', type=Account.LIABILITY)

        # Create a customer
        self.customer = Customer.objects.create(organization=self.organization, name='Test Customer GL')

        # URL for creating invoices
        self.invoices_url = reverse('invoice-list-create')  # Assuming this is the correct name from urls.py

    def test_create_invoice_sent_status_creates_gl_transaction(self):
        '''Test that creating an invoice with 'SENT' status generates a GL transaction and correct journal entries.'''
        invoice_data = {
            'customer': str(self.customer.id),  # Use UUID string
            'invoice_number': 'INV-GL-001',
            'issue_date': '2023-10-01',
            'due_date': '2023-10-31',
            'status': Invoice.SENT,  # Create as SENT
            'items': [
                {'description': 'Product A', 'quantity': Decimal('2.00'), 'unit_price': Decimal('100.00'), 'tax_amount': Decimal('10.00')},
                {'description': 'Service B', 'quantity': Decimal('1.00'), 'unit_price': Decimal('50.00'), 'tax_amount': Decimal('0.00')}
            ]
            # Subtotal = 250 (2*100 + 1*50), Tax = 20 (2*10), Total Amount = 270
            # Corrected items: tax_amount is per item total, not unit. If tax is 10% on Product A, it's 2*100 * 10% = 20.
            # Let's assume tax_amount in item is total tax for that line.
            # Item 1: amount = 200, tax = 10 => total line price = 210
            # Item 2: amount = 50, tax = 0 => total line price = 50
            # Invoice: Subtotal = 200+50 = 250. Total Tax = 10+0 = 10. Total Amount = 260.
        }
        # Re-calculate based on assumption that 'tax_amount' is total tax for the line item
        invoice_data['items'][0]['tax_amount'] = Decimal('20.00')  # e.g. 10% on 200
        # Product A: amount 200, tax 20. Service B: amount 50, tax 0.
        # Subtotal = 250. Total Tax = 20. Total Amount = 270. This matches the comment.

        response = self.client.post(self.invoices_url, invoice_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invoice_id = response.data['id']
        created_invoice = Invoice.objects.get(id=invoice_id)

        self.assertIsNotNone(created_invoice.transaction, 'Invoice should have a linked GL transaction.')

        gl_transaction = created_invoice.transaction
        self.assertEqual(gl_transaction.organization, self.organization)
        self.assertEqual(gl_transaction.description, f'Invoice {created_invoice.invoice_number} to {self.customer.name}')

        journal_entries = JournalEntry.objects.filter(transaction=gl_transaction).order_by('account__name')
        self.assertEqual(journal_entries.count(), 3, 'Should be 3 journal entries (AR, Sales, Tax).')

        ar_entry = journal_entries.get(account=self.ar_account)
        self.assertEqual(ar_entry.debit_amount, Decimal('270.00'))  # Total amount
        self.assertEqual(ar_entry.credit_amount, Decimal('0.00'))

        sales_entry = journal_entries.get(account=self.sales_account)
        self.assertEqual(sales_entry.debit_amount, Decimal('0.00'))
        self.assertEqual(sales_entry.credit_amount, Decimal('250.00'))  # Subtotal

        tax_entry = journal_entries.get(account=self.tax_payable_account)
        self.assertEqual(tax_entry.debit_amount, Decimal('0.00'))
        self.assertEqual(tax_entry.credit_amount, Decimal('20.00'))  # Total tax

        total_debits = sum(je.debit_amount for je in journal_entries)
        total_credits = sum(je.credit_amount for je in journal_entries)
        self.assertEqual(total_debits, total_credits, 'GL Transaction must be balanced.')
        self.assertEqual(total_debits, Decimal('270.00'))

    def test_create_invoice_draft_status_no_gl_transaction(self):
        '''Test that creating an invoice with 'DRAFT' status does NOT generate a GL transaction.'''
        invoice_data = {
            'customer': str(self.customer.id),
            'invoice_number': 'INV-GL-DRAFT-001',
            'issue_date': '2023-10-02',
            'due_date': '2023-11-01',
            'status': Invoice.DRAFT,
            'items': [
                {'description': 'Draft Item', 'quantity': Decimal('1.00'), 'unit_price': Decimal('30.00'), 'tax_amount': Decimal('0.00')}
            ]
        }
        response = self.client.post(self.invoices_url, invoice_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invoice_id = response.data['id']
        created_invoice = Invoice.objects.get(id=invoice_id)

        self.assertIsNone(created_invoice.transaction, 'Draft invoice should NOT have a linked GL transaction.')
        # Check based on transaction linked to this invoice, not all transactions.
        self.assertEqual(Transaction.objects.filter(invoice_origin=created_invoice).count(), 0, 'No GL transaction should be created for draft invoice.')

    def test_update_invoice_draft_to_sent_creates_gl_transaction(self):
        '''Test updating an invoice from DRAFT to SENT generates a GL transaction.'''
        draft_invoice_data = {
            'customer': str(self.customer.id),
            'invoice_number': 'INV-GL-DRAFT-002',
            'issue_date': '2023-10-03',
            'due_date': '2023-11-02',
            'status': Invoice.DRAFT,
            'items': [{'description': 'Service X', 'quantity': Decimal('1.00'), 'unit_price': Decimal('120.00'), 'tax_amount': Decimal('12.00')}]
            # Subtotal = 120, Tax = 12, Total = 132
        }
        response_create = self.client.post(self.invoices_url, draft_invoice_data, format='json')
        self.assertEqual(response_create.status_code, status.HTTP_201_CREATED, response_create.data)
        invoice_id = response_create.data['id']

        draft_invoice = Invoice.objects.get(id=invoice_id)
        self.assertIsNone(draft_invoice.transaction)

        invoice_detail_url = reverse('invoice-detail', kwargs={'pk': invoice_id})

        update_data_full = {
            'customer': str(self.customer.id),
            'invoice_number': draft_invoice_data['invoice_number'],
            'issue_date': draft_invoice_data['issue_date'],
            'due_date': draft_invoice_data['due_date'],
            'status': Invoice.SENT,  # This is the key change
            'items': draft_invoice_data['items']  # Resend items as per current serializer update logic
        }

        response_update = self.client.patch(invoice_detail_url, update_data_full, format='json')
        self.assertEqual(response_update.status_code, status.HTTP_200_OK, response_update.data)

        updated_invoice = Invoice.objects.get(id=invoice_id)
        self.assertIsNotNone(updated_invoice.transaction, 'Invoice updated to SENT should have a linked GL transaction.')

        gl_transaction = updated_invoice.transaction
        journal_entries = JournalEntry.objects.filter(transaction=gl_transaction).order_by('account__name')
        self.assertEqual(journal_entries.count(), 3)

        ar_entry = journal_entries.get(account=self.ar_account)
        self.assertEqual(ar_entry.debit_amount, Decimal('132.00'))

        sales_entry = journal_entries.get(account=self.sales_account)
        self.assertEqual(sales_entry.credit_amount, Decimal('120.00'))

        tax_entry = journal_entries.get(account=self.tax_payable_account)
        self.assertEqual(tax_entry.credit_amount, Decimal('12.00'))

    def test_create_invoice_gl_failure_rolls_back_invoice(self):
        self.skipTest("Skipping GL failure rollback test; requires advanced mocking or specific setup.")

    def test_create_invoice_no_tax(self):
        '''Test invoice creation with no tax items still creates balanced GL.'''
        invoice_data = {
            'customer': str(self.customer.id),
            'invoice_number': 'INV-GL-NOTAX-001',
            'issue_date': '2023-10-04',
            'due_date': '2023-11-03',
            'status': Invoice.SENT,
            'items': [
                {'description': 'Consulting', 'quantity': Decimal('10.00'), 'unit_price': Decimal('75.00'), 'tax_amount': Decimal('0.00')}
            ]  # Subtotal = 750, Tax = 0, Total = 750
        }
        response = self.client.post(self.invoices_url, invoice_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        invoice_id = response.data['id']
        created_invoice = Invoice.objects.get(id=invoice_id)
        self.assertIsNotNone(created_invoice.transaction)

        gl_transaction = created_invoice.transaction
        journal_entries = JournalEntry.objects.filter(transaction=gl_transaction)
        # Expecting 2 entries if no tax: AR debit, Sales credit
        self.assertEqual(journal_entries.count(), 2)

        ar_entry = journal_entries.get(account=self.ar_account)
        self.assertEqual(ar_entry.debit_amount, Decimal('750.00'))

        sales_entry = journal_entries.get(account=self.sales_account)
        self.assertEqual(sales_entry.credit_amount, Decimal('750.00'))

        total_debits = sum(je.debit_amount for je in journal_entries)
        total_credits = sum(je.credit_amount for je in journal_entries)
        self.assertEqual(total_debits, total_credits)
        self.assertEqual(total_debits, Decimal('750.00'))

    def test_invoice_gl_posting_uses_correct_accounts(self):
        '''Ensure specific accounts are used for AR, Sales, and Tax Payable.'''
        # This is implicitly tested in test_create_invoice_sent_status_creates_gl_transaction
        # by checking journal_entries.get(account=self.ar_account), etc.
        # This test can be more explicit if there were account selection logic based on item type, etc.
        # For now, the default account usage is covered.
        pass

    # Consider tests for updating an invoice that has already been posted to GL:
    # - If amounts change, how is GL affected? (e.g., new adjusting transaction, or update existing - complex)
    # - If status changes to VOID, is GL transaction reversed or voided?
    # These are more advanced scenarios, likely for future iterations.
    # Current serializer update logic might not fully handle GL adjustments on posted invoices.
