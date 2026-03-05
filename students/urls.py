from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.home, name='home'),
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/bulk-import/', views.student_bulk_import, name='student_bulk_import'),
    path('students/bulk-import/template/', views.student_bulk_import_template, name='student_bulk_import_template'),
    path('students/upgrade/', views.student_upgrade, name='student_upgrade'),
    path('students/graduate/', views.student_graduate, name='student_graduate'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/mark/<str:grade>/<int:division_id>/', views.mark_attendance_class, name='mark_attendance_class'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('hostel-movements/', views.hostel_movement_list, name='hostel_movement_list'),
    path('hostel-movements/create/', views.hostel_movement_create, name='hostel_movement_create'),
    path('hostel-movements/<int:pk>/update/', views.hostel_movement_update, name='hostel_movement_update'),
    path('exam-types/', views.exam_type_list, name='exam_type_list'),
    path('exam-types/create/', views.exam_type_create, name='exam_type_create'),
    path('exam-types/<int:pk>/update/', views.exam_type_update, name='exam_type_update'),
    path('exam-types/<int:pk>/delete/', views.exam_type_delete, name='exam_type_delete'),
    path('marks/entry/', views.mark_entry_step1, name='mark_entry'),
    path('marks/entry/<int:exam_type_id>/', views.mark_entry_step2, name='mark_entry_step2'),
    path('marks/entry/<int:exam_type_id>/class/', views.mark_entry_step3, name='mark_entry_step3'),
    path('marks/list/', views.mark_entry_list, name='mark_entry_list'),
    path('marks/list/data/', views.mark_entry_classwise_data, name='mark_list_data'),
    path('progress-report/', views.progress_report, name='progress_report'),
    path('progress-report/<int:pk>/', views.progress_report_detail, name='progress_report_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('attendance/analytics/', views.attendance_analytics, name='attendance_analytics'),
    path('performance-analysis/', views.performance_analysis, name='performance_analysis'),
    path('attendance/class/<str:grade>/<int:division_id>/', views.attendance_class_detail, name='attendance_class_detail'),
    path('attendance/student/<int:student_id>/', views.attendance_student_detail, name='attendance_student_detail'),
    path('progress-reports/bulk-pdf/', views.bulk_progress_report_pdf, name='bulk_progress_report_pdf'),
    path('attendance/update-tracking/', views.attendance_update_tracking, name='attendance_update_tracking'),
    
    # Academic Year Management
    path('academic-years/', views.academic_year_list, name='academic_year_list'),
    path('academic-years/create/', views.academic_year_create, name='academic_year_create'),
    path('academic-years/<int:pk>/update/', views.academic_year_update, name='academic_year_update'),
    
    # Subject Management
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/update/', views.subject_update, name='subject_update'),
    
    # Enquiry Management
    path('enquiries/', views.enquiry_list_view, name='enquiry_list'),
    path('enquiries/new/', views.enquiry_create_view, name='enquiry_create'),
    path('enquiries/<int:pk>/token/', views.enquiry_generate_token_view, name='enquiry_generate_token'),
    path('enquiries/<int:pk>/enroll/', views.enquiry_enroll_view, name='enquiry_enroll'),
    path('enquiries/<int:pk>/token/print/', views.enquiry_token_print_view, name='enquiry_token_print'),
]
