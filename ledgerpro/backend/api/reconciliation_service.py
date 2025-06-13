import logging
from .models import StagedBankTransaction, ReconciliationRule, Account, Organization  # Removed unused Transaction, JournalEntry
from decimal import Decimal
# django.utils.timezone is Not explicitly used in this snippet but good for date operations
# Q and F removed as they are not used

logger = logging.getLogger(__name__)


def evaluate_condition(transaction_value, operator, rule_value):
    '''Evaluates a single condition.'''
    # Ensure types are compatible for comparison, especially for numbers
    if isinstance(transaction_value, (Decimal, int, float)) and isinstance(rule_value, (str, int, float)):
        try:
            transaction_value_decimal = Decimal(str(transaction_value))
            rule_value_decimal = Decimal(str(rule_value))
            # If both are successfully converted to Decimal, use them for comparison
            transaction_value = transaction_value_decimal
            rule_value = rule_value_decimal
        except Exception:  # Specified exception
            # Could not convert both to Decimal, fall back to string or original type comparison
            pass
    elif isinstance(transaction_value, str):  # Ensure rule_value is also string for string operations
        rule_value = str(rule_value)

    if operator == 'contains':
        return str(rule_value).lower() in str(transaction_value).lower()
    elif operator == 'does_not_contain':
        return str(rule_value).lower() not in str(transaction_value).lower()
    elif operator == 'equals':
        # Handle case where one is Decimal and other is int/float after conversion attempt
        if isinstance(transaction_value, Decimal) and isinstance(rule_value, (int, float)):
            return transaction_value == Decimal(str(rule_value))
        return transaction_value == rule_value
    elif operator == 'not_equals':
        if isinstance(transaction_value, Decimal) and isinstance(rule_value, (int, float)):
            return transaction_value != Decimal(str(rule_value))
        return transaction_value != rule_value
    elif operator == 'greater_than':
        if isinstance(transaction_value, (Decimal, int, float)) and isinstance(rule_value, (Decimal, int, float)):
            return transaction_value > rule_value
    elif operator == 'less_than':
        if isinstance(transaction_value, (Decimal, int, float)) and isinstance(rule_value, (Decimal, int, float)):
            return transaction_value < rule_value
    # Add more operators: starts_with, ends_with, is_empty, etc.
    logger.debug(f"Unsupported operator: {operator} or incompatible types for value: {transaction_value} and rule value: {rule_value}")
    return False


def check_rule_conditions(staged_tx: StagedBankTransaction, rule: ReconciliationRule):
    '''Checks if a staged transaction matches all conditions of a rule.'''
    if not rule.conditions or not isinstance(rule.conditions, list):
        logger.warning(f"Rule {rule.name} (ID: {rule.id}) has no conditions or conditions are malformed.")
        return False

    for condition in rule.conditions:  # conditions is a list of dicts
        field_name = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')

        if not field_name or not operator:
            logger.warning(f"Skipping malformed condition in Rule {rule.name}: {condition}")
            continue  # Or treat as failure for the rule? For now, skip malformed condition.

        if not hasattr(staged_tx, field_name):
            logger.warning(f'Rule {rule.name} references invalid field \'{field_name}\' on StagedBankTransaction.')
            return False

        transaction_value = getattr(staged_tx, field_name)

        if not evaluate_condition(transaction_value, operator, value):
            return False  # One condition failed, rule does not match
    return True  # All conditions passed


