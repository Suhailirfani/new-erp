from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .decorators import role_required, student_own_data_required
from django.urls import reverse
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, datetime
from django.db.models import Max

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
from .models import (
    Student, Attendance, HostelMovement, Period, Activity, Division, Room,
    ExamType, Subject, MarkEntry, ProgressReport, AcademicYear, Enrollment,
    Grade, Section
)
from .forms import SectionForm, AcademicYearForm, EnquiryForm, GradeForm, DivisionForm, SubjectForm


def home(request):
    """Dashboard/Home page"""
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
        today = date.today()
        
        # Only calculate administrative statistics if the user is not a student
        if profile.role != 'student':
            # Statistics
            total_students = Student.objects.filter(is_active=True).count()
            hostel_students = Student.objects.filter(student_type='hostel', is_active=True).count()
            day_scholar_students = Student.objects.filter(student_type='day_scholar', is_active=True).count()
    
            # Today's attendance stats
            today_attendance = Attendance.objects.filter(date=today)
            today_present = today_attendance.filter(status='present').count()
            today_absent = today_attendance.filter(status='absent').count()
    
            # Pending hostel movements (not returned)
            pending_movements = HostelMovement.objects.filter(is_returned=False).count()
    
            context.update({
                'total_students': total_students,
                'hostel_students': hostel_students,
                'day_scholar_students': day_scholar_students,
                'today_present': today_present,
                'today_absent': today_absent,
                'pending_movements': pending_movements,
            })
            
        elif profile.role == 'student' and profile.student_record:
            # Student-only Portal Data
            student = profile.student_record
            active_year = AcademicYear.objects.filter(is_active=True).first()
            
            # 1. Attendance Data
            student_today_att = Attendance.objects.filter(student=student, date=today).first()
            today_status = student_today_att.status if student_today_att else 'not_marked'
            
            # Monthly attendance
            current_month = today.month
            curr_year = today.year
            monthly_att = Attendance.objects.filter(
                student=student, 
                date__year=curr_year, 
                date__month=current_month
            )
            monthly_total = monthly_att.count()
            monthly_present = monthly_att.filter(status='present').count()
            
            # Yearly attendance
            if active_year:
                yearly_att = Attendance.objects.filter(
                    student=student,
                    date__gte=active_year.start_date,
                    date__lte=active_year.end_date if active_year.end_date else today
                )
                yearly_total = yearly_att.count()
                yearly_present = yearly_att.filter(status='present').count()
            else:
                yearly_total = 0
                yearly_present = 0
                
            # 2. Results / Academics Data
            # All results in the active academic year
            exam_results = []
            if active_year:
                enrollment = Enrollment.objects.filter(student=student, academic_year=active_year).first()
                if enrollment and enrollment.grade:
                    # Fetch MarkEntry where exam_type's academic year is active_year
                    exam_results = MarkEntry.objects.filter(
                        student=student, 
                        exam_type__academic_year=active_year
                    ).select_related('exam_type', 'subject').order_by('-exam_type__start_date', 'subject__name')
            
            # 3. Hostel Movement Data
            hostel_status = None
            if student.student_type == 'hostel':
                # Check for an open 'Away' record
                open_movement = HostelMovement.objects.filter(student=student, is_returned=False).first()
                hostel_status = 'away' if open_movement else 'present'
                
            # 4. Fee Data
            student_fees = []
            fee_total_paid = 0
            fee_total_due = 0
            try:
                from fees.models import StudentFee
                fees_list = StudentFee.objects.filter(student=student)
                for fee in fees_list:
                    student_fees.append(fee)
                    fee_total_paid += fee.amount_paid
                    if fee.status != 'paid':
                        # The balance is what is still due
                        fee_total_due += fee.balance
            except ImportError:
                pass # If fees module is missing or disconnected
                
            context.update({
                'student_record': student,
                'today_status': today_status,
                'monthly_total': monthly_total,
                'monthly_present': monthly_present,
                'yearly_total': yearly_total,
                'yearly_present': yearly_present,
                'exam_results': exam_results,
                'hostel_status': hostel_status,
                'fee_total_paid': fee_total_paid,
                'fee_total_due': fee_total_due,
            })
        
    return render(request, 'students/home.html', context)


@role_required(['admin', 'teacher', 'accountant'])
def student_create(request):
    """Create a new student"""
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        grade_id = request.POST.get('grade')
        division_id = request.POST.get('division') or None
        room_id = request.POST.get('room') or None
        section_id = request.POST.get('section') or None
        student_type = request.POST.get('student_type', 'day_scholar')
        email = request.POST.get('email', '')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')
        
        form_year_id = request.POST.get('academic_year_id')
        form_year = None
        if form_year_id:
            form_year = AcademicYear.objects.filter(id=form_year_id).first()
        else:
            form_year = active_year

        # Check if student_id already exists
        if Student.objects.filter(student_id=student_id).exists():
            messages.error(request, f'Student with ID {student_id} already exists.')
        else:
            student = Student.objects.create(
                student_id=student_id,
                first_name=first_name,
                last_name=last_name,
                student_type=student_type,
                email=email,
                phone=phone,
                address=address,
            )
            
            siblings_ids = request.POST.getlist('siblings')
            if siblings_ids:
                student.siblings.set(siblings_ids)
            
            if form_year:
                Enrollment.objects.create(
                    student=student,
                    academic_year=form_year,
                    section_id=section_id if section_id else None,
                    grade_id=grade_id,
                    division_id=division_id if division_id else None,
                    room_id=room_id if room_id else None
                )
            
            messages.success(request, f'Student {student.full_name} created successfully for {form_year.name if form_year else "the selected year"}!')
            return redirect('students:student_list')

    divisions = Division.objects.all()
    rooms = Room.objects.all()
    sections = Section.objects.all().order_by('order', 'name')
    grades = Grade.objects.all().order_by('order', 'name')
    all_students = Student.objects.filter(is_active=True).order_by('first_name', 'last_name')
    context = {
        'all_students': all_students,
        'divisions': divisions,
        'rooms': rooms,
        'sections': sections,
        'grades': grades,
        'academic_years': academic_years,
        'active_year': active_year,
    }
    return render(request, 'students/student_create.html', context)


@role_required(['admin', 'accountant'])
def student_bulk_import(request):
    """Bulk import students from Excel file"""
    if not PANDAS_AVAILABLE:
        messages.error(request, 'pandas library is required for bulk import. Please install it: pip install pandas openpyxl')
        return redirect('students:student_list')

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    active_year = AcademicYear.objects.filter(is_active=True).first()

    if request.method == 'POST':
        if 'excel_file' not in request.FILES:
            messages.error(request, 'Please select an Excel file.')
            return redirect('students:student_bulk_import')

        excel_file = request.FILES['excel_file']
        
        form_year_id = request.POST.get('academic_year_id')
        form_year = None
        if form_year_id:
            form_year = AcademicYear.objects.filter(id=form_year_id).first()
        else:
            form_year = active_year
            
        if not form_year:
            messages.error(request, 'No academic year selected or active.')
            return redirect('students:student_bulk_import')

        try:
            # Read Excel file
            df = pd.read_excel(excel_file)

            # Expected columns (case-insensitive matching)
            required_columns = ['student_id', 'first_name', 'last_name', 'grade']
            optional_columns = ['division', 'room', 'student_type', 'email', 'phone', 'address', 'section']

            # Normalize column names (lowercase and strip spaces)
            df.columns = df.columns.str.lower().str.strip()

            # Check required columns
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                return redirect('students:student_bulk_import')

            # Get divisions and rooms for lookup
            divisions = {div.name.lower(): div for div in Division.objects.all()}
            rooms = {room.room_number.lower(): room for room in Room.objects.all()}

            success_count = 0
            error_count = 0
            errors = []

            # Process each row
            for index, row in df.iterrows():
                try:
                    student_id = str(row['student_id']).strip()
                    first_name = str(row['first_name']).strip()
                    last_name = str(row['last_name']).strip()
                    grade = str(row['grade']).strip()

                    # Check if student already exists
                    if Student.objects.filter(student_id=student_id).exists():
                        errors.append(f"Row {index + 2}: Student ID {student_id} already exists")
                        error_count += 1
                        continue

                    # Validate grade is not empty
                    if not grade or grade == 'nan':
                        errors.append(f"Row {index + 2}: Grade cannot be empty")
                        error_count += 1
                        continue

                    # Get division
                    division = None
                    if 'division' in df.columns and pd.notna(row.get('division')):
                        div_name = str(row['division']).strip().lower()
                        division = divisions.get(div_name)
                        if not division:
                            # Try to find by case-insensitive match
                            for div in Division.objects.all():
                                if div.name.lower() == div_name:
                                    division = div
                                    break

                    # Get room
                    room = None
                    if 'room' in df.columns and pd.notna(row.get('room')):
                        room_number = str(row['room']).strip().lower()
                        room = rooms.get(room_number)
                        if not room:
                            # Try to find by case-insensitive match
                            for r in Room.objects.all():
                                if r.room_number.lower() == room_number:
                                    room = r
                                    break

                    # Get section
                    section = None
                    if 'section' in df.columns and pd.notna(row.get('section')):
                        section_name = str(row['section']).strip().lower()
                        for s in Section.objects.all():
                            if s.name.lower() == section_name:
                                section = s
                                break

                    # Get student type
                    student_type = 'day_scholar'
                    if 'student_type' in df.columns and pd.notna(row.get('student_type')):
                        st_type = str(row['student_type']).strip().lower()
                        if st_type in ['hostel', 'day_scholar', 'day scholar']:
                            student_type = 'hostel' if st_type == 'hostel' else 'day_scholar'

                    # Get optional fields
                    email = str(row.get('email', '')).strip() if 'email' in df.columns and pd.notna(row.get('email')) else ''
                    phone = str(row.get('phone', '')).strip() if 'phone' in df.columns and pd.notna(row.get('phone')) else ''
                    address = str(row.get('address', '')).strip() if 'address' in df.columns and pd.notna(row.get('address')) else ''

                    # Create student
                    student = Student.objects.create(
                        student_id=student_id,
                        first_name=first_name,
                        last_name=last_name,
                        student_type=student_type,
                        email=email,
                        phone=phone,
                        address=address,
                    )
                    
                    Enrollment.objects.create(
                        student=student,
                        academic_year=form_year,
                        grade=grade_obj, # Use Grade object
                        section=section,
                        division=division,
                        room=room
                    )
                    
                    success_count += 1

                except Exception as e:
                    errors.append(f"Row {index + 2}: {str(e)}")
                    error_count += 1

            # Show results
            if success_count > 0:
                messages.success(request, f'Successfully imported {success_count} student(s) into {form_year.name}.')
            if error_count > 0:
                error_msg = f'Failed to import {error_count} student(s).'
                if errors:
                    error_msg += f' Errors: {"; ".join(errors[:5])}'  # Show first 5 errors
                    if len(errors) > 5:
                        error_msg += f' ... and {len(errors) - 5} more.'
                messages.warning(request, error_msg)

            return redirect('students:student_list')

        except Exception as e:
            messages.error(request, f'Error reading Excel file: {str(e)}')
            return redirect('students:student_bulk_import')

    # GET request - show upload form
    context = {
        'academic_years': academic_years,
        'active_year': active_year,
        'sample_columns': [
            'student_id (Required)',
            'first_name (Required)',
            'last_name (Required)',
            'grade (Required)',
            'division (Optional)',
            'room (Optional)',
            'section (Optional)',
            'student_type (Optional: day_scholar or hostel)',
            'email (Optional)',
            'phone (Optional)',
            'address (Optional)'
        ]
    }
    return render(request, 'students/student_bulk_import.html', context)


