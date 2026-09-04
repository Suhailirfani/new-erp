from django.urls import path
from . import views

app_name = 'fees'

urlpatterns = [
    # Control Panel / Dashboard
    path('', views.finance_dashboard, name='finance_dashboard'),
    path('dashboard/', views.finance_dashboard, name='dashboard'),
    path('fees-dashboard/', views.finance_dashboard, name='fees_dashboard'),
    
    # Fee Collection Counter & Student Ledger
    path('counter/', views.fee_counter, name='fee_counter'),
    path('student/<int:student_id>/', views.student_fee_detail, name='student_fees'),
    path('student/<int:student_id>/ledger/', views.student_fee_detail, name='student_fee_detail'),
    path('student/<int:student_id>/apply-reduction/', views.apply_fee_reduction_submit, name='apply_fee_reduction_submit'),
    path('student/<int:student_id>/add-adhoc/', views.add_adhoc_fee_submit, name='add_adhoc_fee_submit'),
    path('student/<int:student_id>/collect/', views.collect_payment_submit, name='collect_payment_submit'),
    path('receipt/<str:receipt_id>/', views.print_receipt, name='print_receipt'),
    path('batch-monthly-billing/', views.batch_monthly_billing, name='batch_monthly_billing'),
    
    # Office Incomes & Expenses
    path('incomes/', views.income_list, name='income_list'),
    path('incomes/add/', views.income_create, name='income_create'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/add/', views.expense_create, name='expense_create'),
    
    # Accounting Books & Reports
    path('day-book/', views.day_book, name='day_book'),
    path('ledger-book/', views.ledger_book, name='ledger_book'),
    path('reports/', views.finance_reports, name='finance_reports'),
    
    # Caution Deposits
    path('caution-deposits/', views.caution_deposits, name='caution_deposits'),
    path('caution-deposits/<int:deposit_id>/refund/', views.caution_deposit_refund_submit, name='caution_deposit_refund_submit'),
    
    # Setup & Configurations
    path('setup/', views.fee_setup, name='fee_setup'),
    path('setup/payment-settings/', views.payment_settings_update, name='payment_settings_update'),
    path('setup/bus-stops/add/', views.bus_stop_create, name='bus_stop_create'),
    path('setup/bus-stops/<int:stop_id>/edit/', views.bus_stop_update, name='bus_stop_update'),
    path('setup/bus-stops/<int:stop_id>/delete/', views.bus_stop_delete, name='bus_stop_delete'),
    path('setup/items/add/', views.fee_item_create, name='fee_item_create'),
    path('setup/items/<int:item_id>/edit/', views.fee_item_update, name='fee_item_update'),
    path('setup/items/<int:item_id>/delete/', views.fee_item_delete, name='fee_item_delete'),
]

