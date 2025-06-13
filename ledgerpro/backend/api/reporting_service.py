import logging
from .models import Account, Organization  # Removed unused Transaction, JournalEntry here for now
from decimal import Decimal
from datetime import date  # Added timedelta, Sum removed as unused

logger = logging.getLogger(__name__)


def get_profit_and_loss_data(organization: Organization, date_from: date, date_to: date):
    '''
    Generates data for a Profit & Loss statement for a given organization and date range.

    Args:
        organization (Organization): The organization for which to generate the report.
        date_from (date): The start date of the reporting period.
        date_to (date): The end date of the reporting period.

    Returns:
        dict: A dictionary containing the P&L report data.

    Raises:
        ValueError: If date_from or date_to are not provided.
    '''
    if not (date_from and date_to):
        logger.error(f"P&L report generation failed for org {organization.id}: date_from or date_to not provided.")
        raise ValueError('Both date_from and date_to are required for P&L.')

    logger.info(f"Generating P&L report for organization '{organization.name}' from {date_from} to {date_to}.")

    revenue_accounts = Account.objects.filter(organization=organization, type=Account.REVENUE, is_active=True)
    expense_accounts = Account.objects.filter(organization=organization, type=Account.EXPENSE, is_active=True)

    total_revenue = Decimal('0.00')
    revenues_breakdown = []
    for acc in revenue_accounts:
        # Using the new get_period_activity method if available and confirmed working,
        # otherwise using the direct query logic as fallback.
        # Assuming get_period_activity is now part of Account model.
        period_activity = acc.get_period_activity(date_from, date_to)
        if period_activity != Decimal('0.00'):  # Only include accounts with activity
            revenues_breakdown.append({'account_name': acc.name, 'amount': period_activity})
        total_revenue += period_activity

    total_expenses = Decimal('0.00')
    expenses_breakdown = []
    for acc in expense_accounts:
        period_activity = acc.get_period_activity(date_from, date_to)
        if period_activity != Decimal('0.00'):
            expenses_breakdown.append({'account_name': acc.name, 'amount': period_activity})
        total_expenses += period_activity

    net_income = total_revenue - total_expenses

    return {
        'report_type': 'Profit and Loss',
        'organization_name': organization.name,
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'revenues': {
            'total': total_revenue,
            'breakdown': revenues_breakdown,
        },
        'expenses': {
            'total': total_expenses,
            'breakdown': expenses_breakdown,
        },
        'net_income': net_income,
    }


def get_balance_sheet_data(organization: Organization, as_of_date: date):
    '''Generates data for Balance Sheet.'''
    if not as_of_date:
        raise ValueError('as_of_date is required for Balance Sheet.')

    asset_accounts = Account.objects.filter(organization=organization, type=Account.ASSET, is_active=True)
    liability_accounts = Account.objects.filter(organization=organization, type=Account.LIABILITY, is_active=True)
    equity_accounts = Account.objects.filter(organization=organization, type=Account.EQUITY, is_active=True)

    total_assets = Decimal('0.00')
    assets_breakdown = []
    for acc in asset_accounts:
        balance = acc.get_balance(date_to=as_of_date)
        if balance != Decimal('0.00'):
            assets_breakdown.append({'account_name': acc.name, 'balance': balance})
        total_assets += balance

    total_liabilities = Decimal('0.00')
    liabilities_breakdown = []
    for acc in liability_accounts:
        balance = acc.get_balance(date_to=as_of_date)
        if balance != Decimal('0.00'):
            liabilities_breakdown.append({'account_name': acc.name, 'balance': balance})
        total_liabilities += balance

    # Calculate Retained Earnings / Current Year Net Income component for Equity
    # This is a simplified approach. True retained earnings is cumulative from prior years.
    # Here, we calculate net income from the start of the organization's "financial history" or a reasonable start date.
    # For simplicity, let's assume the "start of time" for P&L calculation for retained earnings is the earliest transaction date
    # or the organization's creation date if no transactions. This is still an approximation.

    # A common approach for Balance Sheet's equity section:
    # 1. Sum balances of explicit equity accounts (e.g., Common Stock, Paid-in Capital).
    # 2. Calculate historical Retained Earnings (usually a single account updated at year-end close).
    # 3. Calculate Current Year's Net Income (not yet closed to Retained Earnings).

    # Simplified approach for MVP:
    # Sum explicit equity accounts.
    # Calculate current year's net income and add it to equity.

    total_explicit_equity = Decimal('0.00')
    equity_breakdown = []
    for acc in equity_accounts:
        balance = acc.get_balance(date_to=as_of_date)
        if balance != Decimal('0.00'):
            equity_breakdown.append({'account_name': acc.name, 'balance': balance})
        total_explicit_equity += balance

    # Calculate Current Year Net Income (assuming calendar year for simplicity)
    current_year_start = date(as_of_date.year, 1, 1)
    current_year_net_income = Decimal('0.00')
    if as_of_date >= current_year_start:
        pnl_for_current_year_equity = get_profit_and_loss_data(organization, current_year_start, as_of_date)
        current_year_net_income = pnl_for_current_year_equity['net_income']

    # Add calculated current year net income to equity breakdown
    if current_year_net_income != Decimal('0.00') or not any(e['account_name'] == 'Current Year Net Income (Calculated)' for e in equity_breakdown):
        equity_breakdown.append({'account_name': 'Current Year Net Income (Calculated)', 'balance': current_year_net_income})

    total_equity_calculated = total_explicit_equity + current_year_net_income

    verification_difference = total_assets - (total_liabilities + total_equity_calculated)
    if abs(verification_difference) > Decimal('0.01'):  # Allow for small rounding differences
        logger.warning(
            f'Balance Sheet for {organization.name} as of {as_of_date} may not balance: '
            f'Assets ({total_assets}) != Liabilities ({total_liabilities}) + Equity ({total_equity_calculated}). '
            f'Difference: {verification_difference}'
        )

    return {
        'report_type': 'Balance Sheet',
        'organization_name': organization.name,
        'as_of_date': as_of_date.isoformat(),
        'assets': {
            'total': total_assets,
            'breakdown': assets_breakdown,
        },
        'liabilities': {
            'total': total_liabilities,
            'breakdown': liabilities_breakdown,
        },
        'equity': {
            'total': total_equity_calculated,
            'breakdown': equity_breakdown,
        },
        'verification': {
            'assets_equals_liabilities_plus_equity': abs(verification_difference) <= Decimal('0.01'),  # Check with tolerance
            'difference': verification_difference
        }
    }