@role_required(['admin', 'accountant'])
def student_bulk_import_template(request):
    """Download an Excel template for bulk student import"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students Import Template"

    columns = [
        ("student_id", True, "STU001", 15),
        ("first_name", True, "John", 20),
        ("last_name", True, "Doe", 20),
        ("grade", True, "10", 10),
        ("division", False, "A", 15),
        ("room", False, "101", 10),
        ("section", False, "HS", 10),
        ("student_type", False, "day_scholar", 15),
        ("email", False, "john@example.com", 25),
        ("phone", False, "1234567890", 15),
        ("address", False, "123 Main St", 30),
    ]

    # Writing headers and initial data
    for col_idx, (col_name, is_required, sample_val, width) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        # Header Style
        cell.font = Font(bold=True, color="FFFFFF")
        fill_color = "007BFF" if is_required else "6C757D" # Blue for required, grey for optional
        cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
        
        # Adjust width
        ws.column_dimensions[get_column_letter(col_idx)].width = width
        
        # Add sample data
        ws.cell(row=2, column=col_idx, value=sample_val)

    # Prepare HttpResponse
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.xlsx"'
    wb.save(response)
    
    return response

@role_required(['admin', 'accountant'])
def student_upgrade(request):
    """Upgrade students to next grade (e.g., grade 11 to 12, or 1st Year to 2nd Year)"""
    active_year = AcademicYear.objects.filter(is_active=True).first()
    if not active_year:
        messages.error(request, 'Please set an active academic year to perform upgrades.')
        return redirect('students:home')

    if request.method == 'POST':
        from_grade_name = request.POST.get('from_grade', '').strip()
        to_grade_name = request.POST.get('to_grade', '').strip()
        confirm = request.POST.get('confirm')

        if not from_grade_name or not to_grade_name:
            messages.error(request, 'Please enter both from and to grades.')
            return redirect('students:student_upgrade')

        if from_grade_name == to_grade_name:
            messages.error(request, 'From grade and to grade cannot be the same.')
            return redirect('students:student_upgrade')

        # Get Grade objects
        from_grade_obj = get_object_or_404(Grade, name=from_grade_name)
        to_grade_obj, _ = Grade.objects.get_or_create(name=to_grade_name)

        # Find latest enrollment for each active student
        enrollments_to_upgrade = []
        active_students = Student.objects.filter(is_active=True).prefetch_related('enrollments__academic_year')
        
        for student in active_students:
            # Order by academic year name descending to get latest
            enrollments = sorted(student.enrollments.all(), key=lambda x: x.academic_year.name, reverse=True)
            if enrollments:
                latest = enrollments[0]
                if latest.grade == from_grade_obj: # Compare with Grade object
                    # Also check if they already have an enrollment in the active year that is NOT from_grade
                    active_yr_enrollment = next((e for e in enrollments if e.academic_year == active_year), None)
                    if not active_yr_enrollment or active_yr_enrollment.grade == from_grade_obj: # Compare with Grade object
                        enrollments_to_upgrade.append(latest)

        count = len(enrollments_to_upgrade)

        if count == 0:
            messages.warning(request, f'No active students found in grade "{from_grade_name}" to upgrade.')
            return redirect('students:student_upgrade')

        if confirm != 'yes':
            # Show confirmation page
            context = {
                'from_grade': from_grade_name,
                'to_grade': to_grade_name,
                'student_count': count,
                'enrollments': enrollments_to_upgrade[:50],  # Show first 50 for preview
                'show_all': count > 50,
            }
            return render(request, 'students/student_upgrade_confirm.html', context)

        # Perform upgrade
        updated_count = 0
        created_count = 0
        for latest in enrollments_to_upgrade:
            # If the latest enrollment is ALREADY in the active year, we update it
            if latest.academic_year == active_year:
                latest.grade = to_grade_obj # Update with Grade object
                latest.save()
                updated_count += 1
            else:
                # Create a new enrollment for the active year
                Enrollment.objects.create(
                    student=latest.student,
                    academic_year=active_year,
                    grade=to_grade_obj, # Use Grade object
                    division=latest.division,
                    room=latest.room,
                    section=latest.section
                )
                created_count += 1

        messages.success(request, f'Successfully upgraded {updated_count + created_count} student(s) from grade "{from_grade_name}" to grade "{to_grade_name}".')
        return redirect('students:student_list')

    # GET request - show upgrade form
    # Get all existing grades from database
    existing_grades = Grade.objects.all().order_by('order', 'name') # Fetch Grade objects
    context = {
        'existing_grades': existing_grades,
    }
    return render(request, 'students/student_upgrade.html', context)


@role_required(['admin', 'accountant'])
def student_graduate(request):
    """Graduate students to Alumni (e.g., from Grade 12 or Final Year)"""
    active_year = AcademicYear.objects.filter(is_active=True).first()
    if not active_year:
        messages.error(request, 'Please set an active academic year to perform graduations.')
        return redirect('students:home')

    if request.method == 'POST':
        from_grade_name = request.POST.get('from_grade', '').strip()
        confirm = request.POST.get('confirm')

        if not from_grade_name:
            messages.error(request, 'Please select a grade to graduate.')
            return redirect('students:student_graduate')

        from_grade_obj = get_object_or_404(Grade, name=from_grade_name)

        # Find latest enrollment for each active student
        enrollments_to_graduate = []
        active_students = Student.objects.filter(is_active=True).prefetch_related('enrollments__academic_year')
        
        for student in active_students:
            # Order by academic year name descending to get latest
            enrollments = sorted(student.enrollments.all(), key=lambda x: x.academic_year.name, reverse=True)
            if enrollments:
                latest = enrollments[0]
                if latest.grade == from_grade_obj: # Compare with Grade object
                    # Only graduate if their latest enrollment is in the active year and matches from_grade
                    if latest.academic_year == active_year:
                        enrollments_to_graduate.append(latest)

        count = len(enrollments_to_graduate)

        if count == 0:
            messages.warning(request, f'No active students found in grade "{from_grade_name}" for the current academic year to graduate.')
            return redirect('students:student_graduate')

        if confirm != 'yes':
            # Show confirmation page
            context = {
                'from_grade': from_grade_name,
                'student_count': count,
                'enrollments': enrollments_to_graduate[:50],  # Show first 50 for preview
                'show_all': count > 50,
            }
            return render(request, 'students/student_graduate_confirm.html', context)

        # Perform graduation
        from alumni.models import AlumniRegistration

        graduated_count = 0
        for latest in enrollments_to_graduate:
            student = latest.student
            
            # Create Alumni record
            AlumniRegistration.objects.create(
                name=student.full_name,
                course=latest.division,
                batch=active_year.name,
                mobile_no=student.phone or ''
            )
            
            # Deactivate student
            student.is_active = False
            student.save()
            
            graduated_count += 1

        messages.success(request, f'Successfully graduated {graduated_count} student(s) from grade "{from_grade_name}" to Alumni.')
        return redirect('students:student_list')

    # GET request - show graduate form
    existing_grades = Grade.objects.all().order_by('order', 'name') # Fetch Grade objects
    context = {
        'existing_grades': existing_grades,
    }
    return render(request, 'students/student_graduate.html', context)


@login_required
def student_list(request):
    """List all students for the active academic year with filters"""
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    if not active_year:
        messages.warning(request, "Please create and set an Active Academic Year first.")
        # Fallback to just basic student list if no academic year exists
        students = Student.objects.filter(is_active=True)
    else:
        # We query Enrollments for the active year
        enrollments = Enrollment.objects.filter(academic_year=active_year, student__is_active=True).select_related('student', 'division', 'room', 'grade')

        # Filters
        grade_id = request.GET.get('grade') # Get grade ID
        division = request.GET.get('division')
        section = request.GET.get('section')
        student_type = request.GET.get('student_type')
        room = request.GET.get('room')
        search = request.GET.get('search')

        if grade_id:
            enrollments = enrollments.filter(grade_id=grade_id) # Filter by grade ID
        if division:
            enrollments = enrollments.filter(division_id=division)
        if section:
            enrollments = enrollments.filter(section_id=section)
        if student_type:
            enrollments = enrollments.filter(student__student_type=student_type)
        if room:
            enrollments = enrollments.filter(room_id=room)
        if search:
            enrollments = enrollments.filter(
                Q(student__student_id__icontains=search) |
                Q(student__first_name__icontains=search) |
                Q(student__last_name__icontains=search)
            )
        
        # Apply ordering: Grade (order then name), Division name, then Student ID
        enrollments = enrollments.order_by(
            'grade__order', 
            'grade__name', 
            'division__name', 
            'student__student_id'
        )
        
        # We will pass enrollments instead of students to the template, but we will adapt the template or rename the variable. 
        # Let's pass 'enrollments' as 'students' variable to MINIMIZE template changes initially,
        # but wait, the template expects `student.student_id`, `student.full_name`, `student.grade`. 
        # An enrollment has `enrollment.student.student_id`, `enrollment.grade`.
        # So we MUST update the template anyway to use `enrollment` objects. Let's pass 'enrollments'.
        
        students = enrollments 

    if request.GET.get('export') == 'excel':
        import openpyxl
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="students_list.xlsx"'
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students List"
        
        columns = ['Student ID', 'First Name', 'Last Name', 'Grade', 'Division', 'Room', 'Student Type', 'Phone', 'Email', 'Address']
        ws.append(columns)
        
        for item in students:
            if hasattr(item, 'student'): # Enrollment
                s = item.student
                grade_val = item.grade.name if item.grade else '' # Access grade name
                div_val = item.division.name if item.division else ''
                room_val = item.room.room_number if item.room else ''
            else: # Student fallback if no active year
                s = item
                grade_val = ''
                div_val = ''
                room_val = ''
                
            ws.append([
                s.student_id,
                s.first_name,
                s.last_name,
                grade_val,
                div_val,
                room_val,
                s.get_student_type_display(),
                s.phone,
                s.email,
                s.address
            ])
            
        wb.save(response)
        return response

    divisions = Division.objects.all()
    rooms = Room.objects.all()
    sections = Section.objects.all().order_by('order', 'name')
    grades = Grade.objects.all().order_by('order', 'name') # Fetch Grade objects

    context = {
        'students': students,
        'divisions': divisions,
        'rooms': rooms,
        'sections': sections,
        'grades': grades, # Pass Grade objects
        'current_filters': {
            'grade': grade_id if active_year else None, # Use grade_id
            'division': division if active_year else None,
            'section': section if active_year else None,
            'student_type': student_type if active_year else None,
            'room': room if active_year else None,
            'search': search if active_year else None,
        }
    }
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'students/partials/student_table_body.html', context)
        
    return render(request, 'students/student_list.html', context)


@role_required(['admin', 'teacher'])
def mark_attendance(request):
    """Mark attendance - Step 1: Select Date and Class"""
    attendance_type = request.GET.get('type', 'daily')
    selected_date = request.GET.get('date', date.today().isoformat())
    period_id = request.GET.get('period')
    activity_id = request.GET.get('activity')
    
    # -------------------------------------------------
    # CLASSROOM-WISE SUMMARY (GRADE + DIVISION)
    # -------------------------------------------------
    classroom_summary = OrderedDict()
    
    active_year = AcademicYear.objects.filter(is_active=True).first()
    if not active_year:
        messages.error(request, 'Please set an active academic year to mark attendance.')
        return redirect('students:home')
    
    # Get all active classes
    active_enrollments = Enrollment.objects.filter(
        academic_year=active_year, 
        student__is_active=True,
        grade__isnull=False
    ).values(
        'grade__section__id', 'grade__section__name', 
        'grade__id', 'grade__name', 
        'division__id', 'division__name'
    ).distinct()
    
    for cls in active_enrollments:
        if not cls['grade__id']: # Skip students without a grade
            continue
        g_id = cls['grade__id']
        g_name = cls['grade__name']
        d_id = cls['division__id']
        d_name = cls['division__name'] or 'No Division'
        s_id = cls['grade__section__id']
        s_name = cls['grade__section__name'] or 'No Section'
        cls_name = f"{g_name} - {d_name}"
        
        # Get count of students in this class
        student_count = Enrollment.objects.filter(academic_year=active_year, student__is_active=True, grade_id=g_id)
        if d_id:
            student_count = student_count.filter(division_id=d_id)
        else:
            student_count = student_count.filter(division__isnull=True)
            
        student_count = student_count.count()
        if student_count == 0:
            continue
            
        # Get count of recorded attendance for this class on selected date/type
        recorded_query = Attendance.objects.filter(
            date=selected_date,
            attendance_type=attendance_type,
            enrollment__grade_id=g_id,
            enrollment__academic_year=active_year
        )
        if d_id:
            recorded_query = recorded_query.filter(enrollment__division_id=d_id)
        else:
            recorded_query = recorded_query.filter(enrollment__division__isnull=True)
            
        if attendance_type == 'period' and period_id:
            recorded_query = recorded_query.filter(period_id=period_id)
        elif attendance_type == 'activity' and activity_id:
            recorded_query = recorded_query.filter(activity_id=activity_id)

        recorded_count = recorded_query.count()
        
        # Build status string (e.g., "12 / 12 Marked" or "0 / 12 Marked")
        if recorded_count == student_count:
            status = 'Complete'
            status_class = 'success'
        elif recorded_count > 0:
            status = 'Partial'
            status_class = 'warning'
        else:
            status = 'Not Marked'
            status_class = 'danger'
            
        classroom_summary[cls_name] = {
            'section_id': s_id,
            'section': s_name,
            'grade_id': g_id, # Pass grade ID
            'grade_name': g_name, # Pass grade name
            'division_id': d_id,
            'division': d_name,
            'student_count': student_count,
            'recorded_count': recorded_count,
            'status': status,
            'status_class': status_class
        }

    # Sorting
    division_summary = {k: v for k, v in classroom_summary.items() if v['division'] != 'No Division'}

    periods = Period.objects.all()
    activities = Activity.objects.filter(date=selected_date) if selected_date else Activity.objects.none()

    context = {
        'attendance_type': attendance_type,
        'selected_date': selected_date,
        'periods': periods,
        'activities': activities,
        'selected_period': period_id,
        'selected_activity': activity_id,
        'classroom_summary': classroom_summary,
        'division_summary': division_summary,
    }
    return render(request, 'students/mark_attendance.html', context)

@role_required(['admin', 'teacher'])
def mark_attendance_class(request, grade_id, division_id): # Changed grade to grade_id
    """Mark attendance - Step 2: Enter attendance for specific class"""
    attendance_type = request.GET.get('type', 'daily')
    selected_date = request.GET.get('date', date.today().isoformat())
    period_id = request.GET.get('period')
    activity_id = request.GET.get('activity')
    section_id = request.GET.get('section')
    
    # Handle division matching 'None' (from URL)
    actual_division_id = None if division_id == 0 else division_id
    
    active_year = AcademicYear.objects.filter(is_active=True).first()
    if not active_year:
        messages.error(request, 'Please set an active academic year to mark attendance.')
        return redirect('students:home')

    grade_obj = get_object_or_404(Grade, id=grade_id) # Get Grade object

    # Get enrollments based on class
    enrollments = Enrollment.objects.filter(academic_year=active_year, student__is_active=True, grade=grade_obj).select_related('student', 'division', 'room', 'section')
    
    if grade_obj.section:
        section_name = grade_obj.section.name
    else:
        section_name = "No Section"
        
    if actual_division_id:
        enrollments = enrollments.filter(division_id=actual_division_id)
        division = get_object_or_404(Division, id=actual_division_id)
        class_name = f"{section_name} - {grade_obj.name} - {division.name}" 
    else:
        enrollments = enrollments.filter(division__isnull=True)
        class_name = f"{section_name} - {grade_obj.name} - No Division"

    # Get existing attendance for the date
    existing_attendance = {}
    if attendance_type == 'period' and period_id:
        existing_attendance = {
            att.enrollment_id: att.status
            for att in Attendance.objects.filter(
                date=selected_date,
                attendance_type='period',
                period_id=period_id,
                enrollment__in=enrollments
            )
        }
    elif attendance_type == 'activity' and activity_id:
        existing_attendance = {
            att.enrollment_id: att.status
            for att in Attendance.objects.filter(
                date=selected_date,
                attendance_type='activity',
                activity_id=activity_id,
                enrollment__in=enrollments
            )
        }
    elif attendance_type == 'daily':
        existing_attendance = {
            att.enrollment_id: att.status
            for att in Attendance.objects.filter(
                date=selected_date,
                attendance_type='daily',
                enrollment__in=enrollments
            )
        }

    if request.method == 'POST':
        # Automatically determine who is marking the attendance from the logged-in user
        marked_by = request.user.get_full_name() or request.user.username
        if not marked_by:
            marked_by = "Admin" # Fallback if user somehow has no name/username
            
        attendance_data = request.POST.getlist('attendance')
        success_count = 0

        for data in attendance_data:
            enrollment_id, status = data.split('|')
            enrollment = get_object_or_404(Enrollment, id=enrollment_id)
            student = enrollment.student

            # Build filter for finding existing attendance
            filter_kwargs = {
                'student': student,
                'enrollment': enrollment,
                'date': selected_date,
                'attendance_type': attendance_type,
            }

            if attendance_type == 'period':
                if period_id:
                    filter_kwargs['period_id'] = period_id
                else:
                    continue  # Skip if period is required but not provided
            elif attendance_type == 'activity':
                if activity_id:
                    filter_kwargs['activity_id'] = activity_id
                else:
                    continue  # Skip if activity is required but not provided
            else:  # daily
                filter_kwargs['period__isnull'] = True
                filter_kwargs['activity__isnull'] = True

            attendance, created = Attendance.objects.update_or_create(
                defaults={
                    'status': status,
                    'marked_by': marked_by,
                },
                **filter_kwargs
            )
            success_count += 1

        params = [f"type={attendance_type}", f"date={selected_date}"]
        if period_id: params.append(f"period={period_id}")
        if activity_id: params.append(f"activity={activity_id}")
        
        return redirect(f"{reverse('students:mark_attendance')}?{'&'.join(params)}")

    context = {
        'class_name': class_name,
        'grade_id': grade_id, # Pass grade ID
        'grade_name': grade_obj.name, # Pass grade name
        'division_id': division_id,
        'section_id': section_id,
        'enrollments': enrollments,
        'attendance_type': attendance_type,
        'selected_date': selected_date,
        'existing_attendance': existing_attendance,
        'selected_period': period_id,
        'selected_activity': activity_id,
    }
    return render(request, 'students/mark_attendance_class.html', context)


from collections import OrderedDict
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils.timezone import localtime
import calendar
from datetime import date
from django.db.models import Exists, OuterRef


from collections import OrderedDict
from datetime import date
import calendar

from django.shortcuts import render
from django.db.models import Count, Q
from django.utils.timezone import localtime

from .models import Attendance, Grade
from students.models import Student, Division



@role_required(['admin', 'teacher'])
def attendance_list(request):
    """
    Attendance List with:
    - Advanced filters
    - Division-wise summary
    - Monthly Class + Division audit table
    - Sunday & Second Saturday holiday marking
    """

    # -------------------------------------------------
    # GET FILTERS
    # -------------------------------------------------
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    attendance_type = request.GET.get('attendance_type')
    status = request.GET.get('status')
    section = request.GET.get('section')
    grade_id = request.GET.get('grade') # Get grade ID
    division = request.GET.get('division')
    student_id = request.GET.get('student_id')

    # Month / Year for audit
    today = date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    active_year = AcademicYear.objects.filter(is_active=True).first()

    # -------------------------------------------------
    # BASE QUERYSET
    # -------------------------------------------------
    attendances = (
        Attendance.objects
        .filter(enrollment__academic_year=active_year)
        .select_related('student', 'enrollment', 'enrollment__division', 'enrollment__grade', 'period', 'activity')
        .order_by('-date', 'enrollment__grade__order', 'enrollment__grade__name', 'student__last_name') # Order by grade object
    )

    # -------------------------------------------------
    # APPLY FILTERS
    # -------------------------------------------------
    if date_from:
        attendances = attendances.filter(date__gte=date_from)

    if date_to:
        attendances = attendances.filter(date__lte=date_to)

    if attendance_type:
        attendances = attendances.filter(attendance_type=attendance_type)

    if status:
        attendances = attendances.filter(status=status)

    if grade_id:
        attendances = attendances.filter(enrollment__grade_id=grade_id) # Filter by grade ID

    if division:
        attendances = attendances.filter(enrollment__division_id=division)
        
    if section:
        attendances = attendances.filter(enrollment__section_id=section)

    if student_id:
        attendances = attendances.filter(
            student__student_id__icontains=student_id
        )

    # -------------------------------------------------
    # CLASSROOM-WISE SUMMARY (GRADE + DIVISION)
    # -------------------------------------------------
    classroom_summary = OrderedDict()
    
    # Pre-populate with all expected classes so they show even if no attendance
    active_enrollments = Enrollment.objects.filter(academic_year=active_year, student__is_active=True).values('section__id', 'section__name', 'grade__id', 'grade__name', 'division__id', 'division__name').distinct()
    for student_cls in active_enrollments:
        if not student_cls['grade__id']: # Skip students without a grade
            continue
        g_id = student_cls['grade__id']
        g_name = student_cls['grade__name']
        d_id = student_cls['division__id']
        d_name = student_cls['division__name'] or 'No Division'
        s_id = student_cls['section__id']
        s_name = student_cls['section__name'] or 'No Section'
        cls_name = f"{s_name} - {g_name} - {d_name}"
        
        classroom_summary[cls_name] = {
            'section_id': s_id,
            'section': s_name,
            'grade_id': g_id,
            'grade_name': g_name,
            'division_id': d_id,
            'division': d_name,
            'present': 0,
            'absent': 0,
            'late': 0,
            'excused': 0,
            'total': 0,
            'last_marker': None,
            'last_updated': None,
            'today_stats': None,
        }

    if attendances.exists():
        classroom_stats = (
            attendances
            .values(
                'enrollment__section__id',
                'enrollment__section__name',
                'enrollment__grade__id',
                'enrollment__grade__name',
                'enrollment__division__id',
                'enrollment__division__name'
            )
            .annotate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
                excused=Count('id', filter=Q(status='excused')),
            )
            .order_by('enrollment__grade__order', 'enrollment__grade__name', 'enrollment__division__name')
        )

        for stat in classroom_stats:
            grade_id_val = stat['enrollment__grade__id']
            grade_name_val = stat['enrollment__grade__name']
            div_id = stat['enrollment__division__id']
            div_name = stat['enrollment__division__name'] or 'No Division'
            sec_id = stat['enrollment__section__id']
            sec_name = stat['enrollment__section__name'] or 'No Section'

            classroom_name = f"{sec_name} - {grade_name_val} - {div_name}"

            latest_entry = (
                attendances
                .filter(
                    enrollment__grade_id=grade_id_val,
                    enrollment__division_id=div_id
                )
                .order_by('-updated_at', '-created_at', '-id')
                .first()
            )

            last_marker = getattr(latest_entry, 'marked_by', None)
            last_updated = None

            if latest_entry:
                last_dt = (
                    getattr(latest_entry, 'updated_at', None)
                    or getattr(latest_entry, 'created_at', None)
                )
                if last_dt:
                    last_updated = localtime(last_dt)

            if classroom_name in classroom_summary:
                classroom_summary[classroom_name].update({
                    'present': stat['present'],
                    'absent': stat['absent'],
                    'late': stat['late'],
                    'excused': stat['excused'],
                    'total': stat['total'],
                    'last_marker': last_marker,
                    'last_updated': last_updated,
                })
            else:
                classroom_summary[classroom_name] = {
                    'section_id': sec_id,
                    'section': sec_name,
                    'grade_id': grade_id_val,
                    'grade_name': grade_name_val,
                    'division_id': div_id,
                    'division': div_name,
                    'present': stat['present'],
                    'absent': stat['absent'],
                    'late': stat['late'],
                    'excused': stat['excused'],
                    'total': stat['total'],
                    'last_marker': last_marker,
                    'last_updated': last_updated,
                    'today_stats': None,
                }
                
    # -------------------------------------------------
    # TODAY'S CLASSROOM-WISE SUMMARY (GRADE + DIVISION)
    # -------------------------------------------------
    
    updated_classrooms = []
    not_updated_classrooms = []
    
    
    today_attendances = Attendance.objects.filter(date=today, enrollment__academic_year=active_year).select_related('student', 'enrollment', 'enrollment__division', 'enrollment__grade')
    
    if today_attendances.exists():
        today_stats = (
            today_attendances
            .values(
                'enrollment__section__name',
                'enrollment__grade__name',
                'enrollment__division__id',
                'enrollment__division__name'
            )
            .annotate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
                excused=Count('id', filter=Q(status='excused')),
            )
        )
        for stat in today_stats:
            grade_name_val = stat['enrollment__grade__name']
            div_name_val = stat['enrollment__division__name'] or 'No Division'
            sec_name_val = stat['enrollment__section__name'] or 'No Section'
            cls_name = f"{sec_name_val} - {grade_name_val} - {div_name_val}"
            
            if cls_name in classroom_summary:
                classroom_summary[cls_name]['today_stats'] = {
                    'total': stat['total'],
                    'present': stat['present'],
                    'absent': stat['absent'],
                    'late': stat['late'],
                    'excused': stat['excused'],
                }

    # Now populate updated/not_updated lists based on today_stats
    for cls_name, info in classroom_summary.items():
        if info['today_stats']:
            updated_classrooms.append(cls_name)
        else:
            not_updated_classrooms.append(cls_name)

    # -------------------------------------------------
    # RENDER CONTEXT
    # -------------------------------------------------
    
    # Exclude students with division 'None' from division_wise summary
    division_summary = {k: v for k, v in classroom_summary.items() if v['division'] != 'No Division'}

    context = {
        'attendances': attendances,
        'classroom_summary': classroom_summary,
        'division_summary': division_summary,
        'updated_classrooms': updated_classrooms,
        'not_updated_classrooms': not_updated_classrooms,

        # For the drop-downs
        'grades': Grade.objects.all().order_by('order', 'name'), # Fetch Grade objects
        'divisions': Division.objects.all(),
        'sections': Section.objects.all().order_by('order', 'name'),
        
        # State
        'current_filters': {
            'date_from': date_from,
            'date_to': date_to,
            'attendance_type': attendance_type,
            'status': status,
            'student_id': student_id,
            'section': section,
            'grade': grade_id, # Use grade_id
            'division': division
        },
    }

    return render(request, 'students/attendance_list.html', context)

@role_required(['admin', 'ntstaff'])
def hostel_movement_list(request):
    """List hostel movements with stats and enhanced search"""
    from django.db.models import Q
    movements = HostelMovement.objects.select_related('student')

    # Calculate Stats
    total_hostel_students = Student.objects.filter(student_type='hostel', is_active=True).count()
    # Away students are those with a movement log where is_returned is False
    away_students = HostelMovement.objects.filter(is_returned=False, student__is_active=True).values('student').distinct().count()
    present_students = total_hostel_students - away_students

    # Filters
    student_id = request.GET.get('student_id')
    is_returned = request.GET.get('is_returned')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if student_id:
        movements = movements.filter(
            Q(student__student_id__icontains=student_id) | 
            Q(student__first_name__icontains=student_id) |
            Q(student__last_name__icontains=student_id)
        )
    if is_returned is not None:
        movements = movements.filter(is_returned=is_returned == '1')
    if date_from:
        movements = movements.filter(departure_date__gte=date_from)
    if date_to:
        movements = movements.filter(departure_date__lte=date_to)

    movements = movements.order_by('-departure_date', '-departure_time')

    context = {
        'movements': movements,
        'stats': {
            'total': total_hostel_students,
            'present': present_students,
            'away': away_students
        },
        'current_filters': {
            'student_id': student_id,
            'is_returned': is_returned,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    return render(request, 'students/hostel_movement_list.html', context)


@role_required(['admin', 'ntstaff'])
def hostel_movement_create(request):
    """Create hostel movement record"""
    if request.method == 'POST':
        student_id = request.POST.get('student')
        departure_date = request.POST.get('departure_date')
        departure_time = request.POST.get('departure_time')
        escorting_person = request.POST.get('escorting_person')
        reason = request.POST.get('reason')
        expected_return_date = request.POST.get('expected_return_date') or None

        student = get_object_or_404(Student, id=student_id, student_type='hostel')

        movement = HostelMovement.objects.create(
            student=student,
            departure_date=departure_date,
            departure_time=departure_time,
            escorting_person=escorting_person,
            reason=reason,
            expected_return_date=expected_return_date,
        )

        messages.success(request, f'Movement record created for {student.full_name}')
        return redirect('students:hostel_movement_list')

    active_year = AcademicYear.objects.filter(is_active=True).first()
    enrollments = Enrollment.objects.filter(
        academic_year=active_year,
        student__student_type='hostel', 
        student__is_active=True
    ).select_related('student')
    context = {'enrollments': enrollments}
    return render(request, 'students/hostel_movement_create.html', context)


@role_required(['admin', 'ntstaff'])
def hostel_movement_update(request, pk):
    """Update hostel movement (mark as returned)"""
    movement = get_object_or_404(HostelMovement, pk=pk)

    if request.method == 'POST':
        arrival_date = request.POST.get('arrival_date')
        arrival_time = request.POST.get('arrival_time')
        sign = request.POST.get('sign')
        remarks = request.POST.get('remarks')
        is_returned = request.POST.get('is_returned') == 'on'

        movement.arrival_date = arrival_date if arrival_date else None
        movement.arrival_time = arrival_time if arrival_time else None
        movement.sign = sign
        movement.remarks = remarks
        movement.is_returned = is_returned
        movement.save()

        messages.success(request, f'Movement record updated for {movement.student.full_name}')
        return redirect('students:hostel_movement_list')

    context = {'movement': movement}
    return render(request, 'students/hostel_movement_update.html', context)


@role_required(['admin', 'teacher'])
def exam_type_list(request):
    """List all exam types"""
    exam_types = ExamType.objects.all()
    context = {
        'exam_types': exam_types,
    }
    return render(request, 'students/exam_type_list.html', context)


@role_required(['admin', 'teacher'])
def exam_type_create(request):
    """Create a new exam type"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        subject_type = request.POST.get('subject_type', 'all')
        section_id = request.POST.get('section')
        order = request.POST.get('order', 0)

        if not name:
            messages.error(request, 'Exam type name is required.')
            return redirect('students:exam_type_create')

        # Check if exam type already exists
        if ExamType.objects.filter(name__iexact=name).exists():
            messages.error(request, f'Exam type "{name}" already exists.')
            return redirect('students:exam_type_create')

        try:
            order = int(order) if order else 0
        except:
            order = 0

        section = None
        if section_id:
            section = Section.objects.filter(id=section_id).first()

        exam_type = ExamType.objects.create(
            name=name,
            description=description,
            subject_type=subject_type,
            section=section,
            order=order,
        )
        messages.success(request, f'Exam type "{exam_type.name}" created successfully!')
        return redirect('students:exam_type_list')

    # Pass the choices to the template
    sections = Section.objects.all().order_by('order', 'name')
    context = {
        'subject_type_choices': ExamType.SUBJECT_TYPE_CHOICES,
        'sections': sections
    }
    return render(request, 'students/exam_type_create.html', context)


