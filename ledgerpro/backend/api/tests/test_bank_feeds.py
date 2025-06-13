from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest import mock
from decimal import Decimal
from datetime import date
import io # For creating in-memory file for CSV upload

from ledgerpro.backend.api.models import (
    User, Organization, Role, Membership, PlaidItem, StagedBankTransaction
)
# Assuming plaid_service.get_plaid_client can be mocked if not already done by other tests
# from ledgerpro.backend.api.plaid_service import get_plaid_client # Not strictly needed if mocking at service call level

# Mock Plaid API client responses
class MockPlaidLinkTokenCreateResponse:
    def __init__(self, link_token):
        self.link_token = link_token
        self.request_id = 'mock_request_id'
    def to_dict(self):
        return {'link_token': self.link_token, 'request_id': self.request_id}

class MockPlaidItemPublicTokenExchangeResponse:
    def __init__(self, access_token, item_id):
        self.access_token = access_token
        self.item_id = item_id
        self.request_id = 'mock_request_id'
    def to_dict(self):
        return {'access_token': self.access_token, 'item_id': self.item_id, 'request_id': self.request_id}

class MockPlaidTransaction:
    def __init__(self, transaction_id, account_id, name, amount, date_val, pending=False, category=None, merchant_name=None, iso_currency_code='USD', authorized_date_val=None):
        self.transaction_id = transaction_id
        self.account_id = account_id
        self.name = name
        self.amount = Decimal(str(amount))
        self.date = date.fromisoformat(date_val) if isinstance(date_val, str) else date_val
        self.pending = pending
        self.category = category if category else []
        self.merchant_name = merchant_name
        self.iso_currency_code = iso_currency_code
        self.authorized_date = date.fromisoformat(authorized_date_val) if authorized_date_val else self.date
    def to_dict(self):
        return {
            'transaction_id': self.transaction_id, 'account_id': self.account_id, 'name': self.name,
            'amount': self.amount, 'date': self.date, 'pending': self.pending, # Pass date object directly
            'category': self.category, 'merchant_name': self.merchant_name, 'iso_currency_code': self.iso_currency_code,
            'authorized_date': self.authorized_date # Pass date object
        }

class MockPlaidTransactionsSyncResponse:
    def __init__(self, added_txs, next_cursor):
        self.added = added_txs
        self.modified = []
        self.removed = []
        self.next_cursor = next_cursor
        self.has_more = True
        self.request_id = 'mock_sync_request_id'
    def to_dict(self):
        return {
            'added': [tx.to_dict() for tx in self.added], # plaid_service expects dicts here
            'modified': [], 'removed': [],
            'next_cursor': self.next_cursor, 'has_more': self.has_more,
            'request_id': self.request_id
        }


class BankFeedsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='bankfeeduser@example.com', password='password123')
        self.organization = Organization.objects.create(name='Bank Feed Test Org')
        self.role = Role.objects.create(name='AccountantBF')
        Membership.objects.create(user=self.user, organization=self.organization, role=self.role)

        self.client.login(email='bankfeeduser@example.com', password='password123')

        self.create_link_token_url = reverse('plaid-create-link-token')
        self.exchange_public_token_url = reverse('plaid-exchange-public-token')
        self.fetch_transactions_url = reverse('plaid-fetch-transactions')
        self.manual_import_url = reverse('manual-bank-statement-import')

    @mock.patch('ledgerpro.backend.api.plaid_service.get_plaid_client')
    def test_create_plaid_link_token(self, mock_get_plaid_client):
        mock_plaid_api_instance = mock_get_plaid_client.return_value
        # The service expects the response to be a dict, so to_dict() is good.
        mock_plaid_api_instance.link_token_create.return_value = MockPlaidLinkTokenCreateResponse('mock_link_token_123').to_dict()

        response = self.client.post(self.create_link_token_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['link_token'], 'mock_link_token_123')
        mock_plaid_api_instance.link_token_create.assert_called_once()

    @mock.patch('ledgerpro.backend.api.plaid_service.get_plaid_client')
    def test_exchange_public_token(self, mock_get_plaid_client):
        mock_plaid_api_instance = mock_get_plaid_client.return_value
        mock_plaid_api_instance.item_public_token_exchange.return_value = MockPlaidItemPublicTokenExchangeResponse(
            access_token='mock_access_token', item_id='mock_item_id'
        ).to_dict()

        data = {
            'public_token': 'mock_public_token',
            'institution_id': 'ins_1',
            'institution_name': 'Mock Bank'
        }
        response = self.client.post(self.exchange_public_token_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(PlaidItem.objects.filter(organization=self.organization, item_id='mock_item_id').exists())
        plaid_item = PlaidItem.objects.get(item_id='mock_item_id')
        self.assertEqual(plaid_item.access_token, 'mock_access_token')
        self.assertEqual(plaid_item.institution_name, 'Mock Bank')


    @mock.patch('ledgerpro.backend.api.plaid_service.get_plaid_client')
    @mock.patch('django.utils.timezone.now')
    def test_fetch_plaid_transactions(self, mock_timezone_now, mock_get_plaid_client):
        # Mock timezone.now() to return a fixed, non-naive datetime object
        # Django's DateTimeField expects aware datetime objects if USE_TZ=True (default)
        from django.utils import timezone as django_timezone # Import actual timezone
        mock_timezone_now.return_value = django_timezone.make_aware(django_timezone.datetime(2023,1,1,0,0,0))

        mock_plaid_api_instance = mock_get_plaid_client.return_value

        plaid_item = PlaidItem.objects.create(
            organization=self.organization, user=self.user,
            access_token='test_access_token', item_id='test_item_id',
            sync_cursor=None
        )

        tx1 = MockPlaidTransaction('tx1', 'acc1', 'Coffee Shop', -10.50, '2023-10-01')
        tx2 = MockPlaidTransaction('tx2', 'acc1', 'Salary Deposit', 2000.00, '2023-10-05')
        # Pass the list of mock transaction *objects* to the response mock
        mock_plaid_api_instance.transactions_sync.return_value = MockPlaidTransactionsSyncResponse(
            added_txs=[tx1, tx2], next_cursor='new_cursor_123'
        ).to_dict() # Ensure the service receives a dict

        data = {'plaid_item_id': str(plaid_item.id)}
        response = self.client.post(self.fetch_transactions_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('2 new transactions fetched successfully', response.data['message'])

        self.assertEqual(StagedBankTransaction.objects.filter(organization=self.organization).count(), 2)
        plaid_item.refresh_from_db()
        self.assertEqual(plaid_item.sync_cursor, 'new_cursor_123')
        self.assertEqual(plaid_item.last_successful_sync, mock_timezone_now.return_value)

    def test_manual_csv_import_success(self):
        csv_content = (
            'Date,Description,Amount,Currency\n'
            '2023-11-01,Vendor Payment,-150.75,USD\n'
            '2023-11-03,Client Deposit,2000.00,USD\n'
        )
        csv_file = io.StringIO(csv_content)
        # csv_file.name = 'test_statement.csv' # Not needed for APITestCase file upload if using BytesIO or StringIO directly

        response = self.client.post(self.manual_import_url, {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn('2 transactions imported successfully', response.data['message'])
        self.assertEqual(StagedBankTransaction.objects.filter(organization=self.organization, source='CSV').count(), 2)

        tx1 = StagedBankTransaction.objects.get(name='Vendor Payment')
        self.assertEqual(tx1.amount, Decimal('-150.75'))
        self.assertEqual(tx1.date, date(2023, 11, 1))

    def test_manual_csv_import_partial_failure(self):
        csv_content = (
            'Date,Description,Amount\n'
            '2023-11-05,Good Deposit,500.00\n'
            '2023-11-06,Bad Row Missing Amount,\n'
        )
        csv_file = io.StringIO(csv_content)
        # csv_file.name = 'test_partial.csv'

        response = self.client.post(self.manual_import_url, {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS, response.data)
        self.assertEqual(response.data['imported_count'], 1)
        self.assertEqual(len(response.data['failed_rows']), 1)
        self.assertEqual(response.data['failed_rows'][0]['row'], 2)
        self.assertIn('Amount', response.data['failed_rows'][0]['error'])
        self.assertEqual(StagedBankTransaction.objects.filter(organization=self.organization, source='CSV').count(), 1)

    def test_manual_csv_import_no_file(self):
        response = self.client.post(self.manual_import_url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No file provided', response.data['error'])
