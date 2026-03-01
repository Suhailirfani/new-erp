from django.urls import path
from . import views

app_name = 'fees'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('student/<int:student_id>/', views.student_fees, name='student_fees'),
    path('collect/<int:student_id>/', views.collect_payment, name='collect_payment'),
    path('receipt/<int:income_id>/', views.download_receipt, name='download_receipt'),
    
    # Income & Expense Routes
    path('income/add/', views.add_income, name='add_income'),
    path('expense/add/', views.add_expense, name='add_expense'),
    path('api/student-fees/<int:student_id>/', views.get_student_fees, name='api_student_fees'),
    path('api/students-by-grade/', views.get_students_by_grade, name='api_students_by_grade'),
    
    # Bulk actions
    path('setup/assign-admission-fees/', views.assign_bulk_admission_fees, name='assign_bulk_admission_fees'),
    
    # Fee Setup Management
    path('setup/', views.fee_setup_dashboard, name='fee_setup_dashboard'),
    path('setup/category/add/', views.fee_category_create, name='fee_category_create'),
    path('setup/category/<int:pk>/edit/', views.fee_category_update, name='fee_category_update'),
    path('setup/category/<int:pk>/delete/', views.fee_category_delete, name='fee_category_delete'),
    path('setup/item/add/', views.fee_item_create, name='fee_item_create'),
    path('setup/item/<int:pk>/edit/', views.fee_item_update, name='fee_item_update'),
    path('setup/item/<int:pk>/delete/', views.fee_item_delete, name='fee_item_delete'),
]