@role_required(['admin', 'teacher'])
def exam_type_update(request, pk):
    """Update an exam type"""
    exam_type = get_object_or_404(ExamType, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        subject_type = request.POST.get('subject_type', 'all')
        section_id = request.POST.get('section')
        order = request.POST.get('order', 0)

        if not name:
            messages.error(request, 'Exam type name is required.')
            return redirect('students:exam_type_update', pk=pk)

        # Check if name already exists (excluding current)
        if ExamType.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, f'Exam type "{name}" already exists.')
            return redirect('students:exam_type_update', pk=pk)

        try:
            order = int(order) if order else 0
        except:
            order = exam_type.order

        section = None
        if section_id:
            section = Section.objects.filter(id=section_id).first()

        exam_type.name = name
        exam_type.description = description
        exam_type.subject_type = subject_type
        exam_type.section = section
        exam_type.order = order
        exam_type.save()

        messages.success(request, f'Exam type "{exam_type.name}" updated successfully!')
        return redirect('students:exam_type_list')

    sections = Section.objects.all().order_by('order', 'name')
    context = {
        'exam_type': exam_type,
        'subject_type_choices': ExamType.SUBJECT_TYPE_CHOICES,
        'sections': sections
    }
    return render(request, 'students/exam_type_update.html', context)


