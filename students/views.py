from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, datetime
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
from .models import (
    Student, Attendance, HostelMovement, Period, Activity, Division, Room,
    ExamType, Subject, MarkEntry, ProgressReport
)


def home(request):
    """Dashboard/Home page"""
    today = date.today()
    
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
    
    context = {
        'total_students': total_students,
        'hostel_students': hostel_students,
        'day_scholar_students': day_scholar_students,
        'today_present': today_present,
        'today_absent': today_absent,
        'pending_movements': pending_movements,
    }
    return render(request, 'students/home.html', context)


def student_create(request):
    """Create a new student"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        grade = request.POST.get('grade')
        division_id = request.POST.get('division') or None
        room_id = request.POST.get('room') or None
        student_type = request.POST.get('student_type', 'day_scholar')
        email = request.POST.get('email', '')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')
        
        # Check if student_id already exists
        if Student.objects.filter(student_id=student_id).exists():
            messages.error(request, f'Student with ID {student_id} already exists.')
        else:
            student = Student.objects.create(
                student_id=student_id,
                first_name=first_name,
                last_name=last_name,
                grade=grade,
                division_id=division_id if division_id else None,
                room_id=room_id if room_id else None,
                student_type=student_type,
                email=email,
                phone=phone,
                address=address,
            )
            messages.success(request, f'Student {student.full_name} created successfully!')
            return redirect('students:student_list')
    
    divisions = Division.objects.all()
    rooms = Room.objects.all()
    context = {
        'divisions': divisions,
        'rooms': rooms,
    }
    return render(request, 'students/student_create.html', context)


def student_bulk_import(request):
    """Bulk import students from Excel file"""
    if not PANDAS_AVAILABLE:
        messages.error(request, 'pandas library is required for bulk import. Please install it: pip install pandas openpyxl')
        return redirect('students:student_list')
    
    if request.method == 'POST':
        if 'excel_file' not in request.FILES:
            messages.error(request, 'Please select an Excel file.')
            return redirect('students:student_bulk_import')
        
        excel_file = request.FILES['excel_file']
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Expected columns (case-insensitive matching)
            required_columns = ['student_id', 'first_name', 'last_name', 'grade']
            optional_columns = ['division', 'room', 'student_type', 'email', 'phone', 'address']
            
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
                    if not grade:
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
                    Student.objects.create(
                        student_id=student_id,
                        first_name=first_name,
                        last_name=last_name,
                        grade=grade,
                        division=division,
                        room=room,
                        student_type=student_type,
                        email=email,
                        phone=phone,
                        address=address,
                    )
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index + 2}: {str(e)}")
                    error_count += 1
            
            # Show results
            if success_count > 0:
                messages.success(request, f'Successfully imported {success_count} student(s).')
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
        'sample_columns': [
            'student_id', 'first_name', 'last_name', 'grade', 
            'division', 'room', 'student_type', 'email', 'phone', 'address'
        ]
    }
    return render(request, 'students/student_bulk_import.html', context)


def student_upgrade(request):
    """Upgrade students to next grade (e.g., grade 11 to 12, or 1st Year to 2nd Year)"""
    if request.method == 'POST':
        from_grade = request.POST.get('from_grade', '').strip()
        to_grade = request.POST.get('to_grade', '').strip()
        confirm = request.POST.get('confirm')
        
        if not from_grade or not to_grade:
            messages.error(request, 'Please enter both from and to grades.')
            return redirect('students:student_upgrade')
        
        if from_grade == to_grade:
            messages.error(request, 'From grade and to grade cannot be the same.')
            return redirect('students:student_upgrade')
        
        # Get students to upgrade
        students_to_upgrade = Student.objects.filter(grade=from_grade, is_active=True)
        count = students_to_upgrade.count()
        
        if count == 0:
            messages.warning(request, f'No active students found in grade "{from_grade}".')
            return redirect('students:student_upgrade')
        
        if confirm != 'yes':
            # Show confirmation page
            context = {
                'from_grade': from_grade,
                'to_grade': to_grade,
                'student_count': count,
                'students': students_to_upgrade[:50],  # Show first 50 for preview
                'show_all': count > 50,
            }
            return render(request, 'students/student_upgrade_confirm.html', context)
        
        # Perform upgrade
        updated_count = students_to_upgrade.update(grade=to_grade)
        messages.success(request, f'Successfully upgraded {updated_count} student(s) from grade "{from_grade}" to grade "{to_grade}".')
        return redirect('students:student_list')
    
    # GET request - show upgrade form
    # Get all existing grades from database
    existing_grades = Student.objects.values_list('grade', flat=True).distinct().order_by('grade')
    context = {
        'existing_grades': existing_grades,
    }
    return render(request, 'students/student_upgrade.html', context)


def student_list(request):
    """List all students with filters"""
    students = Student.objects.filter(is_active=True).select_related('division', 'room')
    
    # Filters
    grade = request.GET.get('grade')
    division = request.GET.get('division')
    student_type = request.GET.get('student_type')
    room = request.GET.get('room')
    search = request.GET.get('search')
    
    if grade:
        students = students.filter(grade=grade)
    if division:
        students = students.filter(division_id=division)
    if student_type:
        students = students.filter(student_type=student_type)
    if room:
        students = students.filter(room_id=room)
    if search:
        students = students.filter(
            Q(student_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    divisions = Division.objects.all()
    rooms = Room.objects.all()
    grades = Student.objects.values_list('grade', flat=True).distinct().order_by('grade')
    
    context = {
        'students': students,
        'divisions': divisions,
        'rooms': rooms,
        'grades': grades,
        'current_filters': {
            'grade': grade,
            'division': division,
            'student_type': student_type,
            'room': room,
            'search': search,
        }
    }
    return render(request, 'students/student_list.html', context)


def mark_attendance(request):
    """Mark attendance for students"""
    attendance_type = request.GET.get('type', 'daily')
    selected_date = request.GET.get('date', date.today().isoformat())
    grade = request.GET.get('grade')
    division = request.GET.get('division')
    room = request.GET.get('room')
    period_id = request.GET.get('period')
    activity_id = request.GET.get('activity')
    
    # Get students based on filters
    students = Student.objects.filter(is_active=True).select_related('division', 'room')
    
    if grade:
        students = students.filter(grade=grade)
    if division:
        students = students.filter(division_id=division)
    if room:
        students = students.filter(room_id=room)
    
    # Get existing attendance for the date
    existing_attendance = {}
    if attendance_type == 'period' and period_id:
        existing_attendance = {
            att.student_id: att.status
            for att in Attendance.objects.filter(
                date=selected_date,
                attendance_type='period',
                period_id=period_id
            )
        }
    elif attendance_type == 'activity' and activity_id:
        existing_attendance = {
            att.student_id: att.status
            for att in Attendance.objects.filter(
                date=selected_date,
                attendance_type='activity',
                activity_id=activity_id
            )
        }
    elif attendance_type == 'daily':
        existing_attendance = {
            att.student_id: att.status
            for att in Attendance.objects.filter(
                date=selected_date,
                attendance_type='daily'
            )
        }
    
    if request.method == 'POST':
        marked_by = request.POST.get('marked_by', '')
        attendance_data = request.POST.getlist('attendance')
        
        for data in attendance_data:
            student_id, status = data.split('|')
            student = get_object_or_404(Student, id=student_id)
            
            # Build filter for finding existing attendance
            filter_kwargs = {
                'student': student,
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
        
        messages.success(request, f'Attendance marked successfully for {selected_date}')
        return redirect('students:mark_attendance')
    
    periods = Period.objects.all()
    activities = Activity.objects.filter(date=selected_date) if selected_date else Activity.objects.none()
    divisions = Division.objects.all()
    rooms = Room.objects.all()
    grades = Student.objects.values_list('grade', flat=True).distinct().order_by('grade')
    
    context = {
        'students': students,
        'attendance_type': attendance_type,
        'selected_date': selected_date,
        'existing_attendance': existing_attendance,
        'periods': periods,
        'activities': activities,
        'divisions': divisions,
        'rooms': rooms,
        'grades': grades,
        'selected_period': period_id,
        'selected_activity': activity_id,
        'selected_grade': grade,
        'selected_division': division,
        'selected_room': room,
    }
    return render(request, 'students/mark_attendance.html', context)


def attendance_list(request):
    """View attendance records"""
    attendances = Attendance.objects.select_related('student', 'period', 'activity')
    
    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    attendance_type = request.GET.get('attendance_type')
    status = request.GET.get('status')
    grade = request.GET.get('grade')
    student_id = request.GET.get('student_id')
    
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    if attendance_type:
        attendances = attendances.filter(attendance_type=attendance_type)
    if status:
        attendances = attendances.filter(status=status)
    if grade:
        attendances = attendances.filter(student__grade=grade)
    if student_id:
        attendances = attendances.filter(student__student_id__icontains=student_id)
    
    attendances = attendances.order_by('-date', 'student__grade', 'student__last_name')
    
    context = {
        'attendances': attendances,
        'current_filters': {
            'date_from': date_from,
            'date_to': date_to,
            'attendance_type': attendance_type,
            'status': status,
            'grade': grade,
            'student_id': student_id,
        }
    }
    return render(request, 'students/attendance_list.html', context)


def hostel_movement_list(request):
    """List hostel movements"""
    movements = HostelMovement.objects.select_related('student')
    
    # Filters
    student_id = request.GET.get('student_id')
    is_returned = request.GET.get('is_returned')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if student_id:
        movements = movements.filter(student__student_id__icontains=student_id)
    if is_returned is not None:
        movements = movements.filter(is_returned=is_returned == '1')
    if date_from:
        movements = movements.filter(departure_date__gte=date_from)
    if date_to:
        movements = movements.filter(departure_date__lte=date_to)
    
    movements = movements.order_by('-departure_date', '-departure_time')
    
    context = {
        'movements': movements,
        'current_filters': {
            'student_id': student_id,
            'is_returned': is_returned,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    return render(request, 'students/hostel_movement_list.html', context)


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
    
    students = Student.objects.filter(student_type='hostel', is_active=True)
    context = {'students': students}
    return render(request, 'students/hostel_movement_create.html', context)


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


def exam_type_list(request):
    """List all exam types"""
    exam_types = ExamType.objects.all()
    context = {
        'exam_types': exam_types,
    }
    return render(request, 'students/exam_type_list.html', context)


def exam_type_create(request):
    """Create a new exam type"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
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
        
        exam_type = ExamType.objects.create(
            name=name,
            description=description,
            order=order,
        )
        messages.success(request, f'Exam type "{exam_type.name}" created successfully!')
        return redirect('students:exam_type_list')
    
    return render(request, 'students/exam_type_create.html')


