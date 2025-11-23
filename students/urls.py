from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.home, name='home'),
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/bulk-import/', views.student_bulk_import, name='student_bulk_import'),
    path('students/upgrade/', views.student_upgrade, name='student_upgrade'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('hostel-movements/', views.hostel_movement_list, name='hostel_movement_list'),
    path('hostel-movements/create/', views.hostel_movement_create, name='hostel_movement_create'),
    path('hostel-movements/<int:pk>/update/', views.hostel_movement_update, name='hostel_movement_update'),
    path('exam-types/', views.exam_type_list, name='exam_type_list'),
    path('exam-types/create/', views.exam_type_create, name='exam_type_create'),
    path('exam-types/<int:pk>/update/', views.exam_type_update, name='exam_type_update'),
    path('exam-types/<int:pk>/delete/', views.exam_type_delete, name='exam_type_delete'),
    path('marks/entry/', views.mark_entry, name='mark_entry'),
    path('marks/list/', views.mark_entry_list, name='mark_entry_list'),
    path('progress-report/', views.progress_report, name='progress_report'),
    path('progress-report/<int:pk>/', views.progress_report_detail, name='progress_report_detail'),
]