@role_required(['admin', 'teacher'])
def exam_type_delete(request, pk):
    """Delete an exam type"""
    exam_type = get_object_or_404(ExamType, pk=pk)

    if request.method == 'POST':
        name = exam_type.name
        exam_type.delete()
        messages.success(request, f'Exam type "{name}" deleted successfully!')
        return redirect('students:exam_type_list')

    context = {
        'exam_type': exam_type,
    }
    return render(request, 'students/exam_type_delete.html', context)


@role_required(['admin', 'teacher'])
def mark_entry_step1(request):
    """Step 1: Select Exam Type"""
    exam_types = ExamType.objects.all().order_by('order', 'name')
    return render(request, 'students/mark_entry_step1.html', {'exam_types': exam_types})

@role_required(['admin', 'teacher'])
def mark_entry_step2(request, exam_type_id):
    """Step 2: Select Class (Combination of Grade and Division)"""
    exam_type = get_object_or_404(ExamType, id=exam_type_id)
    
    # Get all active students to find unique Grade + Division combinations through Enrollment
    active_year = AcademicYear.objects.filter(is_active=True).first()
    enrollments_query = Enrollment.objects.filter(academic_year=active_year, student__is_active=True).select_related('division', 'grade')
    if exam_type.section:
        enrollments_query = enrollments_query.filter(section=exam_type.section)
    enrollments = enrollments_query
    
    # Extract unique classes
    classes_dict = {}
    for enrollment in enrollments:
        grade_obj = enrollment.grade
        div_id = enrollment.division_id
        div_name = enrollment.division.name if enrollment.division else None
        
        if not grade_obj:
            continue
        
        # Create a unique key for the combination
        key = f"{grade_obj.id}_{div_id or 'none'}"
        
        if key not in classes_dict:
            classes_dict[key] = {
                'grade_id': grade_obj.id,
                'grade_name': grade_obj.name,
                'division_id': div_id,
                'division_name': div_name,
                'student_count': 0
            }
        
        classes_dict[key]['student_count'] += 1
        
    # Sort classes logically (numeric grades first, then by division)
    def class_sort_key(c):
        grade_name = c['grade_name']
        grade_val = (0, int(grade_name)) if grade_name.isdigit() else (1, grade_name.lower())
        div_val = c['division_name'].lower() if c['division_name'] else ''
        return (grade_val, div_val)
        
    classes = sorted(classes_dict.values(), key=class_sort_key)
    
    return render(request, 'students/mark_entry_step2.html', {
        'exam_type': exam_type,
        'classes': classes
    })

@role_required(['admin', 'teacher'])
def mark_entry_step3(request, exam_type_id):
    """Step 3: Enter marks for all subjects for the selected class"""
    exam_type = get_object_or_404(ExamType, id=exam_type_id)
    grade_id = request.GET.get('grade_id') # Get grade ID
    division_id = request.GET.get('division_id')
    
    if not grade_id:
        messages.error(request, 'Grade is required.')
        return redirect('students:mark_entry_step2', exam_type_id=exam_type.id)
        
    grade_obj = get_object_or_404(Grade, id=grade_id) # Get Grade object
    
    # Get students for this class via Enrollment
    active_year = AcademicYear.objects.filter(is_active=True).first()
    enrollments_query = Enrollment.objects.filter(academic_year=active_year, student__is_active=True, grade=grade_obj).select_related('student')
    if exam_type.section:
        enrollments_query = enrollments_query.filter(section=exam_type.section)
        
    if division_id and division_id != 'None':
        enrollments_query = enrollments_query.filter(division_id=division_id)
        division_name = Division.objects.get(id=division_id).name
    else:
        enrollments_query = enrollments_query.filter(division__isnull=True)
        division_id = None
        division_name = None
        
    enrollments = list(enrollments_query.order_by('student__last_name', 'student__first_name'))
    students = [e.student for e in enrollments]
    
    if not students:
        messages.error(request, 'No active students found for this class.')
        return redirect('students:mark_entry_step2', exam_type_id=exam_type.id)
        
    # Get subjects for this class
    subjects_query = Subject.objects.filter(is_active=True, grade=grade_obj) # Filter by Grade object
    
    # First, filter by the exam's subject_type preference
    if exam_type.subject_type != 'all':
        subjects_query = subjects_query.filter(subject_type=exam_type.subject_type)
        
    # Then filter by division
    if division_id:
        if exam_type.subject_type == 'hadiya':
            # If specifically asking for hadiya, just ensure no division constraint blocks it
            subjects_query = subjects_query.filter(division__isnull=True)
        elif exam_type.subject_type == 'division':
            # If specifically asking for division subjects, must match the division
            subjects_query = subjects_query.filter(division_id=division_id)
        else:
            # 'all' - Show both division subjects and common (hadiya) subjects
            subjects_query = subjects_query.filter(
                Q(division_id=division_id) | Q(subject_type='hadiya', division__isnull=True)
            )
    else:
        # If no division, only show common/Hadiya subjects or subjects with no division
        subjects_query = subjects_query.filter(division__isnull=True)
        
    subjects = list(subjects_query.order_by('subject_type', 'name'))
    
    if request.method == 'POST':
        exam_date = request.POST.get('exam_date')
        entered_by = request.POST.get('entered_by', '')
        
        success_count = 0
        
        # Iterate over all possible inputs
        for student in students:
            for subject in subjects:
                # Expected input name format: marks_{student_id}_{subject_id}
                input_name = f'marks_{student.id}_{subject.id}'
                marks_str = request.POST.get(input_name)
                
                if marks_str and marks_str.strip():
                    try:
                        marks_obtained = float(marks_str)
                        
                        # Get max marks (check if custom max_marks was provided, else use subject default)
                        max_marks_input = f'max_marks_{subject.id}'
                        max_marks_str = request.POST.get(max_marks_input)
                        if max_marks_str and max_marks_str.strip():
                            max_marks = float(max_marks_str)
                        else:
                            max_marks = float(subject.max_marks)
                            
                        # Find matching enrollment
                        enrollment = next((e for e in enrollments if e.student == student), None)
                        
                        # Update or create
                        MarkEntry.objects.update_or_create(
                            student=student,
                            exam_type=exam_type,
                            subject=subject,
                            defaults={
                                'enrollment': enrollment,
                                'marks_obtained': marks_obtained,
                                'max_marks': max_marks,
                                'exam_date': exam_date if exam_date else None,
                                'entered_by': entered_by,
                            }
                        )
                        success_count += 1
                    except ValueError:
                        pass # Ignore invalid inputs
                        
        messages.success(request, f'Successfully saved {success_count} mark entries.')
        # Redirect back to the same page to show updated data
        redirect_url = f"{reverse('students:mark_entry_step3', args=[exam_type.id])}?grade_id={grade_id}" # Use grade_id
        if division_id:
            redirect_url += f"&division_id={division_id}"
        return redirect(redirect_url)

    # Get existing marks to populate the form
    # Format: existing_marks[student_id][subject_id] = marks_obtained
    existing_marks = {}
    
    mark_entries = MarkEntry.objects.filter(
        exam_type=exam_type,
        student__in=students,
        subject__in=subjects
    )
    
    for entry in mark_entries:
        if entry.student_id not in existing_marks:
            existing_marks[entry.student_id] = {}
        existing_marks[entry.student_id][entry.subject_id] = float(entry.marks_obtained)
        
    context = {
        'exam_type': exam_type,
        'grade_id': grade_id, # Pass grade ID
        'grade_name': grade_obj.name, # Pass grade name
        'division_id': division_id,
        'division_name': division_name,
        'students': students,
        'subjects': subjects,
        'existing_marks': existing_marks,
    }
    return render(request, 'students/mark_entry_step3.html', context)


from collections import defaultdict
from django.shortcuts import render
from .models import MarkEntry


from django.shortcuts import render
from .models import ExamType, Division

@role_required(['admin', 'teacher'])
def mark_entry_list(request):
    context = {
        'exam_types': ExamType.objects.select_related('section').all(),
        'sections': Section.objects.all().order_by('order', 'name'),
        'divisions': Division.objects.all(),
        'grades': Grade.objects.all().order_by('order', 'name'), # Pass Grade objects
    }
    return render(request, 'students/mark_entry_classwise.html', context)

from collections import defaultdict
from django.http import JsonResponse
from django.template.loader import render_to_string
from .models import MarkEntry


@role_required(['admin', 'teacher'])
def mark_entry_classwise_data(request):
    """
    AJAX view:
    Returns class-wise mark tables with ranking
    """
    mark_entries = MarkEntry.objects.select_related(
        'student',
        'enrollment',
        'enrollment__section',
        'enrollment__division',
        'enrollment__grade', # Select grade
        'exam_type',
        'subject',
    )

    # -------------------------
    # Filters (no reload)
    # -------------------------
    exam_type = request.GET.get('exam_type')
    section = request.GET.get('section')
    grade_id = request.GET.get('grade') # Get grade ID
    division = request.GET.get('division')

    if exam_type:
        mark_entries = mark_entries.filter(exam_type_id=exam_type)
    if section:
        mark_entries = mark_entries.filter(enrollment__section_id=section)
    if grade_id:
        mark_entries = mark_entries.filter(enrollment__grade_id=grade_id) # Filter by grade ID
    if division:
        mark_entries = mark_entries.filter(enrollment__division_id=division)

    # -------------------------
    # Group entries class-wise
    # -------------------------
    grouped = defaultdict(list)

    for entry in mark_entries:
        key = (
            entry.enrollment.section.name if entry.enrollment and entry.enrollment.section else "-",
            entry.enrollment.grade.name if entry.enrollment and entry.enrollment.grade else '-', # Use grade name
            entry.enrollment.division.name if entry.enrollment and entry.enrollment.division else "-",
            entry.exam_type.name,
        )
        grouped[key].append(entry)

    class_tables = []

    # -------------------------
    # Build tables
    # -------------------------
    for (sec, cls, div, exam), entries in grouped.items():

        # Collect subjects (ordered, unique)
        subjects = []
        for e in entries:
            if e.subject.name not in subjects:
                subjects.append(e.subject.name)

        # Collect students
        students = {}

        for e in entries:
            sid = e.student.id
            if sid not in students:
                students[sid] = {
                    'name': e.student.full_name,
                    'marks': [
                        {'marks': '-', 'grade': 'F', 'is_fail': True}
                        for _ in subjects
                    ],
                    'total': 0,
                    'fail_count': len(subjects),  # assume fail until proven pass

                }


        # Fill marks
        for e in entries:
            student = students[e.student.id]
            subject_index = subjects.index(e.subject.name)

            is_fail = str(e.grade_letter).strip().upper() == 'F'

            student['marks'][subject_index] = {
                'marks': float(e.marks_obtained),
                'grade': e.grade_letter,
                'is_fail': is_fail,
            }

            student['total'] += float(e.marks_obtained)

            # reduce fail count if passed
            if not is_fail:
                student['fail_count'] -= 1


        # -------------------------
        # Rank calculation
        # -------------------------
        sorted_students = sorted(
            students.values(),
            key=lambda x: (
                x['fail_count'],   # fewer fails first
                -x['total']        # higher marks next
            )
        )


        prev_key = None
        current_rank = 0

        for index, st in enumerate(sorted_students):
            current_key = (st['fail_count'], st['total'])

            if prev_key is None or current_key != prev_key:
                current_rank = index + 1

            st['rank'] = current_rank
            prev_key = current_key


        # -------------------------
        # Subject-wise averages
        # -------------------------
        subject_totals = [0] * len(subjects)
        student_count = len(sorted_students)

        for st in sorted_students:
            for i, m in enumerate(st['marks']):
                if m['marks'] != '-':
                    subject_totals[i] += m['marks']

        subject_averages = [
            round(total / student_count, 2) if student_count else 0
            for total in subject_totals
        ]

        # -------------------------
        # Final table object
        # -------------------------
        class_tables.append({
            'section': sec,
            'grade': cls,
            'division': div,
            'exam_type': exam,
            'subjects': subjects,
            'students': sorted_students,
            'subject_averages': subject_averages,
        })

    # -------------------------
    # Render partial HTML
    # -------------------------
    html = render_to_string(
        'students/partials/classwise_tables.html',
        {'class_tables': class_tables},
        request=request
    )

    return JsonResponse({'html': html})


