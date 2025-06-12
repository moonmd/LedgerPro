from django.contrib import admin
from .models import (
    Organization, User, Role, Membership,
    Account, Transaction, JournalEntry, AuditLog,
    Customer, Invoice, InvoiceItem, Vendor,
    PlaidItem, StagedBankTransaction, ReconciliationRule,
    Employee, PayRun, Payslip, DeductionType, PayslipDeduction # Added Payroll models
)

admin.site.register(Organization)
admin.site.register(User)
admin.site.register(Role)
admin.site.register(Membership)
admin.site.register(Account)
admin.site.register(Transaction)
admin.site.register(JournalEntry)
admin.site.register(AuditLog)
admin.site.register(Customer)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)
admin.site.register(Vendor)
admin.site.register(PlaidItem)
admin.site.register(StagedBankTransaction)
admin.site.register(ReconciliationRule)
admin.site.register(Employee)
admin.site.register(PayRun)
admin.site.register(Payslip)
admin.site.register(DeductionType)
admin.site.register(PayslipDeduction)
