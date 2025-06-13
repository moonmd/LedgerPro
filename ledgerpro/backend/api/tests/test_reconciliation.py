from django.urls import reverse
from django.test import TestCase  # Changed from APITestCase for ReconciliationServiceTests
from rest_framework import status
from rest_framework.test import APITestCase  # Keep for ReconciliationAPITests
from unittest import mock
from decimal import Decimal
from datetime import date

from ledgerpro.backend.api.models import (
    User, Organization, Role, Membership, Account, StagedBankTransaction, ReconciliationRule  # Transaction removed F401
)
from ledgerpro.backend.api.reconciliation_service import (
    evaluate_condition, check_rule_conditions, apply_rule_actions, run_reconciliation_rules_for_organization
)


class ReconciliationServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Recon Service Org')
        self.user = User.objects.create_user(email='recon_user@example.com', password='password')
        self.expense_account = Account.objects.create(organization=self.organization, name='Office Supplies Expense', type=Account.EXPENSE)

    def test_evaluate_condition(self):
        self.assertTrue(evaluate_condition('Starbucks Coffee', 'contains', 'Starbucks'))
        self.assertFalse(evaluate_condition('Shell Gas', 'contains', 'Starbucks'))
        self.assertTrue(evaluate_condition('Shell Gas', 'does_not_contain', 'Starbucks'))
        self.assertTrue(evaluate_condition(Decimal('-25.00'), 'equals', Decimal('-25.00')))
        self.assertFalse(evaluate_condition(Decimal('-25.00'), 'equals', Decimal('-20.00')))
        self.assertTrue(evaluate_condition(Decimal('-10.00'), 'greater_than', Decimal('-15.00')))
        self.assertTrue(evaluate_condition(Decimal('-20.00'), 'less_than', Decimal('-15.00')))
        self.assertTrue(evaluate_condition('Completed', 'equals', 'Completed'))

    def test_check_rule_conditions(self):
        tx_data = {
            'organization': self.organization, 'date': date.today(), 'name': 'Payment to STARBUCKS Store 123',
            'amount': Decimal('-12.50'), 'currency_code': 'USD', 'transaction_id_source': 'recon_tx_1'
        }
        staged_tx = StagedBankTransaction.objects.create(**tx_data)

        rule_conditions_match = [
            {'field': 'name', 'operator': 'contains', 'value': 'Starbucks'},
            {'field': 'amount', 'operator': 'less_than', 'value': Decimal('-10.00')}
        ]
        rule_match = ReconciliationRule(conditions=rule_conditions_match, name="Match Rule", organization=self.organization)
        self.assertTrue(check_rule_conditions(staged_tx, rule_match))

        rule_conditions_no_match_name = [{'field': 'name', 'operator': 'contains', 'value': 'Microsoft'}]
        rule_no_match_name = ReconciliationRule(conditions=rule_conditions_no_match_name, name="No Match Name", organization=self.organization)
        self.assertFalse(check_rule_conditions(staged_tx, rule_no_match_name))

        rule_conditions_no_match_amount = [{'field': 'amount', 'operator': 'greater_than', 'value': Decimal('0.00')}]
        rule_no_match_amount = ReconciliationRule(conditions=rule_conditions_no_match_amount, name="No Match Amount", organization=self.organization)
        self.assertFalse(check_rule_conditions(staged_tx, rule_no_match_amount))

    @mock.patch('ledgerpro.backend.api.reconciliation_service.Account.objects.get')
    def test_apply_rule_actions_categorize(self, mock_account_get):
        mock_account_get.return_value = self.expense_account

        staged_tx = StagedBankTransaction.objects.create(
            organization=self.organization, date=date.today(), name='Misc Purchase',
            amount=Decimal('-50.00'), transaction_id_source='recon_tx_2',
            reconciliation_status=StagedBankTransaction.RECON_UNMATCHED
        )
        # Ensure applied_rule field exists on StagedBankTransaction for this test to pass fully
        # If not, the save() call in apply_rule_actions might error or not set it.
        # The previous model update step should have added this.
        rule_actions = [{'action_type': 'categorize', 'account_id': str(self.expense_account.id)}]
        rule = ReconciliationRule.objects.create(actions=rule_actions, name='Test Categorize Rule', organization=self.organization, conditions=[{'field': 'name', 'operator': 'contains', 'value': 'Misc'}])

        apply_rule_actions(staged_tx, rule, self.user)
        staged_tx.refresh_from_db()

        self.assertEqual(staged_tx.reconciliation_status, StagedBankTransaction.RECON_RULE_APPLIED)
        self.assertEqual(staged_tx.applied_rule, rule)
        mock_account_get.assert_called_once_with(id=str(self.expense_account.id), organization=self.organization)

    def test_run_reconciliation_rules_for_organization(self):
        StagedBankTransaction.objects.create(organization=self.organization, date=date.today(), name='Starbucks Coffee', amount=Decimal('-5.00'), transaction_id_source='unmatched1', reconciliation_status=StagedBankTransaction.RECON_UNMATCHED)
        StagedBankTransaction.objects.create(organization=self.organization, date=date.today(), name='Office Depot', amount=Decimal('-75.00'), transaction_id_source='unmatched2', reconciliation_status=StagedBankTransaction.RECON_UNMATCHED)
        StagedBankTransaction.objects.create(organization=self.organization, date=date.today(), name='Client Payment', amount=Decimal('200.00'), transaction_id_source='unmatched3', reconciliation_status=StagedBankTransaction.RECON_UNMATCHED)

        ReconciliationRule.objects.create(
            organization=self.organization, name='Starbucks Rule', priority=1, is_active=True,
            conditions=[{'field': 'name', 'operator': 'contains', 'value': 'Starbucks'}],
            actions=[{'action_type': 'categorize', 'account_id': str(self.expense_account.id)}],
            created_by=self.user
        )
        ReconciliationRule.objects.create(
            organization=self.organization, name='Office Depot Rule', priority=2, is_active=True,
            conditions=[{'field': 'name', 'operator': 'contains', 'value': 'Office Depot'}],
            actions=[{'action_type': 'categorize', 'account_id': str(self.expense_account.id)}],
            created_by=self.user
        )

        applied_count = run_reconciliation_rules_for_organization(self.organization, self.user)
        self.assertEqual(applied_count, 2)

        self.assertEqual(StagedBankTransaction.objects.get(transaction_id_source='unmatched1').reconciliation_status, StagedBankTransaction.RECON_RULE_APPLIED)
        self.assertEqual(StagedBankTransaction.objects.get(transaction_id_source='unmatched2').reconciliation_status, StagedBankTransaction.RECON_RULE_APPLIED)
        self.assertEqual(StagedBankTransaction.objects.get(transaction_id_source='unmatched3').reconciliation_status, StagedBankTransaction.RECON_UNMATCHED)


class ReconciliationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='reconapi@example.com', password='password123')
        self.organization = Organization.objects.create(name='Recon API Org')
        # Role.objects.create_default_roles_for_organization(self.organization) # Assuming this helper exists
        self.admin_role = Role.objects.filter(name='Admin').first()
        if not self.admin_role:  # Create a simple Admin role if not present from migrations or default creation
            self.admin_role = Role.objects.create(name='Admin', description='Default Admin Role')

        Membership.objects.create(user=self.user, organization=self.organization, role=self.admin_role)
        self.client.login(email='reconapi@example.com', password='password123')

        self.rules_url = reverse('recon-rule-list-create')
        self.apply_rules_url = reverse('apply-recon-rules')
        self.staged_tx_list_url = reverse('staged-bank-transaction-list')

    def test_create_and_list_reconciliation_rule(self):
        # Need an account for the action part
        expense_acc = Account.objects.create(organization=self.organization, name='API Test Expense', type=Account.EXPENSE)
        rule_data = {
            'name': 'Test Rule API',
            'conditions': [{'field': 'name', 'operator': 'contains', 'value': 'API Test'}],  # Changed 'description' to 'name' for StagedTx
            'actions': [{'action_type': 'categorize', 'account_id': str(expense_acc.id)}],
            'priority': 10,
            'is_active': True
        }
        response_create = self.client.post(self.rules_url, rule_data, format='json')
        self.assertEqual(response_create.status_code, status.HTTP_201_CREATED, response_create.data)

        response_list = self.client.get(self.rules_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_list.data), 1)
        self.assertEqual(response_list.data[0]['name'], 'Test Rule API')

    @mock.patch('ledgerpro.backend.api.reconciliation_service.run_reconciliation_rules_for_organization')
    def test_apply_reconciliation_rules_api(self, mock_run_rules):
        mock_run_rules.return_value = 5
        response = self.client.post(self.apply_rules_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('5 reconciliation rules applied successfully', response.data['message'])
        mock_run_rules.assert_called_once_with(self.organization, self.user)