@role_required(['admin', 'teacher'])
def progress_report(request):
    """Generate and view progress reports"""
    student_id = request.GET.get('student_id')
    exam_type_id = request.GET.get('exam_type')
    section_id = request.GET.get('section')
    grade_id = request.GET.get('grade')
    division_id = request.GET.get('division')
    academic_year_name = request.GET.get('academic_year', '')

    # Data isolation for students
    is_student = hasattr(request.user, 'profile') and request.user.profile.role == 'student'
    if is_student:
        if not request.user.profile.student_record:
            messages.error(request, "Student record not found.")
            return redirect('students:home')
        # Force student_id filter to own student_id
        student_id = request.user.profile.student_record.student_id
        
    enrollments_query = Enrollment.objects.filter(academic_year=active_year).select_related('student', 'grade', 'division', 'section')

    if student_id:
        enrollments_query = enrollments_query.filter(student__student_id__icontains=student_id)
    if section_id:
        enrollments_query = enrollments_query.filter(section_id=section_id)
    if grade_id:
        enrollments_query = enrollments_query.filter(grade_id=grade_id) # Filter by grade ID
    if division_id:
        enrollments_query = enrollments_query.filter(division_id=division_id)

    enrollments = enrollments_query

    if request.method == 'POST':
        if is_student:
             messages.error(request, "Students cannot generate progress reports.")
             return redirect('students:progress_report')
        student_ids = request.POST.getlist('students')
        exam_type_id = request.POST.get('exam_type')
        academic_year_name = request.POST.get('academic_year', '') # Changed to academic_year_name
        generated_by = request.POST.get('generated_by', '')

        if not student_ids or not exam_type_id:
            messages.error(request, 'Please select students and exam type.')
            return redirect('students:progress_report')

        exam_type = get_object_or_404(ExamType, id=exam_type_id)
        created_count = 0

        for student_id in student_ids:
            student = get_object_or_404(Student, id=student_id)

            # Calculate totals from mark entries
            mark_entries = MarkEntry.objects.filter(
                student=student,
                exam_type=exam_type
            )

            if not mark_entries.exists():
                continue

            total_marks = sum(entry.marks_obtained for entry in mark_entries)
            total_max_marks = sum(entry.max_marks for entry in mark_entries)
            percentage = (total_marks / total_max_marks * 100) if total_max_marks > 0 else 0

            # Calculate grade
            if percentage >= 90:
                grade_letter = 'A+'
            elif percentage >= 80:
                grade_letter = 'A'
            elif percentage >= 70:
                grade_letter = 'B+'
            elif percentage >= 60:
                grade_letter = 'B'
            elif percentage >= 50:
                grade_letter = 'C+'
            elif percentage >= 40:
                grade_letter = 'C'
            else:
                grade_letter = 'F'

            # Find the active enrollment for this student
            enrollment = Enrollment.objects.filter(student=student, academic_year=active_year).first()

            # Create or update progress report
            report, created = ProgressReport.objects.update_or_create(
                student=student,
                exam_type=exam_type,
                enrollment=enrollment,
                defaults={
                    'total_marks_obtained': total_marks,
                    'total_max_marks': total_max_marks,
                    'overall_percentage': percentage,
                    'overall_grade': grade_letter,
                    'generated_by': generated_by,
                }
            )
            if created:
                created_count += 1

        messages.success(request, f'Successfully generated {created_count} progress report(s).')
        return redirect('students:progress_report')

    # Get progress reports
    latest_reports = (
        ProgressReport.objects
        .values('student_id')
        .annotate(latest_time=Max('generated_at'))
    )

    reports = ProgressReport.objects.filter(
        generated_at__in=[r['latest_time'] for r in latest_reports]
    ).select_related(
        'student', 'exam_type', 'enrollment__grade' # Select grade
    )


    if student_id:
        reports = reports.filter(student__student_id__icontains=student_id)
    if exam_type_id:
        reports = reports.filter(exam_type_id=exam_type_id)
    if grade_id:
        reports = reports.filter(enrollment__grade_id=grade_id) # Filter by grade ID
    if division_id:
        reports = reports.filter(enrollment__division_id=division_id)
    if academic_year_name:
        reports = reports.filter(enrollment__academic_year__name=academic_year_name)

    reports = reports.order_by('-generated_at', 'enrollment__grade__order', 'enrollment__grade__name', 'student__last_name') # Order by grade object

    exam_types = ExamType.objects.all()
    divisions = Division.objects.all()
    sections = Section.objects.all().order_by('order', 'name')
    # Get all unique grades from database
    all_grades = Grade.objects.all().order_by('order', 'name')

    context = {
        'enrollments': enrollments,
        'reports': reports,
        'exam_types': exam_types,
        'divisions': divisions,
        'grades': all_grades, # Pass Grade objects
        'sections': sections,
        'current_filters': {
            'student_id': student_id,
            'exam_type': exam_type_id,
            'section': section_id,
            'grade': grade_id, # Use grade_id
            'division': division_id,
            'academic_year': academic_year_name,
        }
    }
    return render(request, 'students/progress_report.html', context)


@role_required(['admin', 'teacher', 'student'])
def progress_report_detail(request, pk):
    """View detailed progress report for a student"""
    report = get_object_or_404(ProgressReport, pk=pk)
    
    # Data isolation for students
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not request.user.profile.student_record or request.user.profile.student_record != report.student:
            messages.error(request, "You do not have permission to view other students' progress reports.")
            return redirect('students:home')
            
    mark_entries = MarkEntry.objects.filter(
        student=report.student,
        exam_type=report.exam_type
    ).select_related('subject').order_by('subject__subject_type', 'subject__name')

    # Separate Hadiya and division subjects
    hadiya_subjects = [entry for entry in mark_entries if entry.subject.subject_type == 'hadiya']
    division_subjects = [entry for entry in mark_entries if entry.subject.subject_type == 'division']

    context = {
        'report': report,
        'hadiya_subjects': hadiya_subjects,
        'division_subjects': division_subjects,
        'all_subjects': mark_entries,
    }
    return render(request, 'students/progress_report_detail.html', context)

@login_required
def student_profile(request, pk):
    """View a student's full profile (read-only)"""
    student = get_object_or_404(Student, id=pk)
    
    # Ensure students can only view their own profile, unless they are staff/admin
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not hasattr(request.user.profile, 'student_record') or request.user.profile.student_record != student:
            messages.error(request, 'You do not have permission to view this profile.')
            return redirect('students:home')
            
    # Get active components
    active_year = AcademicYear.objects.filter(is_active=True).first()
    enrollment = student.enrollments.filter(academic_year=active_year).first()
    
    # If no active enrollment found, just get the most recent one
    if not enrollment and student.enrollments.exists():
        enrollment = student.enrollments.order_by('-academic_year__start_date').first()
        
    context = {
        'student': student,
        'enrollment': enrollment,
        'active_year': active_year,
    }
    return render(request, 'students/student_profile.html', context)

@student_own_data_required
def student_edit(request, pk):
    """Edit an existing student"""
    student = get_object_or_404(Student, id=pk)
    
    # Get all academic years for the dropdown
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    # Get current enrollment (prefer the active year, or the most recent one if no active year)
    # But wait, if they are editing a specific enrollment for a specific year, 
    # we should ideally pass that year. For now, we look at active year or latest.
    enrollment = None
    selected_year = active_year
    
    if request.GET.get('year'):
        selected_year = AcademicYear.objects.filter(id=request.GET.get('year')).first()
        
    if selected_year:
        enrollment = Enrollment.objects.filter(student=student, academic_year=selected_year).first()
    elif student.enrollments.exists():
        enrollment = student.enrollments.first()
        selected_year = enrollment.academic_year

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        grade_id = request.POST.get('grade')
        division_id = request.POST.get('division') or None
        room_id = request.POST.get('room') or None
        section_id = request.POST.get('section') or None
        student_type = request.POST.get('student_type', 'day_scholar')
        email = request.POST.get('email', '')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')
        
        # Get the selected academic year from the form
        form_year_id = request.POST.get('academic_year_id')
        form_year = None
        if form_year_id:
            form_year = AcademicYear.objects.filter(id=form_year_id).first()
        else:
            form_year = active_year

        is_student = hasattr(request.user, 'profile') and request.user.profile.role == 'student'

        if is_student:
            student.email = email
            student.phone = phone
            student.address = address
            student.save()
            messages.success(request, f'Your profile was updated successfully!')
            return redirect('students:home')
        else:
            # Check duplicate student ID, but allow same ID for this student
            if Student.objects.exclude(id=student.id).filter(student_id=student_id).exists():
                messages.error(request, f'Student ID {student_id} already exists.')
            else:
                student.student_id = student_id
                student.first_name = first_name
                student.last_name = last_name
                student.student_type = student_type
                student.email = email
                student.phone = phone
                student.address = address
                student.save()
                
                siblings_ids = request.POST.getlist('siblings')
                student.siblings.set(siblings_ids)
                
                if form_year:
                    # Find if an enrollment already exists for this specific student and year
                    year_enrollment = Enrollment.objects.filter(student=student, academic_year=form_year).first()
                    if year_enrollment:
                        year_enrollment.grade_id = grade_id
                        year_enrollment.section_id = section_id
                        year_enrollment.division_id = division_id
                        year_enrollment.room_id = room_id
                        year_enrollment.save()
                    else:
                        Enrollment.objects.create(
                            student=student,
                            academic_year=form_year,
                            grade_id=grade_id,
                            section_id=section_id,
                            division_id=division_id,
                            room_id=room_id
                        )

                messages.success(request, f'Student {student.full_name} updated successfully for {form_year.name if form_year else "the selected year"}!')
                return redirect('students:student_list')

    divisions = Division.objects.all()
    rooms = Room.objects.all()
    sections = Section.objects.all().order_by('order', 'name')
    grades = Grade.objects.all().order_by('order', 'name')
    all_students = Student.objects.filter(is_active=True).exclude(id=student.id).order_by('first_name', 'last_name')

    context = {
        'student': student,
        'divisions': divisions,
        'rooms': rooms,
        'sections': sections,
        'grades': grades,
        'all_students': all_students,
        'academic_years': academic_years,
        'selected_year': selected_year,
        'active_year': active_year,
        'enrollment': enrollment,
    }
    return render(request, 'students/student_edit.html', context)

@role_required(['admin', 'ntstaff'])
def create_student_user(request, pk):
    """Create a linked User account for an existing student"""
    if request.method == 'POST':
        student = get_object_or_404(Student, id=pk)
        
        # Check if already linked
        if hasattr(student, 'user_profile') and student.user_profile:
            messages.error(request, f'Student {student.full_name} already has a linked user account.')
            return redirect('students:student_edit', pk=pk)
            
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('students:student_edit', pk=pk)
            
        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return redirect('students:student_edit', pk=pk)
            
        try:
            # Create the auth User
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=student.first_name,
                last_name=student.last_name,
                email=student.email or ''
            )
            
            # The signal automatically created a UserProfile for this user with role='ntstaff'.
            # We need to fetch it and update it to 'student' and link the student record.
            profile = user.profile
            profile.role = 'student'
            profile.student_record = student
            profile.save()
            
            messages.success(request, f'Login account created successfully for {student.full_name}!')
            
        except Exception as e:
            messages.error(request, f'Error creating user account: {str(e)}')
            
    return redirect('students:student_edit', pk=pk)


@role_required(['admin'])
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.delete()
    messages.success(request, "Student deleted successfully.")
    return redirect('students:student_list')

from django.shortcuts import render
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta, date
from collections import defaultdict
from calendar import monthrange


