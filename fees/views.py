from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from students.decorators import role_required
from django.contrib import messages
from .models import StudentFee, FeePayment, AccountCategory, Income, Expense, FeeCategory, FeeItem, FeeStructure
from students.models import Student, Grade, Division
from django.db.models import Sum, Case, When, DecimalField, Q
from .forms import IncomeForm, ExpenseForm

# We might want to restrict this to 'accountant' or 'admin' later.
@role_required(['admin', 'accountant'])
def finance_dashboard(request):
    """Accountant Dashboard showing Income and Expense with detailed reporting."""
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    
    # 1. High-Level Summary
    total_income = Income.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_balance = total_income - total_expense
    
    # 2. Time-period statistics
    daily_income = Income.objects.filter(date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    daily_expense = Expense.objects.filter(date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    monthly_income = Income.objects.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    monthly_expense = Expense.objects.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    yearly_income = Income.objects.filter(date__gte=start_of_year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    yearly_expense = Expense.objects.filter(date__gte=start_of_year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 3. Item-wise Collection Breakdown (by AccountCategory)
    # We focus on Income categories
    category_collections = AccountCategory.objects.filter(type='income').annotate(
        total=Sum('incomes__amount')
    ).filter(total__gt=0).order_by('-total')

    recent_incomes = Income.objects.all().order_by('-date')[:15]
    recent_expenses = Expense.objects.all().order_by('-date')[:15]

    context = {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_balance': net_balance,
        
        'daily_income': daily_income,
        'daily_expense': daily_expense,
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'yearly_income': yearly_income,
        'yearly_expense': yearly_expense,
        
        'category_collections': category_collections,
        'recent_incomes': recent_incomes,
        'recent_expenses': recent_expenses,
        
        'today': today,
        'page_title': 'Finance Dashboard'
    }
    return render(request, 'fees/finance_dashboard.html', context)

@role_required(['admin', 'accountant'])
def fees_dashboard(request):
    """Dashboard focusing on Classroom-wise Fee Summary."""
    # Get all students with active enrollments
    active_students = Student.objects.filter(is_active=True, enrollments__academic_year__is_active=True).distinct()
    
    # Group students by (Grade, Division)
    classroom_data = {}
    
    for student in active_students:
        enrollment = student.current_enrollment
        if not enrollment:
            continue
            
        grade = enrollment.grade
        if not grade:
            continue
        division = enrollment.division
        classroom_key = (grade.id, division.id if division else None)
        
        if classroom_key not in classroom_data:
            classroom_data[classroom_key] = {
                'grade': grade,
                'division': division,
                'total_due': Decimal('0.00'),
                'student_count': 0,
                'name': f"{grade.name} - {division.name}" if grade and division else (grade.name if grade else "Unassigned")
            }
            
        # Calculate due for this student
        student_due = sum(f.balance for f in student.fees.all() if f.balance > 0)
        classroom_data[classroom_key]['total_due'] += Decimal(str(student_due))
        classroom_data[classroom_key]['student_count'] += 1
            
    # Convert to list and sort by grade name
    classrooms = sorted(classroom_data.values(), key=lambda x: x['name'])
    
    total_institution_due = sum(c['total_due'] for c in classrooms)
        
    context = {
        'classrooms': classrooms,
        'total_institution_due': total_institution_due,
        'page_title': 'Fee Dashboard'
    }
    return render(request, 'fees/fees_dashboard.html', context)

@role_required(['admin', 'accountant'])
def classroom_detail(request, grade_id, division_id=None):
    """Detailed student fee list for a specific classroom."""
    grade = get_object_or_404(Grade, id=grade_id)
    division = None
    if division_id:
        division = get_object_or_404(Division, id=division_id)
        
    students = Student.objects.filter(
        is_active=True,
        enrollments__academic_year__is_active=True,
        enrollments__grade=grade,
        enrollments__division=division
    ).distinct()
    
    student_data = []
    total_class_due = Decimal('0.00')
    
    for student in students:
        total_due = sum(f.balance for f in student.fees.all() if f.balance > 0)
        total_class_due += Decimal(str(total_due))
        student_data.append({
            'student': student,
            'total_due': total_due,
        })
        
    context = {
        'grade': grade,
        'division': division,
        'student_data': student_data,
        'total_class_due': total_class_due,
        'class_name': f"{grade.name} - {division.name}" if division else grade.name,
        'page_title': f"Class Detail: {grade.name}"
    }
    return render(request, 'fees/classroom_detail.html', context)

@role_required(['admin', 'accountant', 'student'])
def student_fees(request, student_id):
    """View all fees for a specific student with dashboard summaries."""
    # Data isolation for students
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not request.user.profile.student_record or request.user.profile.student_record.id != int(student_id):
            messages.error(request, "You do not have permission to view other students' fee details.")
            return redirect('students:home')
            
    student = get_object_or_404(Student, id=student_id)
    from django.utils import timezone
    today = timezone.now().date()
    
    fees = student.fees.all().order_by('due_date')
    
    # Calculate Summaries
    total_paid = fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    total_due = Decimal('0.00')
    balance_pending = Decimal('0.00')
    next_due_date = None
    
    for fee in fees:
        if fee.balance > 0:
            if not next_due_date or (fee.due_date and fee.due_date < next_due_date):
                if fee.due_date and fee.due_date >= today:
                    next_due_date = fee.due_date
            
            if fee.due_date and fee.due_date <= today:
                total_due += fee.balance
            else:
                balance_pending += fee.balance

    # If no future due dates, and still has balance, find the oldest due date
    if not next_due_date:
        overdue_fees = [f for f in fees if f.balance > 0 and f.due_date and f.due_date <= today]
        if overdue_fees:
            next_due_date = overdue_fees[0].due_date

    # Fetch grouped payments to act as combined receipts
    income_ids = FeePayment.objects.filter(student_fee__student=student, income__isnull=False).values_list('income__id', flat=True).distinct()
    incomes = Income.objects.filter(id__in=income_ids).order_by('-date')
    
    unified_receipts = []
    for inc in incomes:
        payments_for_inc = inc.fee_payments.all()
        allocated = sum(p.amount for p in payments_for_inc)
        advance = inc.amount - allocated
        
        unified_receipts.append({
            'income': inc,
            'payments': payments_for_inc,
            'advance_amount': advance
        })
    
    context = {
        'student': student,
        'fees': fees,
        'total_paid': total_paid,
        'total_due': total_due,
        'balance_pending': balance_pending,
        'next_due_date': next_due_date,
        'unified_receipts': unified_receipts,
        'page_title': f"Fees Dashboard: {student.full_name}"
    }
    return render(request, 'fees/student_fees.html', context)

@role_required(['admin', 'accountant'])
def collect_payment(request, student_id):
    """Collect lumped payment for a student and auto-allocate across pending fees."""
    student = get_object_or_404(Student, id=student_id)
    pending_fees = student.fees.filter(status__in=['due', 'partial']).order_by('due_date')
    total_due = sum(f.balance for f in pending_fees)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        remarks = request.POST.get('remarks', '')
        
        selected_fee_ids = request.POST.getlist('selected_fees')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive.")
                
            all_pending_fees = list(pending_fees)
            selected_fees = [f for f in all_pending_fees if str(f.id) in selected_fee_ids]
            unselected_fees = [f for f in all_pending_fees if str(f.id) not in selected_fee_ids]
            
            remaining_amount = amount
            payments_created = []

            # Loop 1: Distribute the amount across the selected fees
            for fee in selected_fees:
                if remaining_amount <= 0:
                    break
                    
                payment_for_this_fee = min(remaining_amount, fee.balance)
                
                payment = FeePayment.objects.create(
                    student_fee=fee,
                    amount=payment_for_this_fee,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    remarks=f"User-selected from total payment. " + remarks,
                    collected_by=request.user.username
                )
                payments_created.append(payment)
                
                fee.amount_paid += payment.amount
                fee.update_status()
                remaining_amount -= payment_for_this_fee

            # Loop 2: Distribute remaining amount across unselected fees
            for fee in unselected_fees:
                if remaining_amount <= 0:
                    break
                    
                payment_for_this_fee = min(remaining_amount, fee.balance)
                
                payment = FeePayment.objects.create(
                    student_fee=fee,
                    amount=payment_for_this_fee,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    remarks=f"Auto-allocated from remaining lumpsum payment. " + remarks,
                    collected_by=request.user.username
                )
                payments_created.append(payment)
                
                fee.amount_paid += payment.amount
                fee.update_status()
                remaining_amount -= payment_for_this_fee
                
            # Loop 3: If funds still remain, apply to UPCOMING (future) fees sorted by due date
            advance_message = ""
            advance_allocated_messages = []
            if remaining_amount > 0:
                # Get all future fees (status 'due', not yet past due, or already partial) sorted by earliest due date
                future_fees = student.fees.filter(
                    status__in=['due', 'partial']
                ).exclude(
                    id__in=[f.id for f in all_pending_fees]  # exclude already-processed fees
                ).order_by('due_date')

                for future_fee in future_fees:
                    if remaining_amount <= 0:
                        break
                    payment_for_this_fee = min(remaining_amount, future_fee.balance)
                    payment = FeePayment.objects.create(
                        student_fee=future_fee,
                        amount=payment_for_this_fee,
                        payment_method=payment_method,
                        reference_number=reference_number,
                        remarks=f"Auto-advance allocation from overpayment. " + remarks,
                        collected_by=request.user.username
                    )
                    payments_created.append(payment)
                    future_fee.amount_paid += payment.amount
                    future_fee.update_status()
                    remaining_amount -= payment_for_this_fee
                    item_name = future_fee.fee_item.name if future_fee.fee_item else 'Fee'
                    due_label = future_fee.due_date.strftime('%d/%m/%Y') if future_fee.due_date else 'upcoming'
                    advance_allocated_messages.append(f"₹{payment.amount:.2f} → {item_name} (due {due_label})")

                if advance_allocated_messages:
                    advance_message = f" Advance applied: {', '.join(advance_allocated_messages)}."

                # If still leftover after all future fees also settled, store rest as advance
                if remaining_amount > 0:
                    student.advance_balance += remaining_amount
                    student.save()
                    advance_message += f" ₹{remaining_amount:.2f} stored as Advance Balance."

            # Automatically log this in the Departmental Income ledger
            from collections import defaultdict
            dept_totals = defaultdict(Decimal)
            payments_by_dept = defaultdict(list)
            
            for payment in payments_created:
                # Assuming StudentFee.fee_item is the link to FeeItem
                # We need to ensure we can access the department
                dept = getattr(payment.student_fee.fee_item, 'department', 'academic')
                dept_totals[dept] += payment.amount
                payments_by_dept[dept].append(payment)
            
            if remaining_amount > 0:
                dept_totals['general'] += remaining_amount
            
            for dept, total_dept_amount in dept_totals.items():
                if total_dept_amount <= 0:
                    continue
                    
                # Get or create a category for this department
                cat_name = f"Student Fees ({dept.capitalize()})"
                fee_category, _ = AccountCategory.objects.get_or_create(
                    name=cat_name, 
                    type='income',
                    defaults={
                        'description': f'Automatically generated category for {dept} student fees',
                        'department': dept
                    }
                )
                
                income_record = Income.objects.create(
                    category=fee_category,
                    amount=total_dept_amount,
                    received_from=student.full_name,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    remarks=f"Departmental Collection: {dept}.{advance_message if dept == 'general' else ''} Remarks: {remarks}",
                    department=dept,
                    collected_by=request.user.username
                )
                
                # Link related payments to this specific departmental income record
                for payment in payments_by_dept[dept]:
                    payment.income = income_record
                    payment.save()
            
            messages.success(request, f"Payment of ₹{amount} collected and allocated successfully across departments.{advance_message}")
            return redirect('fees:student_fees', student_id=student.id)
        except ValueError as e:
            messages.error(request, str(e))
            
    context = {
        'student': student,
        'pending_fees': pending_fees,
        'total_due': total_due,
        'page_title': 'Collect Fee Payment'
    }
    return render(request, 'fees/collect_payment.html', context)

@role_required(['admin', 'accountant'])
def download_receipt(request, income_id):
    """Generate and return an itemized PDF/HTML receipt for a unified Income record."""
    income = get_object_or_404(Income, id=income_id)
    payments = income.fee_payments.all()
    
    # We can infer the student from the first payment. All payments in an income block belong to the same student in this app's workflow.
    student = None
    if payments.exists():
        student = payments.first().student_fee.student
    elif income.received_from:
        # if no individual payments, try to find student by name for pure advance, but less robust
        pass

    allocated_amount = sum(p.amount for p in payments)
    advance_amount = income.amount - allocated_amount
    
    context = {
        'income': income,
        'payments': payments,
        'student': student,
        'allocated_amount': allocated_amount,
        'advance_amount': advance_amount,
    }
    return render(request, 'fees/receipt.html', context)


@role_required(['admin', 'accountant'])
def add_income(request):
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            is_fee_collection = form.cleaned_data.get('is_fee_collection')
            income = form.save(commit=False)
            income.collected_by = request.user.username

            if is_fee_collection:
                student = form.cleaned_data.get('student')
                amount = form.cleaned_data.get('amount')
                
                # Fetch selected fees from array
                selected_fee_ids = request.POST.getlist('selected_fees')
                
                # Fetch all pending fees for this student, oldest due date first
                all_pending_fees = list(student.fees.filter(status__in=['due', 'partial']).order_by('due_date'))
                
                # Partition into selected and unselected preserving ordinality
                selected_fees = [f for f in all_pending_fees if str(f.id) in selected_fee_ids]
                unselected_fees = [f for f in all_pending_fees if str(f.id) not in selected_fee_ids]
                
                remaining_amount = amount
                payments_created = []
                
                # Loop 1: Pay off the selected fees first
                for fee in selected_fees:
                    if remaining_amount <= 0:
                        break
                        
                    payment_for_this_fee = min(remaining_amount, fee.balance)
                    
                    payment = FeePayment.objects.create(
                        student_fee=fee,
                        amount=payment_for_this_fee,
                        payment_method=income.payment_method,
                        reference_number=income.reference_number,
                        remarks=f"User-selected from total payment. " + income.remarks,
                        collected_by=request.user.username
                    )
                    payments_created.append(payment)
                    
                    fee.amount_paid += payment.amount
                    fee.update_status()
                    remaining_amount -= payment_for_this_fee

                # Loop 2: Pay off any remaining unselected pending fees chronologically
                for fee in unselected_fees:
                    if remaining_amount <= 0:
                        break
                        
                    payment_for_this_fee = min(remaining_amount, fee.balance)
                    
                    payment = FeePayment.objects.create(
                        student_fee=fee,
                        amount=payment_for_this_fee,
                        payment_method=income.payment_method,
                        reference_number=income.reference_number,
                        remarks=f"Auto-allocated from remaining lumpsum payment. " + income.remarks,
                        collected_by=request.user.username
                    )
                    payments_created.append(payment)
                    
                    fee.amount_paid += payment.amount
                    fee.update_status()
                    remaining_amount -= payment_for_this_fee
                    
                # Loop 3: If funds still remain, store as advance on student profile
                advance_message = ""
                if remaining_amount > 0:
                    student.advance_balance += remaining_amount
                    student.save()
                    advance_message = f" ₹{remaining_amount} added as Advance."

                # Create a single cohesive Income ledger record for the total
                fee_category = form.cleaned_data.get('category')
                income_record = Income.objects.create(
                    category=fee_category,
                    amount=amount,
                    received_from=income.received_from,
                    payment_method=income.payment_method,
                    reference_number=income.reference_number,
                    remarks=f"Allocated across {len(payments_created)} fee items.{advance_message} " + income.remarks,
                    fee_payment_ref=payments_created[0] if payments_created else None,
                    collected_by=request.user.username
                )
                
                # Link each individual payment piece to the overarching income receipt
                for payment in payments_created:
                    payment.income = income_record
                    payment.save()
                messages.success(request, f"Total payment of ₹{amount} processed successfully.{advance_message}")
            else:
                # Standard pure income
                income.save()
                messages.success(request, "Income recorded successfully.")
            return redirect('fees:dashboard')
    else:
        form = IncomeForm()

    # Get distinct active class/division combinations for the filter dropdown
    class_divisions_query = Student.objects.filter(is_active=True, enrollments__academic_year__is_active=True).values_list('enrollments__grade', 'enrollments__division__name').distinct().order_by('enrollments__grade', 'enrollments__division__name')
    class_divisions = []
    for grade, division in class_divisions_query:
        if division:
            class_divisions.append(f"{grade} - {division}")
        else:
            class_divisions.append(grade)

    context = {
        'form': form,
        'class_divisions': class_divisions,
        'page_title': 'Record Income'
    }
    return render(request, 'fees/income_form.html', context)

@role_required(['admin', 'accountant'])
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.recorded_by = request.user.username
            expense.save()
            messages.success(request, "Expense recorded successfully.")
            return redirect('fees:dashboard')
    else:
        form = ExpenseForm()

    context = {
        'form': form,
        'page_title': 'Record Expense'
    }
    return render(request, 'fees/expense_form.html', context)


from django.http import JsonResponse
from datetime import date
from .models import FeeCategory, FeeItem

@role_required(['admin', 'accountant'])
def assign_bulk_admission_fees(request):
    """Admin/Accountant action to assign admission fees to selected students"""
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        if not student_ids:
            messages.warning(request, "No students selected for fee assignment.")
            return redirect(request.META.get('HTTP_REFERER', 'fees:fees_dashboard'))

        try:
            admission_category = FeeCategory.objects.get(name__icontains='Admission')
            admission_items = FeeItem.objects.filter(category=admission_category)
            
            if not admission_items.exists():
                messages.warning(request, "No fee items found in the Admission category.")
                return redirect('fees:fee_setup_dashboard')

            students = Student.objects.filter(id__in=student_ids, is_active=True).distinct()
            assigned_count = 0
            
            for student in students:
                enrollment = student.current_enrollment 
                if not enrollment:
                    continue

                for item in admission_items:
                    # Logic: Respect targeting
                    # 1. Does it target specific grades? If so, student must be in one of them.
                    if item.applicable_grades.exists() and not item.applicable_grades.filter(id=enrollment.grade.id).exists():
                        continue
                        
                    # 2. Does it target specific divisions? If so, student must be in one of them.
                    if item.applicable_divisions.exists():
                        if not enrollment.division or not item.applicable_divisions.filter(id=enrollment.division.id).exists():
                            continue

                    # 3. Does it target specific student types?
                    if item.target_student_type != 'all':
                        if student.student_type != item.target_student_type:
                            continue

                    # Check for FeeStructure specific amount first
                    fee_struct = FeeStructure.objects.filter(
                        academic_year=enrollment.academic_year,
                        grade=enrollment.grade,
                        division=enrollment.division,
                        fee_item=item
                    ).first()

                    # Fallback to grade-only structure if division-specific not found
                    if not fee_struct and enrollment.division:
                        fee_struct = FeeStructure.objects.filter(
                            academic_year=enrollment.academic_year,
                            grade=enrollment.grade,
                            division__isnull=True,
                            fee_item=item
                        ).first()

                    amount = fee_struct.amount if fee_struct else item.default_amount
                    if amount > 0:
                        # Check for installments
                        installments = item.installment_templates.all()
                        
                        if installments.exists():
                            # Assign each installment
                            for inst in installments:
                                # Check if this specific installment is already assigned
                                inst_exists = StudentFee.objects.filter(
                                    student=student,
                                    fee_item=item,
                                    remarks__icontains=inst.name
                                ).exists()
                                
                                if not inst_exists:
                                    StudentFee.objects.create(
                                        student=student,
                                        fee_item=item,
                                        total_amount=inst.amount,
                                        due_date=inst.due_date,
                                        remarks=f"Installment: {inst.name}"
                                    )
                                    assigned_count += 1
                        else:
                            # Standard single fee item assignment
                            fee_exists = StudentFee.objects.filter(
                                student=student,
                                fee_item=item
                            ).exists()
                            
                            if not fee_exists:
                                StudentFee.objects.create(
                                    student=student,
                                    fee_item=item,
                                    total_amount=amount,
                                    due_date=date.today()
                                )
                                assigned_count += 1
            
            if assigned_count > 0:
                messages.success(request, f"Successfully assigned {assigned_count} admission fee records to existing students.")
            else:
                messages.info(request, "All students already have the admission fees assigned.")
                
        except FeeCategory.DoesNotExist:
            messages.error(request, "Admission fee category does not exist. Please create it first.")

    return redirect(request.META.get('HTTP_REFERER', 'fees:fees_dashboard'))

@role_required(['admin', 'accountant'])
def cancel_selective_admission_fees(request):
    """Admin/Accountant action to cancel admission fees for selected students"""
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        if not student_ids:
            messages.warning(request, "No students selected for fee cancellation.")
            return redirect(request.META.get('HTTP_REFERER', 'fees:fees_dashboard'))

        try:
            admission_category = FeeCategory.objects.get(name__icontains='Admission')
            admission_items = FeeItem.objects.filter(category=admission_category)
            
            if not admission_items.exists():
                messages.warning(request, "No fee items found in the Admission category.")
                return redirect('fees:fee_setup_dashboard')

            # Find fees that are unpaid (amount_paid == 0)
            fees_to_cancel = StudentFee.objects.filter(
                student_id__in=student_ids,
                fee_item__in=admission_items,
                amount_paid=0
            )
            
            cancel_count = fees_to_cancel.count()
            if cancel_count > 0:
                fees_to_cancel.delete()
                messages.success(request, f"Successfully cancelled {cancel_count} admission fee records.")
            else:
                messages.info(request, "No eligible unpaid admission fees were found for the selected students.")
                
        except FeeCategory.DoesNotExist:
            messages.error(request, "Admission fee category does not exist.")
            
    return redirect(request.META.get('HTTP_REFERER', 'fees:fees_dashboard'))

@role_required(['admin', 'accountant'])
def bulk_course_fee_update(request):
    """Bulk update interface for Course Fees across all grades/divisions"""
    from students.models import AcademicYear, Grade, Division
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    if not active_year:
        messages.error(request, "No active academic year found. Please set one up first.")
        return redirect('fees:fee_setup_dashboard')

    # Get or create the Course Fee category and item
    category, _ = FeeCategory.objects.get_or_create(name='Course Fee', defaults={'description': 'Main tuition/course fees'})
    course_fee_item, _ = FeeItem.objects.get_or_create(
        category=category, 
        name='Course Fee', 
        defaults={'default_amount': 0, 'description': 'Standard course fee for the grade'}
    )

    grades = Grade.objects.all().order_by('order', 'name')
    divisions = Division.objects.all().order_by('name')
    
    # We want a list of (Grade, Division or None)
    classrooms = []
    for g in grades:
        if g.section:
            grade_divisions = divisions.filter(section=g.section)
            if grade_divisions.exists():
                for d in grade_divisions:
                    classrooms.append({'grade': g, 'division': d})
            else:
                classrooms.append({'grade': g, 'division': None})
        else:
            classrooms.append({'grade': g, 'division': None})

    if request.method == 'POST':
        updates_count = 0
        for classroom in classrooms:
            g_id = classroom['grade'].id
            d_id = classroom['division'].id if classroom['division'] else 'none'
            input_key = f"fee_{g_id}_{d_id}"
            amount = request.POST.get(input_key)
            
            if amount is not None and amount.strip() != '':
                try:
                    amount = float(amount)
                    FeeStructure.objects.update_or_create(
                        academic_year=active_year,
                        grade=classroom['grade'],
                        division=classroom['division'],
                        fee_item=course_fee_item,
                        defaults={'amount': amount}
                    )
                    
                    # Apply this new fee amount to students currently enrolled in this class
                    from students.models import Enrollment
                    from datetime import date
                    
                    if classroom['division']:
                        enrollments = Enrollment.objects.filter(academic_year=active_year, grade=classroom['grade'], division=classroom['division'])
                    else:
                        enrollments = Enrollment.objects.filter(academic_year=active_year, grade=classroom['grade'], division__isnull=True)
                        
                    # We only bulk update if there are no complex installment templates for this item
                    if not course_fee_item.installment_templates.exists():
                        for enrollment in enrollments:
                            student = enrollment.student
                            fee, created = StudentFee.objects.get_or_create(
                                student=student,
                                fee_item=course_fee_item,
                                defaults={'total_amount': amount, 'due_date': date.today(), 'remarks': 'Automatically allocated from bulk structure update'}
                            )
                            if not created and fee.total_amount != amount:
                                fee.total_amount = amount
                                fee.update_status()
                                
                    updates_count += 1
                except (ValueError, TypeError):
                    continue
        
        messages.success(request, f"Successfully updated {updates_count} course fee structures for {active_year.name}.")
        return redirect('fees:fee_setup_dashboard')

    existing_structures = FeeStructure.objects.filter(academic_year=active_year, fee_item=course_fee_item)
    fee_map = {(fs.grade_id, fs.division_id): fs.amount for fs in existing_structures}

    from collections import defaultdict
    sections = defaultdict(list)
    for c in classrooms:
        section_name = c['grade'].section.name if c['grade'].section else "General"
        c['current_amount'] = fee_map.get((c['grade'].id, c['division'].id if c['division'] else None), 0)
        sections[section_name].append(c)

    context = {
        'sections': dict(sections),
        'active_year': active_year,
        'course_fee_item': course_fee_item,
        'page_title': 'Bulk Manage Course Fees'
    }
    return render(request, 'fees/bulk_course_fee_form.html', context)

@role_required(['admin', 'accountant'])
def manage_fee_installments(request, item_id):
    """Manage the breakdown of a FeeItem into multiple installments"""
    fee_item = get_object_or_404(FeeItem, pk=item_id)
    
    if request.method == 'POST':
        # Clear existing templates to replace them
        fee_item.installment_templates.all().delete()
        
        counts = int(request.POST.get('count', 0))
        templates_to_create = []
        
        for i in range(1, counts + 1):
            name = request.POST.get(f'name_{i}')
            date_val = request.POST.get(f'date_{i}')
            amount = request.POST.get(f'amount_{i}')
            
            if name and date_val and amount:
                templates_to_create.append(FeeInstallmentTemplate(
                    fee_item=fee_item,
                    installment_number=i,
                    name=name,
                    due_date=date_val,
                    amount=amount
                ))
        
        if templates_to_create:
            FeeInstallmentTemplate.objects.bulk_create(templates_to_create)
            messages.success(request, f"Successfully set up {len(templates_to_create)} installments for {fee_item.name}.")
        else:
            messages.info(request, "No installments were created.")
            
        return redirect('fees:fee_setup_dashboard')

    existing_templates = fee_item.installment_templates.all()
    context = {
        'fee_item': fee_item,
        'existing_templates': existing_templates,
        'page_title': f'Manage Installments: {fee_item.name}'
    }
    return render(request, 'fees/manage_installments.html', context)

@role_required(['admin', 'accountant'])
def generate_monthly_fees(request):
    """Batch generate recurring (monthly) fees for all active students"""
    from datetime import date
    from .services import generate_monthly_fees_for_all
    
    if request.method == 'POST':
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        billing_date = date(year, month, 1)
        
        created, updated = generate_monthly_fees_for_all(billing_date)
        
        messages.success(request, f"Monthly fees processed: {created} new generated, {updated} updated based on attendance.")
        return redirect('fees:fee_setup_dashboard')

    return redirect('fees:fee_setup_dashboard')

from .forms import FeeStructureForm

@role_required(['admin', 'accountant'])
def fee_structure_list(request):
    """List all specific fee variations"""
    structures = FeeStructure.objects.select_related('academic_year', 'grade', 'division', 'fee_item').all().order_by('-academic_year__name', 'grade', 'division', 'fee_item__name')
    context = {
        'structures': structures,
        'page_title': 'Grade-Specific Fee Structures'
    }
    return render(request, 'fees/fee_structure_list.html', context)

@role_required(['admin', 'accountant'])
def fee_structure_create(request):
    if request.method == 'POST':
        form = FeeStructureForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee structure created successfully.')
            return redirect('fees:fee_structure_list')
    else:
        initial = {}
        item_id = request.GET.get('item')
        if item_id:
            initial['fee_item'] = item_id
        form = FeeStructureForm(initial=initial)
    
    context = {'form': form, 'page_title': 'Add Fee Structure'}
    return render(request, 'fees/fee_structure_form.html', context)

@role_required(['admin', 'accountant'])
def fee_structure_update(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    if request.method == 'POST':
        form = FeeStructureForm(request.POST, instance=structure)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee structure updated successfully.')
            return redirect('fees:fee_structure_list')
    else:
        form = FeeStructureForm(instance=structure)
        
    context = {'form': form, 'page_title': 'Edit Fee Structure', 'is_edit': True}
    return render(request, 'fees/fee_structure_form.html', context)

@role_required(['admin', 'accountant'])
def fee_structure_delete(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    if request.method == 'POST':
        structure.delete()
        messages.success(request, 'Fee structure deleted successfully.')
        return redirect('fees:fee_structure_list')
    context = {'object': structure, 'page_title': 'Delete Fee Structure'}
    return render(request, 'fees/setup_confirm_delete.html', context)


@role_required(['admin', 'accountant'])
def get_student_fees(request, student_id):
    """API endpoint to get pending fees for a student"""
    student = get_object_or_404(Student, id=student_id)
    fees = student.fees.filter(status__in=['due', 'partial'])
    
    data = []
    for fee in fees:
        item_name = fee.fee_item.name if fee.fee_item else (fee.installment.name if fee.installment else 'General Fee')
        data.append({
            'id': fee.id,
            'name': f"{item_name} (Bal: ₹{fee.balance})",
            'balance': str(fee.balance)
        })
        
    return JsonResponse({'fees': data})

@role_required(['admin', 'accountant'])
def get_students_by_grade(request):
    """API endpoint to get students for a specific grade and division combination"""
    class_division = request.GET.get('grade')
    
    students = Student.objects.filter(is_active=True).order_by('first_name')
    if class_division:
        parts = class_division.split(' - ')
        grade = parts[0]
        if len(parts) > 1:
            division_name = parts[1]
            students = students.filter(enrollments__academic_year__is_active=True, enrollments__grade=grade, enrollments__division__name=division_name).distinct()
        else:
            students = students.filter(enrollments__academic_year__is_active=True, enrollments__grade=grade, enrollments__division__isnull=True).distinct()
            
    data = []
    for student in students:
        data.append({
            'id': student.id,
            'name': f"{student.student_id} - {student.full_name}"
        })
        
    return JsonResponse({'students': data})


from .forms import FeeCategoryForm, FeeItemForm
from .models import FeeCategory, FeeItem

@role_required(['admin', 'accountant'])
def fee_setup_dashboard(request):
    categories = FeeCategory.objects.prefetch_related('fee_items').all()
    context = {
        'categories': categories,
        'page_title': 'Fee Setup Dashboard'
    }
    return render(request, 'fees/setup_dashboard.html', context)

@role_required(['admin', 'accountant'])
def fee_category_create(request):
    if request.method == 'POST':
        form = FeeCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee Category created successfully.')
            return redirect('fees:fee_setup_dashboard')
    else:
        form = FeeCategoryForm()
    
    context = {'form': form, 'page_title': 'Add Fee Category'}
    return render(request, 'fees/setup_form.html', context)

@role_required(['admin', 'accountant'])
def fee_category_update(request, pk):
    category = get_object_or_404(FeeCategory, pk=pk)
    if request.method == 'POST':
        form = FeeCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee Category updated successfully.')
            return redirect('fees:fee_setup_dashboard')
    else:
        form = FeeCategoryForm(instance=category)
        
    context = {'form': form, 'page_title': 'Edit Fee Category', 'is_edit': True}
    return render(request, 'fees/setup_form.html', context)

@role_required(['admin', 'accountant'])
def fee_category_delete(request, pk):
    category = get_object_or_404(FeeCategory, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Fee Category deleted successfully.')
        return redirect('fees:fee_setup_dashboard')
    context = {'object': category, 'page_title': 'Delete Fee Category'}
    return render(request, 'fees/setup_confirm_delete.html', context)

@role_required(['admin', 'accountant'])
def fee_item_create(request):
    if request.method == 'POST':
        form = FeeItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee Item created successfully.')
            return redirect('fees:fee_setup_dashboard')
    else:
        initial = {}
        category_id = request.GET.get('category')
        if category_id:
            initial['category'] = category_id
        form = FeeItemForm(initial=initial)
        
    context = {'form': form, 'page_title': 'Add Fee Item'}
    return render(request, 'fees/setup_form.html', context)

@role_required(['admin', 'accountant'])
def fee_item_update(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    if request.method == 'POST':
        form = FeeItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee Item updated successfully.')
            return redirect('fees:fee_setup_dashboard')
    else:
        form = FeeItemForm(instance=item)
        
    context = {'form': form, 'page_title': 'Edit Fee Item', 'is_edit': True}
    return render(request, 'fees/setup_form.html', context)

@role_required(['admin', 'accountant'])
def fee_item_delete(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Fee Item deleted successfully.')
        return redirect('fees:fee_setup_dashboard')
    context = {'object': item, 'page_title': 'Delete Fee Item'}
    return render(request, 'fees/setup_confirm_delete.html', context)

@role_required(['admin', 'accountant'])
def day_book(request):
    """Chronological list of all financial transactions."""
    from django.db.models import Value, CharField
    from django.utils import timezone
    
    start_date = request.GET.get('start_date', timezone.now().date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    incomes = Income.objects.filter(date__range=[start_date, end_date]).annotate(
        trans_type=Value('income', output_field=CharField())
    )
    expenses = Expense.objects.filter(date__range=[start_date, end_date]).annotate(
        trans_type=Value('expense', output_field=CharField())
    )
    
    # Combine and sort
    from itertools import chain
    transactions = sorted(
        chain(incomes, expenses),
        key=lambda x: (x.date, x.id),
        reverse=True
    )
    
    total_in = Sum(i.amount for i in incomes) # Note: Sum aggregation on queryset is faster but this works for context
    total_in = incomes.aggregate(Sum('amount'))['amount__sum'] or 0
    total_out = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'transactions': transactions,
        'start_date': start_date,
        'end_date': end_date,
        'total_in': total_in,
        'total_out': total_out,
        'net': total_in - total_out,
        'page_title': 'Day Book'
    }
    return render(request, 'fees/day_book.html', context)

@role_required(['admin', 'accountant'])
def ledger_book(request):
    """Ledger view: Financials grouped by AccountCategory."""
    categories = AccountCategory.objects.annotate(
        total_amount=Sum(
            Case(
                When(type='income', then='incomes__amount'),
                When(type='expense', then='expenses__amount'),
                output_field=DecimalField()
            )
        )
    ).filter(total_amount__isnull=False).order_by('type', 'name')
    
    # Detail view if category is selected
    selected_cat_id = request.GET.get('category')
    selected_cat = None
    ledger_entries = []
    if selected_cat_id:
        # Use the annotated queryset so total_amount is available in the template
        selected_cat = categories.filter(id=selected_cat_id).first()
        if not selected_cat:
            selected_cat = AccountCategory.objects.filter(id=selected_cat_id).first()
        if selected_cat:
            if selected_cat.type == 'income':
                ledger_entries = selected_cat.incomes.all().order_by('-date')
            else:
                ledger_entries = selected_cat.expenses.all().order_by('-date')
            
    context = {
        'categories': categories,
        'selected_cat': selected_cat,
        'ledger_entries': ledger_entries,
        'page_title': 'Ledger Book'
    }
    return render(request, 'fees/ledger_book.html', context)

@role_required(['admin', 'accountant'])
def finance_report(request):
    """Profit and Loss / Monthly Performance Report."""
    from django.utils import timezone
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    
    incomes = Income.objects.filter(date__month=month, date__year=year)
    expenses = Expense.objects.filter(date__month=month, date__year=year)
    
    inc_total = incomes.aggregate(Sum('amount'))['amount__sum'] or 0
    exp_total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Categorized breakdown for P&L
    inc_breakdown = AccountCategory.objects.filter(type='income').annotate(
        total=Sum('incomes__amount', filter=Q(incomes__date__month=month, incomes__date__year=year))
    ).filter(total__gt=0)
    
    exp_breakdown = AccountCategory.objects.filter(type='expense').annotate(
        total=Sum('expenses__amount', filter=Q(expenses__date__month=month, expenses__date__year=year))
    ).filter(total__gt=0)
    
    context = {
        'month': month,
        'year': year,
        'inc_total': inc_total,
        'exp_total': exp_total,
        'profit': inc_total - exp_total,
        'inc_breakdown': inc_breakdown,
        'exp_breakdown': exp_breakdown,
        'page_title': 'Finance Performance Report'
    }
    return render(request, 'fees/finance_report.html', context)

@role_required(['admin', 'accountant'])
def departmental_dashboard(request):
    """Comparative Profit & Loss dashboard for Academic vs Hostel departments."""
    from django.db.models import Sum, Q, DecimalField, Case, When
    
    # Financial aggregate by department
    def get_dept_financials(dept):
        inc = Income.objects.filter(department=dept).aggregate(total=Sum('amount'))['total'] or 0
        exp = Expense.objects.filter(department=dept).aggregate(total=Sum('amount'))['total'] or 0
        return {
            'income': inc,
            'expense': exp,
            'profit': inc - exp
        }
    
    academic = get_dept_financials('academic')
    hostel = get_dept_financials('hostel')
    general = get_dept_financials('general')
    
    # Total institution-wide
    total_income = academic['income'] + hostel['income'] + general['income']
    total_expense = academic['expense'] + hostel['expense'] + general['expense']
    
    # Category break down by department
    cat_summary = AccountCategory.objects.annotate(
        inc_total=Sum('incomes__amount'),
        exp_total=Sum('expenses__amount')
    ).filter(Q(inc_total__gt=0) | Q(exp_total__gt=0)).order_by('department', 'name')
    
    context = {
        'academic': academic,
        'hostel': hostel,
        'general': general,
        'total_income': total_income,
        'total_expense': total_expense,
        'overall_profit': total_income - total_expense,
        'cat_summary': cat_summary,
        'page_title': 'Departmental Accounting'
    }
    return render(request, 'fees/departmental_dashboard.html', context)

from .forms import BusStopForm
from .models import BusStop

@role_required(['admin', 'accountant'])
def bus_stop_list(request):
    """List all bus stops."""
    bus_stops = BusStop.objects.all().order_by('stop_name')
    context = {'bus_stops': bus_stops, 'page_title': 'Manage Bus Stops'}
    return render(request, 'fees/bus_stop_list.html', context)

@role_required(['admin', 'accountant'])
def bus_stop_create(request):
    """Create a new bus stop."""
    if request.method == 'POST':
        form = BusStopForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bus stop created successfully.')
            return redirect('fees:bus_stop_list')
    else:
        form = BusStopForm()
    
    context = {'form': form, 'page_title': 'Add Bus Stop'}
    return render(request, 'fees/bus_stop_form.html', context)

@role_required(['admin', 'accountant'])
def bus_stop_update(request, pk):
    """Edit an existing bus stop."""
    bus_stop = get_object_or_404(BusStop, pk=pk)
    if request.method == 'POST':
        form = BusStopForm(request.POST, instance=bus_stop)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bus stop updated successfully.')
            return redirect('fees:bus_stop_list')
    else:
        form = BusStopForm(instance=bus_stop)
        
    context = {'form': form, 'page_title': 'Edit Bus Stop', 'is_edit': True}
    return render(request, 'fees/bus_stop_form.html', context)

@role_required(['admin', 'accountant'])
def bus_stop_delete(request, pk):
    """Delete a bus stop."""
    bus_stop = get_object_or_404(BusStop, pk=pk)
    if request.method == 'POST':
        bus_stop.delete()
        messages.success(request, 'Bus stop deleted successfully.')
        return redirect('fees:bus_stop_list')
        
    context = {'object': bus_stop, 'page_title': 'Delete Bus Stop'}
    return render(request, 'fees/setup_confirm_delete.html', context)

@role_required(['admin', 'accountant'])
def monthly_fee_adjustment(request):
    """Interface to list generated monthly fees and allow manual adjustment based on present days."""
    from students.models import AcademicYear
    from .models import StudentFee
    import datetime
    
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    # Process AJAX update
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        fee_id = request.POST.get('fee_id')
        present_days = request.POST.get('present_days')
        
        try:
            fee = StudentFee.objects.get(id=fee_id)
            if fee.fee_item and fee.fee_item.is_monthly:
                present_days = int(present_days)
                fee.present_days = present_days
                
                # Apply the 40/80/100 logic (matching services.py logic or user request)
                from .services import calculate_prorated_percentage
                # If the user enters present days manually, we can use the same calculation
                percentage = calculate_prorated_percentage(present_days)
                fee.prorated_percentage = percentage
                
                # Default amount calculation points to what the item initially cost
                base_amount = fee.fee_item.default_amount
                if fee.remarks.startswith("Vehicle Fee") and fee.student.bus_stop:
                    base_amount = fee.student.bus_stop.fee_amount
                
                from decimal import Decimal
                new_total = (base_amount * percentage) / Decimal('100.00')
                
                fee.total_amount = new_total
                fee.update_status()
                fee.save()
                
                return JsonResponse({'success': True, 'new_total': float(new_total), 'percentage': float(percentage)})
            else:
                return JsonResponse({'success': False, 'message': 'Not a monthly fee.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    # GET request - list fees
    month = request.GET.get('month', datetime.date.today().month)
    year = request.GET.get('year', datetime.date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = datetime.date.today().month
        year = datetime.date.today().year
        
    target_date = datetime.date(year, month, 1)
    
    monthly_fees = StudentFee.objects.filter(
        billing_month=target_date,
        fee_item__is_monthly=True
    ).select_related('student', 'fee_item')
    
    # Filter by category if requested
    fee_type = request.GET.get('type')
    if fee_type == 'hostel':
        monthly_fees = monthly_fees.filter(fee_item__name__icontains='Hostel')
    elif fee_type == 'vehicle':
        monthly_fees = monthly_fees.filter(fee_item__name__icontains='Bus')
        
    context = {
        'page_title': 'Monthly Fee Adjustments',
        'monthly_fees': monthly_fees,
        'current_month': month,
        'current_year': year,
        'fee_type': fee_type
    }
    return render(request, 'fees/monthly_adjustment.html', context)

@role_required(['admin', 'accountant'])
def add_custom_fee(request, student_id):
    """Manually assign any custom fee to a student."""
    student = get_object_or_404(Student, id=student_id)
    # Get all non-monthly fee items that can be assigned manually
    fee_items = FeeItem.objects.filter(is_monthly=False).order_by('category__name', 'name')
    
    if request.method == 'POST':
        item_id = request.POST.get('fee_item')
        amount = request.POST.get('amount')
        remarks = request.POST.get('remarks', '')
        due_date = request.POST.get('due_date') or timezone.now().date()
        
        try:
            fee_item = get_object_or_404(FeeItem, id=item_id)
            amount = Decimal(amount)
            if amount < 0:
                raise ValueError("Amount cannot be negative.")
                
            StudentFee.objects.create(
                student=student,
                fee_item=fee_item,
                total_amount=amount,
                due_date=due_date,
                remarks=remarks
            )
            messages.success(request, f"{fee_item.name} of ₹{amount} assigned to {student.full_name}.")
            return redirect('fees:student_fees', student_id=student.id)
        except (ValueError, Decimal.InvalidOperation) as e:
            messages.error(request, f"Invalid data: {str(e)}")
            
    context = {
        'student': student,
        'fee_items': fee_items,
        'page_title': f"Add Custom Fee: {student.full_name}"
    }
    return render(request, 'fees/custom_fee_form.html', context)


@role_required(['admin', 'accountant', 'student'])
def print_payment_history(request, student_id):
    """Printable complete payment history for a student."""
    # Data isolation for student role
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not request.user.profile.student_record or request.user.profile.student_record.id != int(student_id):
            messages.error(request, "You do not have permission to view other students' details.")
            return redirect('students:home')

    student = get_object_or_404(Student, id=student_id)
    from django.utils import timezone
    today = timezone.now().date()

    # All fees ever assigned to this student
    fees = student.fees.all().order_by('due_date')

    # All payment transactions
    income_ids = FeePayment.objects.filter(
        student_fee__student=student, income__isnull=False
    ).values_list('income__id', flat=True).distinct()
    incomes = Income.objects.filter(id__in=income_ids).order_by('date')

    receipts = []
    for inc in incomes:
        payments_for_inc = inc.fee_payments.all()
        allocated = sum(p.amount for p in payments_for_inc)
        advance = inc.amount - allocated
        receipts.append({
            'income': inc,
            'payments': payments_for_inc,
            'advance_amount': advance,
        })

    total_charged = fees.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_paid = fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_balance = sum(f.balance for f in fees)

    context = {
        'student': student,
        'fees': fees,
        'receipts': receipts,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'today': today,
        'page_title': f"Payment History: {student.full_name}",
    }
    return render(request, 'fees/payment_history_print.html', context)
