import re

view_roles = {
    'home': ['@login_required'],
    'student_list': ['@login_required'],
    
    'student_create': ["@role_required(['admin', 'teacher', 'accountant'])"],
    'student_bulk_import': ["@role_required(['admin', 'accountant'])"],
    'student_bulk_import_template': ["@role_required(['admin', 'accountant'])"],
    'student_upgrade': ["@role_required(['admin', 'accountant'])"],
    'student_graduate': ["@role_required(['admin', 'accountant'])"],
    
    'student_edit': ["@student_own_data_required"],
    'student_delete': ["@role_required(['admin'])"],
    
    'mark_attendance': ["@role_required(['admin', 'teacher'])"],
    'mark_attendance_class': ["@role_required(['admin', 'teacher'])"],
    'attendance_list': ["@role_required(['admin', 'teacher'])"],
    'attendance_analytics': ["@role_required(['admin', 'teacher'])"],
    'attendance_class_detail': ["@role_required(['admin', 'teacher'])"],
    'attendance_student_detail': ["@role_required(['admin', 'teacher'])"],
    'attendance_update_tracking': ["@role_required(['admin', 'teacher'])"],
    
    'hostel_movement_list': ["@role_required(['admin', 'ntstaff'])"],
    'hostel_movement_create': ["@role_required(['admin', 'ntstaff'])"],
    'hostel_movement_update': ["@role_required(['admin', 'ntstaff'])"],
    
    'exam_type_list': ["@role_required(['admin', 'teacher'])"],
    'exam_type_create': ["@role_required(['admin', 'teacher'])"],
    'exam_type_update': ["@role_required(['admin', 'teacher'])"],
    'exam_type_delete': ["@role_required(['admin', 'teacher'])"],
    
    'mark_entry_step1': ["@role_required(['admin', 'teacher'])"],
    'mark_entry_step2': ["@role_required(['admin', 'teacher'])"],
    'mark_entry_step3': ["@role_required(['admin', 'teacher'])"],
    'mark_entry_list': ["@role_required(['admin', 'teacher'])"],
    'mark_entry_classwise_data': ["@role_required(['admin', 'teacher'])"],
    
    'progress_report': ["@role_required(['admin', 'teacher'])"],
    'progress_report_detail': ["@role_required(['admin', 'teacher'])"],
    'bulk_progress_report_pdf': ["@role_required(['admin', 'teacher'])"],
    'performance_analysis': ["@role_required(['admin', 'teacher'])"],
    
    'section_list': ["@role_required(['admin'])"],
    'section_create': ["@role_required(['admin'])"],
    'section_update': ["@role_required(['admin'])"],
    'section_delete': ["@role_required(['admin'])"],
    
    'academic_year_list': ["@role_required(['admin'])"],
    'academic_year_create': ["@role_required(['admin'])"],
    'academic_year_update': ["@role_required(['admin'])"],
    
    'subject_list': ["@role_required(['admin'])"],
    'subject_create': ["@role_required(['admin'])"],
    'subject_update': ["@role_required(['admin'])"],
    'subject_delete': ["@role_required(['admin'])"],
    
    'grade_list': ["@role_required(['admin'])"],
    'grade_create': ["@role_required(['admin'])"],
    'grade_update': ["@role_required(['admin'])"],
    'grade_delete': ["@role_required(['admin'])"],
    
    'division_list': ["@role_required(['admin'])"],
    'division_create': ["@role_required(['admin'])"],
    'division_update': ["@role_required(['admin'])"],
    'division_delete': ["@role_required(['admin'])"],
    
    'enquiry_list': ["@role_required(['admin', 'ntstaff', 'accountant'])"],
    'enquiry_create': ["@role_required(['admin', 'ntstaff', 'accountant'])"],
    'enquiry_update': ["@role_required(['admin', 'ntstaff', 'accountant'])"],
    'enquiry_delete': ["@role_required(['admin', 'ntstaff', 'accountant'])"],
    'enquiry_enroll': ["@role_required(['admin', 'accountant'])"],
    'enquiry_generate_token': ["@role_required(['admin', 'ntstaff', 'accountant'])"],
    'enquiry_print_token': ["@role_required(['admin', 'ntstaff', 'accountant'])"],
}

with open('students/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out_lines = []
imports_added = False

for i, line in enumerate(lines):
    if line.startswith('def '):
        match = re.match(r'^def ([a-zA-Z0-9_]+)\(', line)
        if match:
            func_name = match.group(1)
            if func_name in view_roles:
                for dec in view_roles[func_name]:
                    out_lines.append(f"{dec}\n")
    out_lines.append(line)
    
    if not imports_added and line.startswith('from django.shortcuts'):
        out_lines.append("from django.contrib.auth.decorators import login_required\n")
        out_lines.append("from .decorators import role_required, student_own_data_required\n")
        imports_added = True

with open('students/views.py', 'w', encoding='utf-8') as f:
    f.writelines(out_lines)

print("Patch complete.")
