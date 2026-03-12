from django.shortcuts import render, get_object_or_404, redirect
from students.decorators import role_required
from django.contrib import messages
from .models import StudentFee, FeePayment, AccountCategory, Income, Expense
from students.models import Student
from django.db.models import Sum
from .forms import IncomeForm, ExpenseForm

# We might want to restrict this to 'accountant' or 'admin' later.
@role_required(['admin', 'accountant'])
def dashboard(request):
    """Accountant Dashboard showing Income, Expense, and Student Fees."""
    # Income/Expense Summary
    total_income = Income.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_expense = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    net_balance = total_income - total_expense

    recent_incomes = Income.objects.all().order_by('-date')[:5]
    recent_expenses = Expense.objects.all().order_by('-date')[:5]

    # Student Filtering
    class_filter = request.GET.get('class_filter', '')
    type_filter = request.GET.get('type_filter', '')
    
    students = Student.objects.filter(is_active=True)
    
    if class_filter:
        parts = class_filter.split(' - ')
        grade = parts[0]
        if len(parts) > 1:
            division_name = parts[1]
            students = students.filter(enrollments__academic_year__is_active=True, enrollments__grade=grade, enrollments__division__name=division_name).distinct()
        else:
            students = students.filter(enrollments__academic_year__is_active=True, enrollments__grade=grade, enrollments__division__isnull=True).distinct()
            
    if type_filter:
        students = students.filter(student_type=type_filter)
        
    student_data = []
    
    for student in students:
        fees = student.fees.all()
        total_due = sum(f.balance for f in fees if f.balance > 0)
        
        # Always append the student, even if total_due is 0
        student_data.append({
            'student': student,
            'total_due': total_due,
        })
            
    # Get distinct active class/division combinations for the filter dropdown
    class_divisions_query = Student.objects.filter(is_active=True, enrollments__academic_year__is_active=True).values_list('enrollments__grade', 'enrollments__division__name').distinct().order_by('enrollments__grade', 'enrollments__division__name')
    class_divisions = []
    for grade, division in class_divisions_query:
        if division:
            class_divisions.append(f"{grade} - {division}")
        else:
            class_divisions.append(grade)
        
    context = {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_balance': net_balance,
        'recent_incomes': recent_incomes,
        'recent_expenses': recent_expenses,
        'student_data': student_data,
        'class_divisions': class_divisions,
        'current_class_filter': class_filter,
        'current_type_filter': type_filter,
        'page_title': 'Accounts Dashboard'
    }
    return render(request, 'fees/dashboard.html', context)

@role_required(['admin', 'accountant', 'student'])
def student_fees(request, student_id):
    """View all fees for a specific student."""
    # Data isolation for students
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        if not request.user.profile.student_record or request.user.profile.student_record.id != int(student_id):
            messages.error(request, "You do not have permission to view other students' fee details.")
            return redirect('students:home')
            
    student = get_object_or_404(Student, id=student_id)
    fees = student.fees.all()
    
    # Fetch grouped payments to act as combined receipts
    # We can fetch all unique Income records tied to this student's fee payments
    income_ids = FeePayment.objects.filter(student_fee__student=student, income__isnull=False).values_list('income__id', flat=True).distinct()
    incomes = Income.objects.filter(id__in=income_ids).order_by('-date')
    
    unified_receipts = []
    for inc in incomes:
        # Get all payments associated with this specific income receipt
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
        'unified_receipts': unified_receipts,
        'page_title': f"Fees for {student.full_name}"
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
            amount = float(amount)
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
                
            # Loop 3: If funds still remain, store as advance on student profile
            advance_message = ""
            if remaining_amount > 0:
                student.advance_balance += remaining_amount
                student.save()
                advance_message = f" ₹{remaining_amount:.2f} added as Advance."

            # Automatically log this in the general Income ledger
            fee_category, _ = AccountCategory.objects.get_or_create(
                name="Student Fees", 
                type="income",
                defaults={'description': 'Automatically generated category for student fees'}
            )
            income_record = Income.objects.create(
                category=fee_category,
                amount=amount,
                received_from=student.full_name,
                payment_method=payment_method,
                reference_number=reference_number,
                remarks=f"Mass Collection across {len(payments_created)} fees.{advance_message} Remarks: {remarks}",
                fee_payment_ref=payments_created[0] if payments_created else None,
                collected_by=request.user.username
            )
            
            # Now update all generated FeePayments to link to this overarching Income record
            for payment in payments_created:
                payment.income = income_record
                payment.save()
            
            messages.success(request, f"Payment of ₹{amount} collected and allocated successfully.{advance_message}")
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
    """Admin/Accountant action to assign admission fees to all current students"""
    if request.method == 'POST':
        try:
            admission_category = FeeCategory.objects.get(name__icontains='Admission')
            admission_items = FeeItem.objects.filter(category=admission_category)
            
            if not admission_items.exists():
                messages.warning(request, "No fee items found in the Admission category.")
                return redirect('fees:dashboard')

            students = Student.objects.all()
            assigned_count = 0
            
            for student in students:
                for item in admission_items:
                    if item.default_amount > 0:
                        # Check if this specific fee item is already assigned to this student
                        fee_exists = StudentFee.objects.filter(
                            student=student,
                            fee_item=item
                        ).exists()
                        
                        if not fee_exists:
                            StudentFee.objects.create(
                                student=student,
                                fee_item=item,
                                total_amount=item.default_amount,
                                due_date=date.today()
                            )
                            assigned_count += 1
            
            if assigned_count > 0:
                messages.success(request, f"Successfully assigned {assigned_count} admission fee records to existing students.")
            else:
                messages.info(request, "All students already have the admission fees assigned.")
                
        except FeeCategory.DoesNotExist:
            messages.error(request, "Admission fee category does not exist. Please create it first.")

    return redirect('fees:dashboard')


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