@role_required(['admin', 'teacher'])
def attendance_analytics(request):
    """Enhanced attendance analytics with multiple time ranges"""

    # Get filter parameters
    report_type = request.GET.get('report_type', 'daily')  # daily, monthly, quarterly, yearly, custom
    selected_date = request.GET.get('date', date.today().isoformat())
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    section_id = request.GET.get('section')
    grade = request.GET.get('grade')
    division_id = request.GET.get('division')

    # Parse selected date
    try:
        current_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except:
        current_date = date.today()

    # Calculate date ranges based on report type
    if report_type == 'daily':
        start_date = current_date
        end_date = current_date
    elif report_type == 'monthly':
        start_date = current_date.replace(day=1)
        _, last_day = monthrange(current_date.year, current_date.month)
        end_date = current_date.replace(day=last_day)
    elif report_type == 'quarterly':
        # Get current quarter
        quarter = (current_date.month - 1) // 3 + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = date(current_date.year, start_month, 1)
        end_month = start_month + 2
        _, last_day = monthrange(current_date.year, end_month)
        end_date = date(current_date.year, end_month, last_day)
    elif report_type == 'yearly':
        start_date = date(current_date.year, 1, 1)
        end_date = date(current_date.year, 12, 31)
    elif report_type == 'custom' and date_from and date_to:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        start_date = current_date
        end_date = current_date

    # Base queryset
    attendances = Attendance.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
        enrollment__academic_year__is_active=True
    ).select_related('student', 'enrollment', 'enrollment__division', 'enrollment__room')

    # Apply filters
    if section_id:
        attendances = attendances.filter(enrollment__section_id=section_id)
    if grade:
        attendances = attendances.filter(enrollment__grade=grade)
    if division_id:
        attendances = attendances.filter(enrollment__division_id=division_id)

    # Calculate overall statistics
    total_records = attendances.count()
    present_count = attendances.filter(status='present').count()
    absent_count = attendances.filter(status='absent').count()
    late_count = attendances.filter(status='late').count()
    excused_count = attendances.filter(status='excused').count()

    overall_percentage = round((present_count / total_records * 100), 2) if total_records > 0 else 0
    present_percentage = round((present_count / total_records * 100), 2) if total_records > 0 else 0
    absent_percentage = round((absent_count / total_records * 100), 2) if total_records > 0 else 0
    late_percentage = round((late_count / total_records * 100), 2) if total_records > 0 else 0
    excused_percentage = round((excused_count / total_records * 100), 2) if total_records > 0 else 0

    # Division-wise breakdown
    division_stats = {}

    # Get distinct combinations of section, grade and division
    grade_div_combinations = attendances.values_list(
        'enrollment__section__id',
        'enrollment__section__name',
        'enrollment__grade__id',
        'enrollment__grade__name',
        'enrollment__division__id',
        'enrollment__division__name'
    ).distinct()

    for sec_id, sec_name, grade_id_val, grade_name_val, div_id, div_name in grade_div_combinations:
        # Filter attendances for this specific grade + division combination
        div_attendances = attendances.filter(
            enrollment__section_id=sec_id,
            enrollment__grade_id=grade_id_val,
            enrollment__division_id=div_id
        )

        div_total = div_attendances.count()
        div_present = div_attendances.filter(status='present').count()
        div_absent = div_attendances.filter(status='absent').count()
        div_late = div_attendances.filter(status='late').count()
        div_excused = div_attendances.filter(status='excused').count()

        div_percentage = round((div_present / div_total * 100), 2) if div_total > 0 else 0

        # Create a unique key for section + grade + division
        sec_name_display = sec_name or 'No Section'
        key = f"{sec_name_display} - {grade_name_val or 'N/A'} - {div_name or 'No Division'}"

        division_stats[key] = {
            'id': div_id,
            'section': sec_name_display,
            'grade_id': grade_id_val,
            'grade': grade_name_val,
            'division': div_name,
            'total': div_total,
            'present': div_present,
            'absent': div_absent,
            'late': div_late,
            'excused': div_excused,
            'percentage': div_percentage,
            'status': 'good' if div_percentage >= 85 else 'warning' if div_percentage >= 75 else 'critical'
        }

    # Sort division_stats by section, grade and division name
    division_stats = dict(sorted(division_stats.items(), key=lambda x: (x[1]['section'] or '', x[1]['grade'] or '', x[1]['division'] or '')))

    # Student-wise statistics (for detailed reports)
    student_stats = []
    if report_type in ['monthly', 'quarterly', 'yearly', 'custom']:
        enrollments = Enrollment.objects.filter(academic_year__is_active=True, student__is_active=True).select_related('student', 'division', 'grade')
        if grade:
            enrollments = enrollments.filter(grade_id=grade)
        if division_id:
            enrollments = enrollments.filter(division_id=division_id)

        for enrollment in enrollments[:100]:  # Limit to avoid performance issues
            student_attendances = attendances.filter(student=enrollment.student)
            total = student_attendances.count()
            present = student_attendances.filter(status='present').count()
            absent = student_attendances.filter(status='absent').count()
            late = student_attendances.filter(status='late').count()

            if total > 0:
                percentage = round((present / total * 100), 2)
                student_stats.append({
                    'student': enrollment.student,
                    'enrollment': enrollment,
                    'total': total,
                    'present': present,
                    'absent': absent,
                    'late': late,
                    'percentage': percentage,
                    'status': 'good' if percentage >= 85 else 'warning' if percentage >= 75 else 'critical'
                })

        # Sort by percentage (lowest first for attention)
        student_stats.sort(key=lambda x: x['percentage'])

    # Daily trend (last 7 days for daily/monthly views)
    daily_trend = []
    if report_type in ['daily', 'monthly']:
        for i in range(6, -1, -1):
            trend_date = current_date - timedelta(days=i)
            day_attendances = Attendance.objects.filter(date=trend_date, enrollment__academic_year__is_active=True)
            if section_id:
                day_attendances = day_attendances.filter(enrollment__section_id=section_id)
            if grade:
                day_attendances = day_attendances.filter(enrollment__grade_id=grade)
            if division_id:
                day_attendances = day_attendances.filter(enrollment__division_id=division_id)

            day_total = day_attendances.count()
            day_present = day_attendances.filter(status='present').count()
            day_percentage = round((day_present / day_total * 100), 2) if day_total > 0 else 0

            daily_trend.append({
                'date': trend_date,
                'percentage': day_percentage,
                'total': day_total
            })

    # Get available grades and divisions for filters
    grades = Grade.objects.all().order_by('order', 'name')
    divisions = Division.objects.all()

    # Handle CSV export
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        filename = f'attendance_report_{report_type}_{start_date}_to_{end_date}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Write header
        writer.writerow(['Attendance Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        writer.writerow([f'Report Type: {report_type}'])
        writer.writerow([])

        # Overall statistics
        writer.writerow(['Overall Statistics'])
        writer.writerow(['Metric', 'Count', 'Percentage'])
        writer.writerow(['Total Records', total_records, ''])
        writer.writerow(['Present', present_count, f'{overall_percentage}%'])
        writer.writerow(['Absent', absent_count, f'{round(absent_count/total_records*100, 2) if total_records > 0 else 0}%'])
        writer.writerow(['Late', late_count, f'{round(late_count/total_records*100, 2) if total_records > 0 else 0}%'])
        writer.writerow(['Excused', excused_count, f'{round(excused_count/total_records*100, 2) if total_records > 0 else 0}%'])
        writer.writerow([])

        # Division-wise statistics
        if division_stats:
            writer.writerow(['Division-wise Statistics'])
            writer.writerow(['Class Details', 'Total', 'Present', 'Absent', 'Late', 'Excused', 'Percentage', 'Status'])
            for key, stats in division_stats.items():
                writer.writerow([
                    key,
                    stats['total'],
                    stats['present'],
                    stats['absent'],
                    stats['late'],
                    stats['excused'],
                    f"{stats['percentage']}%",
                    stats['status']
                ])
            writer.writerow([])

        # Student-wise statistics
        if student_stats:
            writer.writerow(['Student-wise Statistics'])
            writer.writerow(['Student ID', 'Name', 'Section', 'Grade', 'Division', 'Total', 'Present', 'Absent', 'Late', 'Percentage', 'Status'])
            for stat in student_stats:
                writer.writerow([
                    stat['student'].student_id,
                    stat['student'].full_name,
                    stat['enrollment'].section.name if stat['enrollment'].section else '-',
                    stat['enrollment'].grade,
                    stat['enrollment'].division.name if stat['enrollment'].division else '-',
                    stat['total'],
                    stat['present'],
                    stat['absent'],
                    stat['late'],
                    f"{stat['percentage']}%",
                    stat['status']
                ])

        return response

    context = {
        'report_type': report_type,
        'selected_date': selected_date,
        'date_from': date_from,
        'date_to': date_to,
        'selected_grade': grade,
        'selected_division': division_id,
        'selected_section': section_id,
        'grades': grades,
        'divisions': divisions,
        'sections': Section.objects.all().order_by('order', 'name'),
        'total_records': total_records,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'excused_count': excused_count,
        'overall_percentage': overall_percentage,
        'present_percentage': present_percentage,
        'absent_percentage': absent_percentage,
        'late_percentage': late_percentage,
        'excused_percentage': excused_percentage,
        'division_stats': division_stats,
        'student_stats': student_stats,
        'daily_trend': daily_trend,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'students/attendance_analytics.html', context)

# Detect students absent 3+ days in a row
def get_consecutive_absences(student_id, days=3):
    recent = Attendance.objects.filter(
        student_id=student_id,
        date__gte=date.today() - timedelta(days=days)
    ).order_by('-date')

    return all(a.status == 'absent' for a in recent[:days])

from collections import defaultdict
from django.shortcuts import render
from .models import MarkEntry, ExamType

@role_required(['admin', 'teacher'])
def performance_analysis(request):
    exam_type_id = request.GET.get('exam_type')

    exam_types = ExamType.objects.all()
    toppers_by_class = []

    selected_exam_obj = None
    if exam_type_id:
        selected_exam_obj = ExamType.objects.filter(id=exam_type_id).first()


    if exam_type_id:
        entries = MarkEntry.objects.select_related(
            'student',
            'enrollment',
            'enrollment__section',
            'enrollment__division',
            'exam_type',
            'subject',
        ).filter(exam_type_id=exam_type_id)

        grouped = defaultdict(list)

        # Group by section + class + division
        for e in entries:
            key = (
                e.enrollment.section.name if e.enrollment and e.enrollment.section else "-",
                e.enrollment.grade if e.enrollment else "-",
                e.enrollment.division.name if e.enrollment and e.enrollment.division else "-"
            )
            grouped[key].append(e)

        for (section, grade, division), marks in grouped.items():
            students = {}
            subjects_per_student = defaultdict(set)

            # -------------------------
            # Build student-wise data
            # -------------------------
            for m in marks:
                sid = m.student.id

                if sid not in students:
                    students[sid] = {
                        'name': m.student.full_name,
                        'total': 0,
                        'fail_count': 0,
                    }

                students[sid]['total'] += float(m.marks_obtained)
                subjects_per_student[sid].add(m.subject_id)

                # FAIL if grade is F
                is_fail = str(m.grade_letter).strip().upper() == 'F'
                if is_fail:
                    students[sid]['fail_count'] += 1

            # -------------------------
            # ABSENT = FAIL
            # -------------------------
            # find total subjects in this class
            all_subjects = set(m.subject_id for m in marks)

            for sid, st in students.items():
                attended_subjects = subjects_per_student.get(sid, set())
                absent_count = len(all_subjects - attended_subjects)

                st['fail_count'] += absent_count  # absent = fail

            # -------------------------
            # FILTER: ONLY FULL PASS STUDENTS
            # -------------------------
            passed_students = [
                st for st in students.values()
                if st['fail_count'] == 0
            ]

            if not passed_students:
                continue  # no toppers for this class

            # -------------------------
            # SORT & RANK
            # -------------------------
            ranked = sorted(
                passed_students,
                key=lambda x: -x['total']
            )

            for idx, st in enumerate(ranked):
                st['rank'] = idx + 1

            toppers_by_class.append({
                'section': section,
                'grade': grade,
                'division': division,
                'toppers': ranked[:3]  # 🥇🥈🥉 ONLY PASSED
            })

    context = {
        'exam_types': exam_types,
        'selected_exam': exam_type_id,
        'selected_exam_obj': selected_exam_obj,
        'toppers_by_class': toppers_by_class
    }
    return render(request, 'students/performance_analysis.html', context)

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from django.db.models import Max
from django.db.models import IntegerField
from django.db.models.functions import Cast



@role_required(['admin', 'teacher'])
def bulk_progress_report_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="progress_reports.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    latest_reports = (
        ProgressReport.objects
        .values('student_id')
        .annotate(latest_time=Max('generated_at'))
    )

    reports = ProgressReport.objects.filter(
        generated_at__in=[r['latest_time'] for r in latest_reports]
    ).select_related(
        'student', 'exam_type', 'enrollment', 'enrollment__division'
    ).annotate(
        student_id_int=Cast('student__student_id', IntegerField())
    ).order_by(
        'student_id_int'
    )


    for report in reports:
        y = height - 2 * cm

        # ================= INSTITUTION HEADER =================
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(
            width / 2,
            y,
            "MARKAZ HADIYA WOMEN'S COLLEGE, THAZHAPRA"
        )
        y -= 0.7 * cm

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(
            width / 2,
            y,
            "HIGHER SECONDARY HALF YEARLY EXAMINATION"
        )
        y -= 1 * cm

        # Divider line
        c.line(2 * cm, y, width - 2 * cm, y)
        y -= 1 * cm

        # ================= REPORT TITLE =================
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, y, "PROGRESS REPORT")
        y -= 1.2 * cm

        c.setFont("Helvetica", 11)
        c.drawString(2 * cm, y, f"Student ID : {report.student.student_id}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Name       : {report.student.full_name}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Grade      : {report.enrollment.grade.name if report.enrollment and report.enrollment.grade else '-'}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Division   : {report.enrollment.division.name if report.enrollment and report.enrollment.division else '-'}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Exam       : {report.exam_type.name}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Academic Year : {report.enrollment.academic_year.name if report.enrollment else '-'}")
        y -= 1 * cm

        # ================= OVERALL PERFORMANCE =================
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Overall Performance")
        y -= 0.4 * cm

        overall_table = Table(
            [
                ["Total Marks", "Percentage", "Grade", "Rank"],
                [
                    f"{report.total_marks_obtained}/{report.total_max_marks}",
                    f"{report.overall_percentage:.2f}%",
                    report.overall_grade,
                    report.rank or "-"
                ]
            ],
            colWidths=[4 * cm] * 4
        )

        overall_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))

        overall_table.wrapOn(c, width, height)
        overall_table.drawOn(c, 2 * cm, y - 2 * cm)
        y -= 3 * cm

        # ================= SUBJECT DATA (SAME AS DETAIL VIEW) =================
        mark_entries = MarkEntry.objects.filter(
            student=report.student,
            exam_type=report.exam_type
        ).select_related('subject').order_by(
            'subject__subject_type', 'subject__name'
        )

        hadiya_subjects = [
            e for e in mark_entries if e.subject.subject_type == 'hadiya'
        ]
        division_subjects = [
            e for e in mark_entries if e.subject.subject_type == 'division'
        ]

        def draw_subject_table(title, entries, y_pos):
            if not entries:
                return y_pos

            c.setFont("Helvetica-Bold", 12)
            c.drawString(2 * cm, y_pos, title)
            y_pos -= 0.4 * cm

            data = [["Subject", "Marks", "Max", "Percentage", "Grade"]]

            for e in entries:
                data.append([
                    e.subject.name,
                    e.marks_obtained,
                    e.max_marks,
                    f"{e.percentage:.2f}%",
                    e.grade_letter
                ])

            table = Table(data, colWidths=[6*cm, 3*cm, 3*cm, 3*cm, 2*cm])
            table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('ALIGN', (1,1), (-1,-1), 'CENTER'),
                ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
            ]))

            table_height = len(data) * 0.6 * cm
            table.wrapOn(c, width, height)
            table.drawOn(c, 2 * cm, y_pos - table_height)

            return y_pos - table_height - 0.8 * cm

        y = draw_subject_table("Hadiya (Islamic) Subjects", hadiya_subjects, y)
        y = draw_subject_table("Division Specific Subjects", division_subjects, y)
        # ================= PARENT SIGNATURE =================
        y -= 1.5 * cm

        c.setFont("Helvetica-Bold", 11)
        c.drawString(2 * cm, y, "Parent / Guardian Signature:")
        c.drawString(width / 2 + 1 * cm, y, "Date:")

        y -= 0.8 * cm

        # Signature lines
        c.line(2 * cm, y, width / 2 - 1 * cm, y)
        c.line(width / 2 + 1 * cm, y, width - 2 * cm, y)


        # ================= NEW PAGE =================
        c.showPage()

    c.save()
    return response

