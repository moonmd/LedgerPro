import logging
from .models import (
    Employee, PayRun, Payslip, PayslipDeduction, DeductionType, Organization,
    Account, Transaction, JournalEntry # Added Account, Transaction, JournalEntry
)
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction # For atomic operations
from .account_utils import get_or_create_default_account # Added import

logger = logging.getLogger(__name__)

# _get_or_create_payroll_account method removed, will use centralized utility

def calculate_gross_pay(employee: Employee, pay_period_start_date, pay_period_end_date, hours_worked=None):
    if employee.pay_type == Employee.SALARY:
        num_pay_periods_in_year = 26
        gross = employee.pay_rate / Decimal(str(num_pay_periods_in_year))
        return Decimal(gross).quantize(Decimal('0.01'))
    elif employee.pay_type == Employee.HOURLY:
        if hours_worked is None:
            logger.warning(f"Hours worked not provided for hourly employee {employee.id}. Assuming 0 hours for safety.")
            hours_worked = Decimal('0.00') # Default to 0 if not provided.
        else:
            hours_worked = Decimal(str(hours_worked))
        gross = employee.pay_rate * hours_worked
        return Decimal(gross).quantize(Decimal('0.01'))
    return Decimal('0.00')


@db_transaction.atomic
def process_pay_run(pay_run: PayRun, employee_inputs: list, user):
    if pay_run.status not in [PayRun.DRAFT, PayRun.PROCESSING]: # Allow reprocessing from PROCESSING
        raise ValueError(f'PayRun must be in DRAFT or PROCESSING status to process. Current status: {pay_run.status}')

    initial_status = pay_run.status
    pay_run.status = PayRun.PROCESSING
    pay_run.save(update_fields=['status'])

    total_run_gross_pay = Decimal('0.00')
    total_run_net_pay = Decimal('0.00')
    aggregated_deductions = {}
    processed_payslips_for_gl = []

    for emp_input in employee_inputs:
        employee_id = emp_input.get('employee_id')
        if not employee_id:
            logger.warning(f"Skipping employee input due to missing 'employee_id': {emp_input}")
            continue # Or handle error more strictly
        try:
            employee = Employee.objects.get(id=employee_id, organization=pay_run.organization, is_active=True)
        except Employee.DoesNotExist:
            logger.warning(f'Active employee with ID {employee_id} not found. Skipping.')
            continue

        hours = emp_input.get('hours_worked')
        gross_pay = calculate_gross_pay(employee, pay_run.pay_period_start_date, pay_run.pay_period_end_date, hours)
        current_payslip_total_deductions = Decimal('0.00')

        payslip, created = Payslip.objects.update_or_create(
            pay_run=pay_run, employee=employee,
            defaults={
                'gross_pay': gross_pay,
                'notes': f'Hours: {hours}' if hours is not None else (payslip.notes if not created else '')
            }
        )
        if not created: # Clear previous deductions if reprocessing
            payslip.deductions_applied.all().delete()

        manual_deductions_data = emp_input.get('manual_deductions', [])
        for ded_input in manual_deductions_data:
            ded_type_id = ded_input.get('deduction_type_id')
            ded_amount_str = ded_input.get('amount')
            if not ded_type_id or ded_amount_str is None:
                logger.warning(f"Malformed deduction input {ded_input} for {employee}. Skipping.")
                continue
            try:
                ded_type = DeductionType.objects.get(id=ded_type_id, organization=pay_run.organization, is_active=True)
                ded_amount = Decimal(str(ded_amount_str)).quantize(Decimal('0.01'))
                if ded_amount < Decimal('0.00'):
                     logger.warning(f"Negative deduction amount {ded_amount} for {ded_type.name} not allowed. Skipping.")
                     continue
                PayslipDeduction.objects.create(payslip=payslip, deduction_type=ded_type, amount=ded_amount)
                current_payslip_total_deductions += ded_amount
                agg_key = ded_type.name
                aggregated_deductions[agg_key] = aggregated_deductions.get(agg_key, Decimal('0.00')) + ded_amount
            except DeductionType.DoesNotExist:
                logger.warning(f'Deduction type ID {ded_type_id} not found. Skipping for {employee}.')
            except Exception as e_ded:
                logger.warning(f'Error processing deduction {ded_input} for {employee}: {e_ded}. Skipping.')

        payslip.total_deductions = current_payslip_total_deductions
        payslip.net_pay = gross_pay - current_payslip_total_deductions
        payslip.save()
        processed_payslips_for_gl.append(payslip) # Add to list for GL summary

        total_run_gross_pay += gross_pay
        total_run_net_pay += payslip.net_pay

    if not processed_payslips_for_gl: # If no employees were processed successfully
        pay_run.status = initial_status # Revert to original status (e.g. DRAFT)
        pay_run.notes = f'{pay_run.notes or ""}Processing failed: No valid employee data processed.'.strip()
        pay_run.save()
        logger.warning(f'PayRun {pay_run.id} processing resulted in no payslips. Status reverted to {initial_status}.')
        raise ValueError('No employee data processed for this pay run.')

    organization = pay_run.organization
    payroll_expense_acc = get_or_create_default_account(organization, Account.EXPENSE, 'Payroll Expense', 'Payroll Expenses (Default)', 'payroll expense')
    wages_payable_acc = get_or_create_default_account(organization, Account.LIABILITY, 'Wages Payable', 'Wages Payable (Default)', 'wages payable')
    generic_deductions_payable_acc = get_or_create_default_account(organization, Account.LIABILITY, 'Deductions Payable', 'Deductions Payable (Default)', 'deductions payable')

    gl_transaction = Transaction.objects.create(
        organization=organization, date=pay_run.payment_date,
        description=f'Payroll for period {pay_run.pay_period_start_date} to {pay_run.pay_period_end_date}',
        created_by=user
    )
    JournalEntry.objects.create(
        transaction=gl_transaction, account=payroll_expense_acc, debit_amount=total_run_gross_pay,
        description='Total gross payroll expense for pay run.'
    )
    JournalEntry.objects.create(
        transaction=gl_transaction, account=wages_payable_acc, credit_amount=total_run_net_pay,
        description='Total net wages payable to employees.'
    )
    total_aggregated_deductions_amount = sum(aggregated_deductions.values())
    if total_aggregated_deductions_amount > Decimal('0.00'):
        JournalEntry.objects.create(
            transaction=gl_transaction, account=generic_deductions_payable_acc, credit_amount=total_aggregated_deductions_amount,
            description='Total employee deductions payable.'
        )

    current_debits = sum(je.debit_amount for je in gl_transaction.journal_entries_set.all())
    current_credits = sum(je.credit_amount for je in gl_transaction.journal_entries_set.all())
    if abs(current_debits - current_credits) > Decimal('0.005'): # Tolerance for small rounding
        logger.error(f'GL Transaction for PayRun {pay_run.id} is unbalanced! Debits: {current_debits}, Credits: {current_credits}. Rolling back.')
        raise ValueError(f'Failed to create a balanced GL transaction for the pay run. Difference: {current_debits - current_credits}')

    pay_run.gl_transaction = gl_transaction
    pay_run.status = PayRun.COMPLETED
    pay_run.processed_by = user
    pay_run.processed_at = timezone.now()
    pay_run.save()

    logger.info(f'PayRun {pay_run.id} processed successfully. Status: {pay_run.status}. GL Transaction: {gl_transaction.id}')
    return pay_run
