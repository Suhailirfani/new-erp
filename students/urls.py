from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('home/', views.home, name='home'),
    path('', views.landing_page, name='landing'),
    path('about-us/', views.about_us, name='about_us'),
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/bulk-import/', views.student_bulk_import, name='student_bulk_import'),
    path('students/bulk-import/template/', views.student_bulk_import_template, name='student_bulk_import_template'),
    path('students/upgrade/', views.student_upgrade, name='student_upgrade'),
    path('students/graduate/', views.student_graduate, name='student_graduate'),
    path('attendance/mark/<int:grade_id>/<int:division_id>/', views.mark_attendance_class, name='mark_attendance_class'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('hostel-movements/', views.hostel_movement_list, name='hostel_movement_list'),
    path('hostel-movements/create/', views.hostel_movement_create, name='hostel_movement_create'),
    path('hostel-movements/<int:pk>/update/', views.hostel_movement_update, name='hostel_movement_update'),
    path('hostel-students/', views.hostel_student_list_view, name='hostel_student_list'),
    path('hostel-students/<int:pk>/', views.hostel_student_detail_view, name='hostel_student_detail'),
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
    path('students/<int:pk>/profile/', views.student_profile, name='student_profile'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/create-user/', views.create_student_user, name='create_student_user'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('attendance/analytics/', views.attendance_analytics, name='attendance_analytics'),
    path('performance-analysis/', views.performance_analysis, name='performance_analysis'),
    path('attendance/class/<int:grade_id>/<int:division_id>/', views.attendance_class_detail, name='attendance_class_detail'),
    path('attendance/student/<int:student_id>/', views.attendance_student_detail, name='attendance_student_detail'),
    path('progress-reports/bulk-pdf/', views.bulk_progress_report_pdf, name='bulk_progress_report_pdf'),
    path('attendance/update-tracking/', views.attendance_update_tracking, name='attendance_update_tracking'),
    
    # Section Management
    path('sections/', views.section_list, name='section_list'),
    path('sections/create/', views.section_create, name='section_create'),
    path('sections/<int:pk>/update/', views.section_update, name='section_update'),
    path('sections/<int:pk>/delete/', views.section_delete, name='section_delete'),

    # Academic Year Management
    path('academic-years/', views.academic_year_list, name='academic_year_list'),
    path('academic-years/create/', views.academic_year_create, name='academic_year_create'),
    path('academic-years/<int:pk>/update/', views.academic_year_update, name='academic_year_update'),
    
    # Subject Management
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/update/', views.subject_update, name='subject_update'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    
    # Grade Management
    path('grades/', views.grade_list, name='grade_list'),
    path('grades/create/', views.grade_create, name='grade_create'),
    path('grades/<int:pk>/update/', views.grade_update, name='grade_update'),
    path('grades/<int:pk>/delete/', views.grade_delete, name='grade_delete'),
    
    # Division Management
    path('divisions/', views.division_list, name='division_list'),
    path('divisions/create/', views.division_create, name='division_create'),
    path('divisions/<int:pk>/update/', views.division_update, name='division_update'),
    path('divisions/<int:pk>/delete/', views.division_delete, name='division_delete'),
    
    # Enquiry Management
    path('enquiries/', views.enquiry_list_view, name='enquiry_list'),
    path('enquiries/print-list/', views.enquiry_print_list_view, name='enquiry_print_list'),
    path('enquiries/new/', views.enquiry_create_view, name='enquiry_create'),
    path('enquiries/success/<str:application_number>/', views.enquiry_success_view, name='enquiry_success'),
    path('enquiries/status/', views.enquiry_status_view, name='enquiry_status'),
    path('enquiries/<int:pk>/receive/', views.enquiry_mark_received, name='enquiry_mark_received'),
    path('enquiries/global-interview-date/', views.enquiry_set_global_interview_date, name='enquiry_set_global_interview_date'),
    path('enquiries/<int:pk>/token/', views.enquiry_generate_token_view, name='enquiry_generate_token'),
    path('enquiries/<int:pk>/enroll/', views.enquiry_enroll_view, name='enquiry_enroll'),
    path('enquiries/<int:pk>/token/print/', views.enquiry_token_print_view, name='enquiry_token_print'),
    path('enquiries/<int:pk>/edit/', views.enquiry_update_view, name='enquiry_edit'),
    path('enquiries/<int:pk>/delete/', views.enquiry_delete_view, name='enquiry_delete'),

    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/update/', views.user_update, name='user_update'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    # Alumni Management
    path('alumni/', views.alumni_list, name='alumni_list'),
    path('alumni/bulk-transfer/', views.alumni_bulk_transfer, name='alumni_bulk_transfer'),
    path('alumni/bulk-restore/', views.alumni_bulk_restore, name='alumni_bulk_restore'),
    path('student/<int:student_id>/transfer-alumni/', views.transfer_to_alumni, name='transfer_to_alumni'),
    path('alumni/<int:pk>/edit/', views.alumni_update, name='alumni_update'),
    path('alumni/<int:pk>/delete/', views.alumni_delete, name='alumni_delete'),

    # Job Vacancy Management
    path('careers/', views.career_page, name='career'),
    path('careers/apply/<int:job_id>/', views.job_apply, name='job_apply'),
    path('careers/success/<str:application_number>/', views.job_success, name='job_success'),
    path('dashboard/admin/vacancies/', views.job_vacancy_list_admin, name='job_vacancy_list_admin'),
    path('dashboard/admin/vacancies/add/', views.job_vacancy_create, name='job_vacancy_create'),
    path('dashboard/admin/vacancies/<int:pk>/edit/', views.job_vacancy_update, name='job_vacancy_update'),
    path('dashboard/admin/vacancies/<int:pk>/delete/', views.job_vacancy_delete, name='job_vacancy_delete'),
    path('dashboard/admin/applications/', views.job_application_list_admin, name='job_application_list_admin'),
]
