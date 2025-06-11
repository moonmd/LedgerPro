from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserRegistrationView, UserLoginView, UserDetailView, RoleListView, RoleDetailView,
    AccountViewSet, AccountDetailView,
    TransactionViewSet, TransactionDetailView,
    AuditLogListView,
    CustomerViewSet, CustomerDetailView,
    InvoiceViewSet, InvoiceDetailView,
    VendorViewSet, VendorDetailView,
    PlaidCreateLinkTokenView, PlaidExchangePublicTokenView, PlaidFetchTransactionsView,
    StagedBankTransactionListView, ManualBankStatementImportView,
    ReconciliationRuleViewSet, ReconciliationRuleDetailView, ApplyReconciliationRulesView,
    StagedBankTransactionDetailView,
    ProfitAndLossView, BalanceSheetView,
    InvoiceSendEmailView, # Added for send email action
    # Payroll Views
    EmployeeViewSet, DeductionTypeViewSet, PayRunViewSet, PayslipListView, PayslipDetailView
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'deduction-types', DeductionTypeViewSet, basename='deduction-type')
router.register(r'payruns', PayRunViewSet, basename='payrun')
# Note: Some existing views like AccountViewSet, CustomerViewSet etc. are ListCreateAPIView,
# not full ModelViewSets, so they are not added to the router here.
# If they were ModelViewSets, they could be:
# router.register(r'accounts', AccountViewSet, basename='account')
# router.register(r'customers', CustomerViewSet, basename='customer')
# router.register(r'vendors', VendorViewSet, basename='vendor')
# router.register(r'reconciliation-rules', ReconciliationRuleViewSet, basename='reconciliationrule')


urlpatterns = [
    # Existing non-router paths...
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', UserLoginView.as_view(), name='user-login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', UserDetailView.as_view(), name='user-detail'),
    path('roles/', RoleListView.as_view(), name='role-list'),
    path('roles/<int:pk>/', RoleDetailView.as_view(), name='role-detail'),

    # Assuming these remain as separate ListCreate and RetrieveUpdateDestroy views for now
    path('accounts/', AccountViewSet.as_view(), name='account-list-create'),
    path('accounts/<uuid:pk>/', AccountDetailView.as_view(), name='account-detail'),
    path('transactions/', TransactionViewSet.as_view(), name='transaction-list-create'),
    path('transactions/<uuid:pk>/', TransactionDetailView.as_view(), name='transaction-detail'),
    path('auditlogs/', AuditLogListView.as_view(), name='auditlog-list'),
    path('customers/', CustomerViewSet.as_view(), name='customer-list-create'),
    path('customers/<uuid:pk>/', CustomerDetailView.as_view(), name='customer-detail'),
    path('invoices/', InvoiceViewSet.as_view(), name='invoice-list-create'),
    path('invoices/<uuid:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'), # Handles GET, PUT, DELETE for InvoiceDetailView
    path('invoices/<uuid:pk>/send-email/', InvoiceSendEmailView.as_view(), name='invoice-send-email'), # Corrected to use InvoiceSendEmailView
    path('vendors/', VendorViewSet.as_view(), name='vendor-list-create'),
    path('vendors/<uuid:pk>/', VendorDetailView.as_view(), name='vendor-detail'),

    path('plaid/create-link-token/', PlaidCreateLinkTokenView.as_view(), name='plaid-create-link-token'),
    path('plaid/exchange-public-token/', PlaidExchangePublicTokenView.as_view(), name='plaid-exchange-public-token'),
    path('plaid/fetch-transactions/', PlaidFetchTransactionsView.as_view(), name='plaid-fetch-transactions'),

    path('bank/staged-transactions/', StagedBankTransactionListView.as_view(), name='staged-bank-transaction-list'),
    path('bank/staged-transactions/<uuid:pk>/', StagedBankTransactionDetailView.as_view(), name='staged-bank-transaction-detail'),
    path('bank/staged-transactions/<uuid:pk>/suggest-matches/', StagedBankTransactionDetailView.as_view({'get': 'suggest_matches'}), name='staged-bank-transaction-suggest-matches'),
    path('bank/staged-transactions/<uuid:pk>/match-to-transaction/', StagedBankTransactionDetailView.as_view({'post': 'match_to_transaction'}), name='staged-bank-transaction-match'),
    path('bank/staged-transactions/<uuid:pk>/create-ledger-transaction/', StagedBankTransactionDetailView.as_view({'post': 'create_ledger_transaction'}), name='staged-bank-transaction-create-ledger'),
    path('bank/manual-import/', ManualBankStatementImportView.as_view(), name='manual-bank-statement-import'),

    path('bank/reconciliation-rules/', ReconciliationRuleViewSet.as_view(), name='recon-rule-list-create'), # Assuming ListCreateAPIView
    path('bank/reconciliation-rules/<uuid:pk>/', ReconciliationRuleDetailView.as_view(), name='recon-rule-detail'), # Assuming RetrieveUpdateDestroyAPIView
    path('bank/apply-reconciliation-rules/', ApplyReconciliationRulesView.as_view(), name='apply-recon-rules'),

    path('reports/profit-and-loss/', ProfitAndLossView.as_view(), name='report-profit-and-loss'),
    path('reports/balance-sheet/', BalanceSheetView.as_view(), name='report-balance-sheet'),

    # Payroll specific List/Retrieve (not part of router if not full ModelViewSet for all actions)
    path('payslips/', PayslipListView.as_view(), name='payslip-list'),
    path('payslips/<uuid:pk>/', PayslipDetailView.as_view(), name='payslip-detail'),

    # Include router paths for ViewSets
    path('', include(router.urls)), # This should typically be last or prefixed e.g. path('api/v1/', include(router.urls))
]
