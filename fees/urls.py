from django.urls import path
from . import views

app_name = 'fees'

urlpatterns = [
    path('finance-dashboard/', views.finance_dashboard, name='finance_dashboard'),
    path('fees-dashboard/', views.fees_dashboard, name='fees_dashboard'),
    path('fees-dashboard/classroom/<int:grade_id>/', views.classroom_detail, name='classroom_detail'),
    path('fees-dashboard/classroom/<int:grade_id>/<int:division_id>/', views.classroom_detail, name='classroom_detail_with_division'),
    # Redirect legacy dashboard to finance dashboard for now if needed, or just remove it
    path('dashboard/', views.finance_dashboard, name='dashboard'), # Keep legacy name for now to prevent breaks
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
    path('setup/cancel-admission-fees/', views.cancel_selective_admission_fees, name='cancel_selective_admission_fees'),
    
    # Fee Setup Management
    path('setup/bulk-course-fees/', views.bulk_course_fee_update, name='bulk_course_fee_update'),
    path('setup/generate-monthly/', views.generate_monthly_fees, name='generate_monthly_fees'),
    path('setup/', views.fee_setup_dashboard, name='fee_setup_dashboard'),
    path('setup/item/<int:item_id>/installments/', views.manage_fee_installments, name='manage_fee_installments'),
    path('setup/category/add/', views.fee_category_create, name='fee_category_create'),
    path('setup/category/<int:pk>/edit/', views.fee_category_update, name='fee_category_update'),
    path('setup/category/<int:pk>/delete/', views.fee_category_delete, name='fee_category_delete'),
    path('setup/item/add/', views.fee_item_create, name='fee_item_create'),
    path('setup/item/<int:pk>/edit/', views.fee_item_update, name='fee_item_update'),
    path('setup/item/<int:pk>/delete/', views.fee_item_delete, name='fee_item_delete'),
    
    # Fee Structure (Grade/Division variations)
    path('setup/structures/', views.fee_structure_list, name='fee_structure_list'),
    path('setup/structures/add/', views.fee_structure_create, name='fee_structure_create'),
    path('setup/structures/<int:pk>/edit/', views.fee_structure_update, name='fee_structure_update'),
    path('setup/structures/<int:pk>/delete/', views.fee_structure_delete, name='fee_structure_delete'),
]