from datetime import date
import calendar
from django.shortcuts import render
from students.models import Student
from .models import Attendance
from students.models import Holiday



@role_required(['admin', 'teacher'])
def attendance_update_tracking(request):
    """
    Monthly Attendance Update Tracking
    (Classroom-wise audit page)
    """

    today = date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    days_in_month = calendar.monthrange(year, month)[1]
    month_days = list(range(1, days_in_month + 1))

    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    class_divisions = (
        Enrollment.objects
        .filter(academic_year=active_year)
        .exclude(grade__isnull=True)
        .exclude(grade__exact='')
        .select_related('division', 'section')
        .values('section__id', 'section__name', 'grade', 'division__id', 'division__name')
        .distinct()
        .order_by('section__name', 'grade', 'division__name')
    )

    attendance_matrix = []

    for cd in class_divisions:
        row = {
            'section': cd['section__name'],
            'grade': cd['grade'],
            'division': cd['division__name'],
            'days': []
        }

        for d in month_days:
            current_date = date(year, month, d)
            weekday = current_date.weekday()
            manual_holiday = Holiday.objects.filter(date=current_date).first()

            is_manual_holiday = manual_holiday is not None
            holiday_title = manual_holiday.title if manual_holiday else ''

            # Holiday logic
            is_sunday = weekday == 6
            is_second_saturday = (
                weekday == 5 and
                ((d + date(year, month, 1).weekday()) // 7 + 1) == 2
            )

            is_holiday = is_sunday or is_second_saturday or is_manual_holiday

            recorded = False
            if not is_holiday:
                recorded = Attendance.objects.filter(
                    enrollment__section_id=cd['section__id'],
                    enrollment__grade=cd['grade'],
                    enrollment__division_id=cd['division__id'],
                    enrollment__academic_year=active_year,
                    date=current_date
                ).exists()

            row['days'].append({
                'day': d,
                'recorded': recorded,
                'is_holiday': is_holiday,
                'holiday_type': (
                    holiday_title if is_manual_holiday
                    else 'Sunday' if is_sunday
                    else 'Second Saturday' if is_second_saturday
                    else ''
                )
            })


        attendance_matrix.append(row)

    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December'),
    ]

    CURRENT_YEAR = date.today().year
    YEAR_CHOICES = list(range(CURRENT_YEAR - 3, CURRENT_YEAR + 2))


    context = {
        'attendance_matrix': attendance_matrix,
        'month_days': month_days,
        'selected_month': month,
        'selected_year': year,
        'month_choices': MONTH_CHOICES,
        'year_choices': YEAR_CHOICES,
    }

    return render(request, 'students/attendance_update_tracking.html', context)
from django.contrib.auth.decorators import login_required


@role_required(['admin', 'teacher'])
def attendance_class_detail(request, grade, division_id):
    """
    Shows a list of students for a specific grade and division,
    along with their total attendance count and percentage.
    """
    try:
        if division_id == 0:
            division = None
        else:
            division = Division.objects.get(id=division_id)
    except Division.DoesNotExist:
        messages.error(request, "Division not found.")
        return redirect('students:attendance_list')

    active_year = AcademicYear.objects.filter(is_active=True).first()
    section_id = request.GET.get('section')
    
    if division:
        enrollments = Enrollment.objects.filter(grade=grade, division=division, academic_year=active_year, student__is_active=True).select_related('student', 'section').order_by('student__first_name', 'student__last_name')
    else:
        enrollments = Enrollment.objects.filter(grade=grade, division__isnull=True, academic_year=active_year, student__is_active=True).select_related('student', 'section').order_by('student__first_name', 'student__last_name')
        
    if section_id:
        enrollments = enrollments.filter(section_id=section_id)
        section = Section.objects.get(id=section_id)
    else:
        enrollments = enrollments.filter(section__isnull=True)
        section = None
    
    # Calculate attendance stats for each student
    student_stats = []
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    for enrollment in enrollments:
        attendances = Attendance.objects.filter(enrollment=enrollment)
        
        if date_from:
            attendances = attendances.filter(date__gte=date_from)
        if date_to:
            attendances = attendances.filter(date__lte=date_to)
            
        total_days = attendances.count()
        present_count = attendances.filter(status='present').count()
        late_count = attendances.filter(status='late').count()
        excused_count = attendances.filter(status='excused').count()
        absent_count = attendances.filter(status='absent').count()
        
        # Calculate percentage (Present + Late + Excused are considered 'attended')
        attended_count = present_count + late_count + excused_count
        
        percentage = 0
        if total_days > 0:
            percentage = round((attended_count / total_days) * 100, 2)
            
        student_stats.append({
            'student': enrollment.student,
            'enrollment': enrollment,
            'total_days': total_days,
            'present_count': present_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'absent_count': absent_count,
            'percentage': percentage
        })

    context = {
        'grade': grade,
        'division': division,
        'section': section,
        'section_id': section_id,
        'student_stats': student_stats,
        'current_filters': {
            'date_from': date_from,
            'date_to': date_to
        }
    }
    return render(request, 'students/attendance_class_detail.html', context)


@role_required(['admin', 'teacher', 'student'])
def attendance_student_detail(request, student_id):
    """
    Shows detailed attendance history for a single student.
    Includes monthly breakdown and date-specific checker.
    """
    # Data isolation for students
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not request.user.profile.student_record or request.user.profile.student_record.id != int(student_id):
            messages.error(request, "You do not have permission to view other students' attendance details.")
            return redirect('students:home')
            
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        messages.error(request, "Student not found.")
        return redirect('students:attendance_list')

    active_year = AcademicYear.objects.filter(is_active=True).first()
    enrollment = Enrollment.objects.filter(student=student, academic_year=active_year).first()

    attendances = Attendance.objects.filter(student=student).order_by('-date')
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    check_date = request.GET.get('check_date')
    
    # For date checker
    check_result = None
    if check_date:
        check_record = Attendance.objects.filter(student=student, date=check_date).first()
        if check_record:
            check_result = {
                'date': check_date,
                'status': check_record.get_status_display(),
                'status_class': check_record.status,
                'marked_by': check_record.marked_by,
                'remarks': check_record.remarks
            }
        else:
             check_result = {
                'date': check_date,
                'status': 'No Record Found',
                'status_class': 'unknown',
                'marked_by': '-',
                'remarks': '-'
             }

    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)

    total_days = attendances.count()
    present_count = attendances.filter(status='present').count()
    late_count = attendances.filter(status='late').count()
    excused_count = attendances.filter(status='excused').count()
    absent_count = attendances.filter(status='absent').count()
    
    attended_count = present_count + late_count + excused_count
    percentage = 0
    if total_days > 0:
        percentage = round((attended_count / total_days) * 100, 2)

    context = {
        'student': student,
        'enrollment': enrollment,
        'attendances': attendances,
        'total_days': total_days,
        'present_count': present_count,
        'late_count': late_count,
        'excused_count': excused_count,
        'absent_count': absent_count,
        'percentage': percentage,
        'check_result': check_result,
        'current_filters': {
            'date_from': date_from,
            'date_to': date_to,
            'check_date': check_date
        }
    }
    return render(request, 'students/attendance_student_detail.html', context)


# ==========================================
# SECTION MANAGEMENT
# ==========================================

from .models import Section
from .forms import SectionForm

@role_required(['admin'])
def section_list(request):
    """List all sections"""
    sections = Section.objects.all().order_by('order', 'name')
    context = {'sections': sections}
    return render(request, 'students/section_list.html', context)