def apply_rule_actions(staged_tx: StagedBankTransaction, rule: ReconciliationRule, user):
    '''Applies the actions of a matched rule to a staged transaction.'''
    organization = staged_tx.organization
    if not rule.actions or not isinstance(rule.actions, list):
        logger.warning(f"Rule {rule.name} (ID: {rule.id}) has no actions or actions are malformed.")
        return

    for action_def in rule.actions:
        action_type = action_def.get('action_type')

        if action_type == 'categorize':
            account_id = action_def.get('account_id')
            try:
                target_account = Account.objects.get(id=account_id, organization=organization)
                logger.info(f'Rule action for TX {staged_tx.id}: Categorize to account {target_account.name} based on rule {rule.name}')
                staged_tx.reconciliation_status = StagedBankTransaction.RECON_RULE_APPLIED
                staged_tx.applied_rule = rule
                # Placeholder for creating actual Transaction and JournalEntry
                # This part is complex and involves significant accounting logic:
                # 1. Determine the other side of the entry (e.g., a bank account linked to PlaidItem)
                # 2. Create a Transaction
                # 3. Create JournalEntry for debit and credit
                # For example:
                # bank_gl_account = ...  # logic to find the GL account representing the bank account of staged_tx
                # if staged_tx.amount < 0:  # Expense or Asset use
                #    debit_account, credit_account = target_account, bank_gl_account
                # else:  # Income or Liability increase
                #    debit_account, credit_account = bank_gl_account, target_account
                # ledger_tx = Transaction.objects.create(organization=organization, date=staged_tx.date, description=f"Auto-created by rule: {rule.name} for bank tx: {staged_tx.name}", created_by=user)
                # JournalEntry.objects.create(transaction=ledger_tx, account=debit_account, debit_amount=abs(staged_tx.amount))
                # JournalEntry.objects.create(transaction=ledger_tx, account=credit_account, credit_amount=abs(staged_tx.amount))
                # staged_tx.linked_transaction = ledger_tx
                staged_tx.save()

            except Account.DoesNotExist:
                logger.error(f'Account ID {account_id} in rule {rule.name} not found for org {organization.name}.')

        # Add other action_types: 'match_to_vendor', 'set_status', etc.
    logger.info(f'Actions from rule \'{rule.name}\' processed for staged transaction {staged_tx.id}')


def run_reconciliation_rules_for_organization(organization: Organization, user):
    '''Runs all active reconciliation rules for an organization on unmatched transactions.'''
    rules = ReconciliationRule.objects.filter(organization=organization, is_active=True).order_by('priority')
    # Process only a subset to avoid long transactions, or use background tasks for full processing
    unmatched_transactions = StagedBankTransaction.objects.filter(
        organization=organization,
        reconciliation_status=StagedBankTransaction.RECON_UNMATCHED
    )[:100]  # Example: Limit to 100 per run to avoid timeouts in web requests

    applied_count = 0
    for tx in unmatched_transactions:
        for rule in rules:
            if check_rule_conditions(tx, rule):
                apply_rule_actions(tx, rule, user)
                applied_count += 1
                break  # Move to next transaction once a rule has been applied

    logger.info(f'{applied_count} rules applied for organization {organization.name}.')
    return applied_count


def find_suggested_matches(staged_tx: StagedBankTransaction, threshold_days=7, amount_tolerance_percent=1.0):
    '''Suggests potential matches from existing LedgerPro Transactions.'''
    # This is a placeholder and needs significant refinement.
    # Matching criteria:
    # - Date proximity
    # - Amount similarity (absolute or percentage)
    # - Description similarity (e.g., using text matching algorithms if needed)
    # - Avoiding matching already matched transactions

    suggestions = []
    # Example:
    # date_from = staged_tx.date - timedelta(days=threshold_days)
    # date_to = staged_tx.date + timedelta(days=threshold_days)
    # amount_abs = abs(staged_tx.amount)
    # amount_lower_bound = amount_abs * Decimal(str(1 - (amount_tolerance_percent / 100.0)))
    # amount_upper_bound = amount_abs * Decimal(str(1 + (amount_tolerance_percent / 100.0)))

    # potential_gl_txs = Transaction.objects.filter(
    #    organization=staged_tx.organization,
    #    date__range=[date_from, date_to],
    #    # This query is tricky because GL transactions store debits/credits in JournalEntry.
    #    # We need to check if any JE total matches the bank transaction amount.
    #    # This might require querying JournalEntry sums grouped by Transaction.
    #    # Or, if Transaction model stores a total_amount (which it doesn't currently by default for GL)
    # ).exclude(matched_bank_transactions__isnull=False) # Exclude already matched GL transactions

    # For each potential_gl_tx:
    #   Calculate a match_score based on date difference, amount difference, description similarity.
    #   If score > a certain threshold, add to suggestions.

    # Example dummy suggestion:
    # suggestions.append({
    #    'ledger_pro_transaction_id': 'some_uuid',
    #    'date': 'YYYY-MM-DD',
    #    'description': 'Example GL Transaction',
    #    'amount': staged_tx.amount, # Or the amount from GL transaction
    #    'match_score': 0.85, # Arbitrary score
    #    'reason': 'Close date and amount'
    # })

    logger.info(f'Found {len(suggestions)} potential matches for staged transaction {staged_tx.id}')
    return suggestions
