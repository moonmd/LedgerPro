import logging
from .models import Employee, PayRun, Payslip, PayslipDeduction, DeductionType, Organization
from decimal import Decimal
from django.utils import timezone # Added for timezone.now()

logger = logging.getLogger(__name__)

def calculate_gross_pay(employee: Employee, pay_period_start_date, pay_period_end_date, hours_worked=None):
    '''Calculates gross pay for an employee for a pay period.'''
    # This is highly simplified. Real calculation involves pay frequency, proration for new hires/terms.
    if employee.pay_type == Employee.SALARY:
        # Assuming salary is annual. Prorate for pay period.
        # This needs pay_frequency on Employee model. For now, assume bi-weekly (26 pay periods).
        # This is a major simplification.
        num_pay_periods_in_year = 26 # Placeholder
        gross = employee.pay_rate / Decimal(str(num_pay_periods_in_year)) # Ensure Decimal division
        return Decimal(gross).quantize(Decimal('0.01'))
    elif employee.pay_type == Employee.HOURLY:
        if hours_worked is None:
            # Default to 0 if not provided, or raise error based on policy
            logger.warning(f"Hours worked not provided for hourly employee {employee.id}. Assuming 0 hours.")
            hours_worked = Decimal('0.00')
        else:
            hours_worked = Decimal(str(hours_worked))

        gross = employee.pay_rate * hours_worked
        return Decimal(gross).quantize(Decimal('0.01'))
    return Decimal('0.00')


def process_pay_run(pay_run: PayRun, employee_inputs: list, user):
    '''
    Processes a pay run: calculates gross pay, deductions, net pay for each employee, and creates Payslips.
    employee_inputs: list of dicts, e.g.,
        [{'employee_id': uuid, 'hours_worked': 40, 'manual_deductions': [{'deduction_type_id': uuid_str, 'amount': '50.00'}] }]
    '''
    if pay_run.status not in [PayRun.DRAFT, PayRun.PROCESSING]: # Allow reprocessing if stuck in processing
        raise ValueError(f'PayRun must be in DRAFT or PROCESSING status to process. Current status: {pay_run.status}')

    initial_status = pay_run.status
    pay_run.status = PayRun.PROCESSING
    pay_run.save(update_fields=['status'])

    all_payslips_created_successfully = True # Track overall success
    try:
        for emp_input in employee_inputs:
            employee_id = emp_input.get('employee_id')
            if not employee_id:
                logger.warning(f"Skipping employee input due to missing 'employee_id': {emp_input}")
                all_payslips_created_successfully = False
                continue
            try:
                employee = Employee.objects.get(id=employee_id, organization=pay_run.organization, is_active=True)
            except Employee.DoesNotExist:
                logger.warning(f'Active employee with ID {employee_id} not found in organization {pay_run.organization.name}. Skipping.')
                all_payslips_created_successfully = False
                continue

            hours = emp_input.get('hours_worked') # Can be None
            gross_pay = calculate_gross_pay(employee, pay_run.pay_period_start_date, pay_run.pay_period_end_date, hours)

            total_deductions = Decimal('0.00')
            manual_deductions_data = emp_input.get('manual_deductions', [])

            # Create or update Payslip
            payslip, created = Payslip.objects.update_or_create(
                pay_run=pay_run,
                employee=employee,
                defaults={
                    'gross_pay': gross_pay,
                    'notes': f'Hours: {hours}' if hours else payslip.notes if not created else ''
                }
            )

            # Clear existing deductions for this payslip if reprocessing
            if not created:
                payslip.deductions_applied.all().delete()

            for ded_input in manual_deductions_data:
                ded_type_id = ded_input.get('deduction_type_id')
                ded_amount_str = ded_input.get('amount')
                if not ded_type_id or ded_amount_str is None:
                    logger.warning(f"Malformed deduction input {ded_input} for {employee}. Skipping.")
                    all_payslips_created_successfully = False
                    continue
                try:
                    ded_type = DeductionType.objects.get(id=ded_type_id, organization=pay_run.organization, is_active=True)
                    ded_amount = Decimal(str(ded_amount_str)).quantize(Decimal('0.01'))

                    if ded_amount < Decimal('0.00'):
                        logger.warning(f"Negative deduction amount {ded_amount} for {ded_type.name} not allowed for {employee}. Skipping.")
                        all_payslips_created_successfully = False
                        continue

                    PayslipDeduction.objects.create(
                        payslip=payslip,
                        deduction_type=ded_type,
                        amount=ded_amount
                    )
                    total_deductions += ded_amount
                except DeductionType.DoesNotExist:
                    logger.warning(f'Active deduction type ID {ded_type_id} not found. Skipping deduction for {employee}.')
                    all_payslips_created_successfully = False
                except Exception as e_ded: # Catch other errors like invalid decimal amount
                    logger.warning(f'Error processing deduction {ded_input} for {employee}: {e_ded}. Skipping.')
                    all_payslips_created_successfully = False


            payslip.total_deductions = total_deductions
            payslip.net_pay = gross_pay - total_deductions # Taxes are ignored for MVP
            payslip.save()

        if all_payslips_created_successfully:
            pay_run.status = PayRun.COMPLETED
        else:
            pay_run.status = PayRun.DRAFT # Revert to DRAFT if any issue, or use a specific error status
            logger.warning(f'PayRun {pay_run.id} processing had issues. Reverted to DRAFT. Check logs.')
            # Optionally, add a note to pay_run.notes about partial failure

        pay_run.processed_by = user
        pay_run.processed_at = timezone.now()
        pay_run.save()
        logger.info(f'PayRun {pay_run.id} processing finished. Status: {pay_run.status}')
        return pay_run

    except Exception as e:
        # Revert status if it was changed from DRAFT initially
        if initial_status == PayRun.DRAFT:
             pay_run.status = PayRun.DRAFT
        pay_run.notes = f'{pay_run.notes or ""} Processing failed: {str(e)}'.strip()
        pay_run.save()
        logger.error(f'Major error processing PayRun {pay_run.id}: {e}')
        raise
