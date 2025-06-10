from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from unittest import mock # For mocking email sending

from ledgerpro.backend.api.models import (
    User, Organization, Role, Membership, Customer, Invoice, InvoiceItem, Account
)

class InvoicingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='invoiceuser@example.com', password='password123')
        self.organization = Organization.objects.create(name='Invoice Test Org')
        self.role = Role.objects.create(name='BillingClerk')
        Membership.objects.create(user=self.user, organization=self.organization, role=self.role)

        self.client.login(email='invoiceuser@example.com', password='password123')

        self.customer1 = Customer.objects.create(organization=self.organization, name='Cust A Inc.')
        self.customer2 = Customer.objects.create(organization=self.organization, name='Cust B Ltd.')

        # For GL posting tests (though main GL tests are in test_invoice_gl.py, ensure accounts exist for serializer)
        Account.objects.get_or_create(organization=self.organization, name='Accounts Receivable (Default)', type=Account.ASSET)
        Account.objects.get_or_create(organization=self.organization, name='Sales Revenue (Default)', type=Account.REVENUE)
        Account.objects.get_or_create(organization=self.organization, name='Sales Tax Payable (Default)', type=Account.LIABILITY)


        self.customers_url = reverse('customer-list-create')
        self.invoices_url = reverse('invoice-list-create')
        self.customer_detail_url = lambda pk: reverse('customer-detail', kwargs={'pk': pk})
        self.invoice_detail_url = lambda pk: reverse('invoice-detail', kwargs={'pk': pk})
        self.invoice_send_email_url = lambda pk: reverse('invoice-send-email', kwargs={'pk': pk})


    # Customer API Tests
    def test_create_customer(self):
        data = {'name': 'New Customer LLC', 'email': 'contact@newcustomer.com'}
        response = self.client.post(self.customers_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Customer.objects.filter(name='New Customer LLC', organization=self.organization).count(), 1)

    def test_list_customers(self):
        response = self.client.get(self.customers_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # customer1 and customer2

    def test_retrieve_customer(self):
        response = self.client.get(self.customer_detail_url(self.customer1.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.customer1.name)

    def test_update_customer(self):
        update_data = {'name': 'Customer A Updated', 'phone': '123-456-7890'}
        response = self.client.patch(self.customer_detail_url(self.customer1.id), update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, 'Customer A Updated')
        self.assertEqual(self.customer1.phone, '123-456-7890')

    def test_delete_customer(self):
        # Create a customer with no invoices to test deletion
        temp_customer = Customer.objects.create(organization=self.organization, name='Temp Cust')
        response = self.client.delete(self.customer_detail_url(temp_customer.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Customer.objects.filter(id=temp_customer.id).exists())

    # Invoice API Tests
    def test_create_invoice_valid_data(self):
        invoice_data = {
            'customer': str(self.customer1.id),
            'invoice_number': 'INV-API-001',
            'issue_date': '2023-11-01',
            'due_date': '2023-11-30',
            'status': Invoice.DRAFT,
            'items': [
                {'description': 'Item X', 'quantity': Decimal('1.00'), 'unit_price': Decimal('200.00'), 'tax_amount': Decimal('20.00')}
            ]
        }
        response = self.client.post(self.invoices_url, invoice_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Invoice.objects.count(), 1)
        created_invoice = Invoice.objects.first()
        self.assertEqual(created_invoice.invoice_number, 'INV-API-001')
        self.assertEqual(created_invoice.items.count(), 1)
        self.assertEqual(created_invoice.subtotal, Decimal('200.00'))
        self.assertEqual(created_invoice.total_tax, Decimal('20.00'))
        self.assertEqual(created_invoice.total_amount, Decimal('220.00'))


    def test_create_invoice_missing_required_fields(self):
        invoice_data = {'customer': str(self.customer1.id)} # Missing many fields
        response = self.client.post(self.invoices_url, invoice_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_invoices(self):
        # Create some invoices
        Invoice.objects.create(organization=self.organization, customer=self.customer1, invoice_number='INV001', issue_date='2023-01-01', due_date='2023-01-31', total_amount=100, created_by=self.user)
        Invoice.objects.create(organization=self.organization, customer=self.customer2, invoice_number='INV002', issue_date='2023-02-01', due_date='2023-02-28', total_amount=200, created_by=self.user)

        response = self.client.get(self.invoices_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    @mock.patch('ledgerpro.backend.api.email_utils.send_invoice_email')
    def test_send_invoice_email_action(self, mock_send_invoice_email):
        mock_send_invoice_email.return_value = True

        invoice = Invoice.objects.create(
            organization=self.organization, customer=self.customer1, created_by=self.user,
            invoice_number='INV-EMAIL-01', issue_date='2023-11-05', due_date='2023-12-05',
            status=Invoice.DRAFT, total_amount=500, subtotal=450, total_tax=50
        )
        self.customer1.email = 'customer@example.com'
        self.customer1.save()

        response = self.client.post(self.invoice_send_email_url(invoice.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['message'], 'Invoice sent successfully.')

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.SENT)
        mock_send_invoice_email.assert_called_once_with(invoice)

    @mock.patch('ledgerpro.backend.api.email_utils.send_invoice_email')
    def test_send_invoice_email_failure(self, mock_send_invoice_email):
        mock_send_invoice_email.return_value = False

        invoice = Invoice.objects.create(
            organization=self.organization, customer=self.customer1, created_by=self.user,
            invoice_number='INV-EMAIL-02', issue_date='2023-11-06', due_date='2023-12-06',
            status=Invoice.DRAFT, total_amount=300, subtotal=270, total_tax=30
        )
        self.customer1.email = 'customer@example.com'
        self.customer1.save()

        response = self.client.post(self.invoice_send_email_url(invoice.id))
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR, response.data)
        self.assertIn('Failed to send invoice email', response.data.get('error', ''))

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.DRAFT)