@role_required(['admin', 'ntstaff'])
def hostel_student_list_view(request):
    """List all students registered to the hostel"""
    from django.db.models import Q
    
    students = Student.objects.filter(student_type='hostel')
    
    search_query = request.GET.get('search', '')
    if search_query:
        students = students.filter(
            Q(student_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
        
    # Calculate current status for each
    away_student_ids = set(HostelMovement.objects.filter(is_returned=False).values_list('student_id', flat=True))
    
    for st in students:
        st.is_away = st.id in away_student_ids
        
    context = {
        'students': students,
        'search_query': search_query
    }
    return render(request, 'students/hostel_student_list.html', context)


@role_required(['admin', 'ntstaff', 'student'])
def hostel_student_detail_view(request, pk):
    """Detailed profile for a specific hostel student"""
    # Data isolation for students
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not request.user.profile.student_record or request.user.profile.student_record.id != int(pk):
            from django.contrib import messages
            messages.error(request, "You do not have permission to view other students' hostel details.")
            return redirect('students:home')
    from datetime import datetime, date
    
    student = get_object_or_404(Student, pk=pk, student_type='hostel')
    movements = HostelMovement.objects.filter(student=student).order_by('-departure_date', '-departure_time')
    
    # Calculate historical away days
    total_away_days = 0
    today = timezone.now().date()
    
    for movement in movements:
        end_date = movement.arrival_date if movement.is_returned else today
        start_date = movement.departure_date
        total_away_days += (end_date - start_date).days
        
    # Enrollment baseline (when they joined)
    enroll_date = student.created_at.date()
    total_days_since_enroll = (today - enroll_date).days
    total_present_days = max(0, total_days_since_enroll - total_away_days)
    
    # Check specific date logic
    check_date_str = request.GET.get('check_date')
    check_status = None
    
    if check_date_str:
        try:
            check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
            # If the date is before enrollment or after today
            if check_date < enroll_date:
                check_status = "Not Enrolled Yet"
            elif check_date > today:
                check_status = "Future Date"
            else:
                # Find if any movement perfectly covers this date
                was_away = False
                for movement in movements:
                    m_end = movement.arrival_date if movement.is_returned else today
                    if movement.departure_date <= check_date <= m_end:
                        was_away = True
                        break
                check_status = "Away" if was_away else "Present"
        except ValueError:
            pass
            
    is_currently_away = movements.filter(is_returned=False).exists()
    
    context = {
        'student': student,
        'movements': movements,
        'total_away_days': total_away_days,
        'total_present_days': total_present_days,
        'is_currently_away': is_currently_away,
        'check_date_str': check_date_str,
        'check_status': check_status
    }
    return render(request, 'students/hostel_student_detail.html', context)


@role_required(['admin'])
def section_create(request):
    """Create a new section"""
    if request.method == 'POST':
        form = SectionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Section created successfully.')
            return redirect('students:section_list')
    else:
        form = SectionForm()
    
    context = {
        'form': form,
        'title': 'Create Section',
        'is_update': False
    }
    return render(request, 'students/section_form.html', context)


@role_required(['admin'])
def section_update(request, pk):
    """Update an existing section"""
    section = get_object_or_404(Section, pk=pk)
    if request.method == 'POST':
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            messages.success(request, 'Section updated successfully.')
            return redirect('students:section_list')
    else:
        form = SectionForm(instance=section)
    
    context = {
        'form': form,
        'title': 'Update Section',
        'is_update': True
    }
    return render(request, 'students/section_form.html', context)


@role_required(['admin'])
def section_delete(request, pk):
    """Delete an existing section"""
    section = get_object_or_404(Section, pk=pk)
    section.delete()
    messages.success(request, 'Section deleted successfully.')
    return redirect('students:section_list')

# ==========================================
# ACADEMIC YEAR MANAGEMENT
# ==========================================
from .forms import AcademicYearForm, SubjectForm

@role_required(['admin'])
def academic_year_list(request):
    """List all academic years"""
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    context = {'academic_years': academic_years}
    return render(request, 'students/academic_year_list.html', context)


@role_required(['admin'])
def academic_year_create(request):
    """Create a new academic year"""
    if request.method == 'POST':
        form = AcademicYearForm(request.POST)
        if form.is_valid():
            year = form.save()
            # If this is set as active, deactivate others
            if year.is_active:
                AcademicYear.objects.exclude(id=year.id).update(is_active=False)
            messages.success(request, 'Academic Year created successfully.')
            return redirect('students:academic_year_list')
    else:
        form = AcademicYearForm()
    
    context = {
        'form': form,
        'title': 'Create Academic Year',
        'is_update': False
    }
    return render(request, 'students/academic_year_form.html', context)


@role_required(['admin'])
def academic_year_update(request, pk):
    """Update an existing academic year"""
    year = get_object_or_404(AcademicYear, pk=pk)
    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=year)
        if form.is_valid():
            updated_year = form.save()
            # If this is set as active, deactivate others
            if updated_year.is_active:
                AcademicYear.objects.exclude(id=updated_year.id).update(is_active=False)
            messages.success(request, 'Academic Year updated successfully.')
            return redirect('students:academic_year_list')
    else:
        form = AcademicYearForm(instance=year)
    
    context = {
        'form': form,
        'title': 'Update Academic Year',
        'is_update': True
    }
    return render(request, 'students/academic_year_form.html', context)


# ==========================================
# SUBJECT MANAGEMENT
# ==========================================

@role_required(['admin'])
def subject_list(request):
    """List all subjects with filtering"""
    subjects = Subject.objects.all().order_by('grade', 'subject_type', 'name')
    
    # Filters
    grade = request.GET.get('grade')
    subject_type = request.GET.get('subject_type')
    
    if grade:
        subjects = subjects.filter(grade=grade)
    if subject_type:
        subjects = subjects.filter(subject_type=subject_type)
        
    # Get all unique grades for the filter dropdown
    grades = list(Subject.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    
    context = {
        'subjects': subjects,
        'grades': grades,
        'current_filters': {
            'grade': grade,
            'subject_type': subject_type
        }
    }
    return render(request, 'students/subject_list.html', context)


@role_required(['admin'])
def subject_create(request):
    """Create a new subject"""
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully.')
            return redirect('students:subject_list')
    else:
        form = SubjectForm()
        
    context = {
        'form': form,
        'title': 'Create Subject',
        'is_update': False
    }
    return render(request, 'students/subject_form.html', context)


@role_required(['admin'])
def subject_update(request, pk):
    """Update an existing subject"""
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated successfully.')
            return redirect('students:subject_list')
    else:
        form = SubjectForm(instance=subject)
        
    context = {
        'form': form,
        'title': 'Update Subject',
        'is_update': True
    }
    return render(request, 'students/subject_form.html', context)


# --- Enquiry Views ---

def enquiry_create_view(request):
    """Public or admin view to submit a new enquiry"""
    from .forms import EnquiryForm
    from .models import Division, AcademicYear
    import json
    
    if request.method == 'POST':
        form = EnquiryForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            
            # Auto-assign the active academic year for the selected section (or globally)
            active_year = AcademicYear.objects.filter(is_active=True).first()
            if active_year:
                enquiry.academic_year = active_year
                
            enquiry.save()
            return redirect('students:enquiry_success', application_number=enquiry.application_number)
    else:
        form = EnquiryForm()

    # Pass division mapping for the dependent course dropdown
    divisions = list(Division.objects.values('id', 'name', 'section_id'))
    divisions_json = json.dumps(divisions)
        
    return render(request, 'students/enquiry_form.html', {
        'form': form,
        'divisions_json': divisions_json
    })

def enquiry_success_view(request, application_number):
    """Public page shown after successfully submitting an enquiry"""
    from .models import Enquiry
    enquiry = get_object_or_404(Enquiry, application_number=application_number)
    return render(request, 'students/enquiry_success.html', {
        'application_number': application_number,
        'enquiry': enquiry
    })

def enquiry_status_view(request):
    """Public page to check enquiry status using application number"""
    from .models import Enquiry
    enquiry = None
    searched = False
    
    # Check for both form submission (POST) or direct link (GET parameter)
    app_number = None
    if request.method == 'POST':
        app_number = request.POST.get('application_number', '').strip()
    else:
        app_number = request.GET.get('app_no', '').strip()
        
    if app_number:
        searched = True
        enquiry = Enquiry.objects.filter(application_number__iexact=app_number).first()
        if not enquiry:
            messages.error(request, 'Application not found. Please check your application number.')
            
    from .models import GlobalSettings
    global_settings = GlobalSettings.load()
            
    return render(request, 'students/enquiry_status.html', {
        'enquiry': enquiry,
        'searched': searched,
        'global_settings': global_settings
    })


def enquiry_list_view(request):
    """Dashboard to list all enquiries in tabbed tables"""
    from .models import Enquiry, GlobalSettings
    import urllib.parse
    
    # Base query ordered by newest
    all_enquiries = Enquiry.objects.all().order_by('-created_at')
    global_settings = GlobalSettings.load()
    template = global_settings.whatsapp_message_template
    
    # Pre-compute WhatsApp URLs per enquiry to keep templates clean
    for enquiry in all_enquiries:
        status_url = request.build_absolute_uri(f"/students/enquiries/status/?app_no={enquiry.application_number}")
        message = template.format(
            name=enquiry.name,
            app_no=enquiry.application_number,
            status_link=status_url
        )
        enquiry.whatsapp_url = f"https://wa.me/{urllib.parse.urlencode({'phone': enquiry.phone})[6:]}?text={urllib.parse.quote(message)}"

    # Separate querysets for tabs
    pending_enquiries = [e for e in all_enquiries if e.status == 'Pending']
    received_enquiries = [e for e in all_enquiries if e.status == 'Received']
    token_enquiries = [e for e in all_enquiries if e.status == 'Token Generated']
    enrolled_enquiries = [e for e in all_enquiries if e.status == 'Enrolled']

    return render(request, 'students/enquiry_list.html', {
        'pending_enquiries': pending_enquiries,
        'received_enquiries': received_enquiries,
        'token_enquiries': token_enquiries,
        'enrolled_enquiries': enrolled_enquiries,
        'global_settings': global_settings
    })


@role_required(['admin', 'teacher', 'ntstaff'])
def enquiry_print_list_view(request):
    """Renders a clean, print-friendly list of all enquiries"""
    from .models import Enquiry
    enquiries = Enquiry.objects.all().order_by('-created_at')
    return render(request, 'students/enquiry_print_list.html', {
        'enquiries': enquiries,
        'today': timezone.now()
    })

def enquiry_generate_token_view(request, pk):
    """Generates the next sequential token for the day for the specific enquiry"""
    from .models import Enquiry
    from django.db.models import Max
    
    enquiry = get_object_or_404(Enquiry, pk=pk)
    
    if request.method == 'POST':
        if enquiry.status == 'Pending' or enquiry.status == 'Received':
            # Generate Token Logic
            today = timezone.now().date()
            # Find max token for today
            max_token = Enquiry.objects.filter(
                updated_at__date=today, 
                status='Token Generated'
            ).aggregate(Max('token_number'))['token_number__max']
            
            next_token = (max_token or 0) + 1
            
            enquiry.token_number = next_token
            enquiry.status = 'Token Generated'
            enquiry.save()
            messages.success(request, f'Token #{next_token} generated for {enquiry.name}.')
    
    return redirect('students:enquiry_list')

@role_required(['admin', 'teacher', 'ntstaff'])
def enquiry_mark_received(request, pk):
    """Marks a pending enquiry as Received"""
    from .models import Enquiry
    enquiry = get_object_or_404(Enquiry, pk=pk)
    
    if request.method == 'POST' and enquiry.status == 'Pending':
        enquiry.status = 'Received'
        enquiry.save()
        messages.success(request, f'Application {enquiry.application_number} marked as Received.')
        
    return redirect('students:enquiry_list')

@role_required(['admin', 'teacher', 'ntstaff'])
def enquiry_set_global_interview_date(request):
    """Sets the global, common interview date for all enquiries"""
    from .models import GlobalSettings
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        try:
            settings = GlobalSettings.load()
            
            if form_type == 'date_form':
                date_str = request.POST.get('global_interview_date')
                settings.common_interview_date = date_str if date_str else None
                settings.save()
                messages.success(request, f'Global interview date updated successfully.')
                
            elif form_type == 'whatsapp_form':
                msg_template = request.POST.get('whatsapp_message_template')
                if msg_template:
                    settings.whatsapp_message_template = msg_template
                    settings.save()
                    messages.success(request, f'WhatsApp message template updated successfully.')
                    
        except Exception as e:
            messages.error(request, f'Failed to update settings. Error: {e}')
                
    return redirect('students:enquiry_list')

def enquiry_token_print_view(request, pk):
    """View to print a generated token"""
    from .models import Enquiry
    enquiry = get_object_or_404(Enquiry, pk=pk)
    return render(request, 'students/enquiry_token_print.html', {'enquiry': enquiry})


def enquiry_enroll_view(request, pk):
    """One-click transition from Enquiry to Student profile"""
    from .models import Enquiry, Student
    
    enquiry = get_object_or_404(Enquiry, pk=pk)
    
    if enquiry.status == 'Enrolled':
        messages.info(request, 'This enquiry is already enrolled.')
        return redirect('students:enquiry_list')

    if request.method == 'POST':
        # Create a new student profile and pre-fill fields
        # Using a temporary unique ID generation for the newly enrolled student
        import random
        temp_id = f"TEMP-{random.randint(1000, 9999)}"
        
        # We assume the name has first and last components, or store everything in first_name
        name_parts = enquiry.name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Create student profile
        new_student = Student.objects.create(
            student_id=temp_id,
            first_name=first_name,
            last_name=last_name,
            phone=enquiry.phone,
            address=enquiry.district
        )
        
        # Update Enquiry status
        enquiry.status = 'Enrolled'
        enquiry.save()
        
        # Check if academic year is available from enquiry, otherwise fallback
        from .models import AcademicYear, Enrollment
        year = enquiry.academic_year
        if not year:
            year = AcademicYear.objects.filter(is_active=True).first()

        if year:
            Enrollment.objects.create(
                student=new_student,
                academic_year=year,
                section=enquiry.section,
                division=enquiry.course,
                grade=None  # Admin must set proper Grade on edit page
            )

        messages.success(request, f'Enquiry {enquiry.name} enrolled successfully! Please assign their proper Student ID and Academic Enrollment below.')
        # Redirect to the student edit form to complete other fields
        return redirect('students:student_edit', pk=new_student.pk)
        
    return redirect('students:enquiry_list')

# --- GRADE CRUD ---

@role_required(['admin'])
def grade_list(request):
    grades = Grade.objects.all()
    return render(request, 'students/grade_list.html', {'grades': grades})

@role_required(['admin'])
def grade_create(request):
    if request.method == 'POST':
        form = GradeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Grade created successfully.')
            return redirect('students:grade_list')
    else:
        form = GradeForm()
    return render(request, 'students/grade_form.html', {'form': form})

@role_required(['admin'])
def grade_update(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    if request.method == 'POST':
        form = GradeForm(request.POST, instance=grade)
        if form.is_valid():
            form.save()
            messages.success(request, 'Grade updated successfully.')
            return redirect('students:grade_list')
    else:
        form = GradeForm(instance=grade)
    return render(request, 'students/grade_form.html', {'form': form, 'is_update': True})

@role_required(['admin'])
def grade_delete(request, pk):
    grade = get_object_or_404(Grade, pk=pk)
    if request.method == 'POST':
        grade.delete()
        messages.success(request, 'Grade deleted successfully.')
        return redirect('students:grade_list')
    return render(request, 'students/grade_confirm_delete.html', {'grade': grade})

# --- DIVISION CRUD ---

@role_required(['admin'])
def division_list(request):
    divisions = Division.objects.all()
    return render(request, 'students/division_list.html', {'divisions': divisions})

@role_required(['admin'])
def division_create(request):
    if request.method == 'POST':
        form = DivisionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Division created successfully.')
            return redirect('students:division_list')
    else:
        form = DivisionForm()
    return render(request, 'students/division_form.html', {'form': form})

@role_required(['admin'])
def division_update(request, pk):
    division = get_object_or_404(Division, pk=pk)
    if request.method == 'POST':
        form = DivisionForm(request.POST, instance=division)
        if form.is_valid():
            form.save()
            messages.success(request, 'Division updated successfully.')
            return redirect('students:division_list')
    else:
        form = DivisionForm(instance=division)
    return render(request, 'students/division_form.html', {'form': form, 'is_update': True})

@role_required(['admin'])
def division_delete(request, pk):
    division = get_object_or_404(Division, pk=pk)
    if request.method == 'POST':
        division.delete()
        messages.success(request, 'Division deleted successfully.')
        return redirect('students:division_list')
    return render(request, 'students/division_confirm_delete.html', {'division': division})

# --- SUBJECT CRUD ---

@role_required(['admin'])
def subject_list(request):
    subjects = Subject.objects.select_related('grade', 'division', 'section').all()
    return render(request, 'students/subject_list.html', {'subjects': subjects})

@role_required(['admin'])
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully.')
            return redirect('students:subject_list')
    else:
        form = SubjectForm()
    return render(request, 'students/subject_form.html', {'form': form})

@role_required(['admin'])
def subject_update(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated successfully.')
            return redirect('students:subject_list')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'students/subject_form.html', {'form': form, 'is_update': True})

@role_required(['admin'])
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted successfully.')
        return redirect('students:subject_list')
    return render(request, 'students/subject_confirm_delete.html', {'subject': subject})

from django.contrib.auth.models import User
from .forms import UserManageForm
from .models import UserProfile

@role_required(['admin'])
def user_list(request):
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    return render(request, 'students/user_list.html', {'users': users})

@role_required(['admin'])
def user_create(request):
    if request.method == 'POST':
        form = UserManageForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()
            
            # The signal might create a default profile, so let's update it or create it
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = form.cleaned_data.get('role')
            profile.student_record = form.cleaned_data.get('student_record')
            profile.save()
            
            messages.success(request, f'User {user.username} created successfully.')
            return redirect('students:user_list')
    else:
        form = UserManageForm()
    
    return render(request, 'students/user_form.html', {'form': form, 'title': 'Create User'})

@role_required(['admin'])
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = getattr(user, 'profile', None)
    
    if request.method == 'POST':
        form = UserManageForm(request.POST, instance=user)
        if form.is_valid():
            updated_user = form.save(commit=False)
            password = form.cleaned_data.get('password')
            if password:
                updated_user.set_password(password)
            updated_user.save()
            
            if not profile:
                profile = UserProfile.objects.create(user=updated_user)
                
            profile.role = form.cleaned_data.get('role')
            profile.student_record = form.cleaned_data.get('student_record')
            profile.save()
            
            messages.success(request, f'User {updated_user.username} updated successfully.')
            return redirect('students:user_list')
    else:
        initial = {}
        if profile:
            initial['role'] = profile.role
            initial['student_record'] = profile.student_record
        form = UserManageForm(instance=user, initial=initial)
        
    return render(request, 'students/user_form.html', {'form': form, 'title': 'Edit User'})

@role_required(['admin'])
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj.is_superuser and request.user.pk != user_obj.pk:
        messages.error(request, "You cannot delete other superusers.")
        return redirect('students:user_list')
        
    if request.method == 'POST':
        user_obj.delete()
        messages.success(request, 'User deleted successfully.')
        return redirect('students:user_list')
    return render(request, 'students/user_confirm_delete.html', {'user_obj': user_obj})