def exam_type_update(request, pk):
    """Update an exam type"""
    exam_type = get_object_or_404(ExamType, pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
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
        
        exam_type.name = name
        exam_type.description = description
        exam_type.order = order
        exam_type.save()
        
        messages.success(request, f'Exam type "{exam_type.name}" updated successfully!')
        return redirect('students:exam_type_list')
    
    context = {
        'exam_type': exam_type,
    }
    return render(request, 'students/exam_type_update.html', context)


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


def mark_entry(request):
    """Enter marks for students"""
    exam_type_id = request.GET.get('exam_type')
    grade = request.GET.get('grade')
    division_id = request.GET.get('division')
    subject_id = request.GET.get('subject')
    
    # Get students based on filters
    students = Student.objects.filter(is_active=True).select_related('division', 'room')
    
    if grade:
        students = students.filter(grade=grade)
    if division_id:
        students = students.filter(division_id=division_id)
    
    # Get existing marks for the selected exam and subject
    existing_marks = {}
    if exam_type_id and subject_id:
        existing_marks = {
            entry.student_id: {
                'marks': entry.marks_obtained,
                'max_marks': entry.max_marks,
            }
            for entry in MarkEntry.objects.filter(
                exam_type_id=exam_type_id,
                subject_id=subject_id
            )
        }
    
    if request.method == 'POST':
        exam_type_id = request.POST.get('exam_type')
        subject_id = request.POST.get('subject')
        exam_date = request.POST.get('exam_date')
        entered_by = request.POST.get('entered_by', '')
        
        if not exam_type_id or not subject_id:
            messages.error(request, 'Please select exam type and subject.')
            return redirect('students:mark_entry')
        
        exam_type = get_object_or_404(ExamType, id=exam_type_id)
        subject = get_object_or_404(Subject, id=subject_id)
        
        marks_data = request.POST.getlist('marks')
        max_marks_data = request.POST.getlist('max_marks')
        student_ids = request.POST.getlist('student_ids')
        
        success_count = 0
        for i, marks_obtained_str in enumerate(marks_data):
            if not marks_obtained_str or not marks_obtained_str.strip():
                continue
            
            if i >= len(student_ids):
                continue
            
            student_id = student_ids[i]
            student = get_object_or_404(Student, id=student_id)
            
            # Get max marks for this entry
            max_marks = float(subject.max_marks)
            if i < len(max_marks_data) and max_marks_data[i]:
                try:
                    max_marks = float(max_marks_data[i])
                except:
                    pass
            
            try:
                marks_obtained = float(marks_obtained_str)
            except:
                continue
            
            # Update or create mark entry
            mark_entry, created = MarkEntry.objects.update_or_create(
                student=student,
                exam_type=exam_type,
                subject=subject,
                defaults={
                    'marks_obtained': marks_obtained,
                    'max_marks': max_marks,
                    'exam_date': exam_date if exam_date else None,
                    'entered_by': entered_by,
                }
            )
            success_count += 1
        
        messages.success(request, f'Successfully entered marks for {success_count} student(s).')
        return redirect('students:mark_entry')
    
    exam_types = ExamType.objects.all()
    subjects = Subject.objects.filter(is_active=True)
    
    # Filter subjects based on grade and division
    if grade:
        subjects = subjects.filter(grade=grade)
        if division_id:
            # Include both division-specific and Hadiya subjects
            subjects = subjects.filter(
                Q(division_id=division_id) | Q(subject_type='hadiya', division__isnull=True)
            )
        # If no division selected, show all subjects for that grade (both Hadiya and division-specific)
        # This allows user to see all available subjects
    
    # Get selected subject for max_marks
    selected_subject_obj = None
    if subject_id:
        try:
            selected_subject_obj = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            pass
    
    divisions = Division.objects.all()
    # Get all unique grades from students, sorted properly
    grades_list = list(Student.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    
    # Also get grades from subjects to show all possible grades
    subject_grades = list(Subject.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    
    # Combine and remove duplicates, keeping order
    all_grades = sorted(set(grades_list + subject_grades), key=lambda x: (
        # Sort numeric grades first, then text grades
        (0, int(x)) if x.isdigit() else (1, x.lower())
    ))
    
    context = {
        'students': students,
        'exam_types': exam_types,
        'subjects': subjects,
        'divisions': divisions,
        'grades': all_grades,
        'existing_marks': existing_marks,
        'selected_exam_type': exam_type_id,
        'selected_subject': subject_id,
        'selected_subject_obj': selected_subject_obj,
        'selected_grade': grade,
        'selected_division': division_id,
    }
    return render(request, 'students/mark_entry.html', context)


def mark_entry_list(request):
    """View all mark entries"""
    mark_entries = MarkEntry.objects.select_related('student', 'exam_type', 'subject')
    
    # Filters
    exam_type_id = request.GET.get('exam_type')
    grade = request.GET.get('grade')
    division_id = request.GET.get('division')
    subject_id = request.GET.get('subject')
    student_id = request.GET.get('student_id')
    
    if exam_type_id:
        mark_entries = mark_entries.filter(exam_type_id=exam_type_id)
    if grade:
        mark_entries = mark_entries.filter(student__grade=grade)
    if division_id:
        mark_entries = mark_entries.filter(student__division_id=division_id)
    if subject_id:
        mark_entries = mark_entries.filter(subject_id=subject_id)
    if student_id:
        mark_entries = mark_entries.filter(student__student_id__icontains=student_id)
    
    mark_entries = mark_entries.order_by('-exam_date', 'student__grade', 'student__last_name')
    
    exam_types = ExamType.objects.all()
    subjects = Subject.objects.filter(is_active=True)
    divisions = Division.objects.all()
    # Get all unique grades from students and subjects, sorted properly
    grades_list = list(Student.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    subject_grades = list(Subject.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    all_grades = sorted(set(grades_list + subject_grades), key=lambda x: (
        (0, int(x)) if x.isdigit() else (1, x.lower())
    ))
    
    context = {
        'mark_entries': mark_entries,
        'exam_types': exam_types,
        'subjects': subjects,
        'divisions': divisions,
        'grades': all_grades,
        'current_filters': {
            'exam_type': exam_type_id,
            'grade': grade,
            'division': division_id,
            'subject': subject_id,
            'student_id': student_id,
        }
    }
    return render(request, 'students/mark_entry_list.html', context)


def progress_report(request):
    """Generate and view progress reports"""
    student_id = request.GET.get('student_id')
    exam_type_id = request.GET.get('exam_type')
    grade = request.GET.get('grade')
    division_id = request.GET.get('division')
    academic_year = request.GET.get('academic_year', '')
    
    students = Student.objects.filter(is_active=True).select_related('division', 'room')
    
    if student_id:
        students = students.filter(student_id__icontains=student_id)
    if grade:
        students = students.filter(grade=grade)
    if division_id:
        students = students.filter(division_id=division_id)
    
    if request.method == 'POST':
        student_ids = request.POST.getlist('students')
        exam_type_id = request.POST.get('exam_type')
        academic_year = request.POST.get('academic_year', '')
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
            
            # Create or update progress report
            report, created = ProgressReport.objects.update_or_create(
                student=student,
                exam_type=exam_type,
                academic_year=academic_year,
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
    reports = ProgressReport.objects.select_related('student', 'exam_type')
    
    if student_id:
        reports = reports.filter(student__student_id__icontains=student_id)
    if exam_type_id:
        reports = reports.filter(exam_type_id=exam_type_id)
    if grade:
        reports = reports.filter(student__grade=grade)
    if division_id:
        reports = reports.filter(student__division_id=division_id)
    if academic_year:
        reports = reports.filter(academic_year=academic_year)
    
    reports = reports.order_by('-generated_at', 'student__grade', 'student__last_name')
    
    exam_types = ExamType.objects.all()
    divisions = Division.objects.all()
    # Get all unique grades from students and subjects, sorted properly
    grades_list = list(Student.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    subject_grades = list(Subject.objects.values_list('grade', flat=True).distinct().order_by('grade'))
    all_grades = sorted(set(grades_list + subject_grades), key=lambda x: (
        (0, int(x)) if x.isdigit() else (1, x.lower())
    ))
    
    context = {
        'students': students,
        'reports': reports,
        'exam_types': exam_types,
        'divisions': divisions,
        'grades': all_grades,
        'current_filters': {
            'student_id': student_id,
            'exam_type': exam_type_id,
            'grade': grade,
            'division': division_id,
            'academic_year': academic_year,
        }
    }
    return render(request, 'students/progress_report.html', context)


def progress_report_detail(request, pk):
    """View detailed progress report for a student"""
    report = get_object_or_404(ProgressReport, pk=pk)
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
