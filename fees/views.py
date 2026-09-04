from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q, Count
from django.views.decorators.http import require_POST
from decimal import Decimal
from datetime import date, datetime, timedelta
import calendar
import json

from students.decorators import role_required
from students.models import Student, Grade, Division, AcademicYear
from .models import (
    FeeCategory, FeeItem, FeeStructure, CourseInstallment, StudentFee,
    ReceiptTransaction, FeePayment, CautionDeposit, CautionDepositRefund,
    AccountCategory, Income, Expense, BusStop, InstitutionPaymentSetting
)
from .services import (
    sync_student_monthly_dues, batch_generate_monthly_fees,
    add_adhoc_charge, assign_admission_essentials,
    record_fee_payment, process_caution_refund,
    get_financial_summary, get_or_create_default_categories,
    apply_fee_reduction
)


@login_required
@role_required(['admin', 'accountant'])
def finance_dashboard(request):
    """Clean, high-level control panel for institutional accounts and fee operations."""
    today = date.today()
    curr_year = today.year
    curr_month = today.month
    
    # 1. Today's Collections & Movements
    today_incomes = Income.objects.filter(date=today)
    today_income_total = today_incomes.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    today_receipts_count = ReceiptTransaction.objects.filter(date=today).count()
    
    today_expenses = Expense.objects.filter(date=today)
    today_expense_total = today_expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    
    # 2. This Month's Figures
    first_of_month = date(curr_year, curr_month, 1)
    month_incomes = Income.objects.filter(date__gte=first_of_month, date__lte=today)
    month_income_total = month_incomes.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    
    month_expenses = Expense.objects.filter(date__gte=first_of_month, date__lte=today)
    month_expense_total = month_expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    
    month_net = month_income_total - month_expense_total
    
    # 3. Overall Student Dues Summary
    total_due_balance = StudentFee.objects.filter(status__in=['due', 'partial']).aggregate(
        b=Sum('total_amount') - Sum('concession_amount') - Sum('amount_paid')
    )['b'] or Decimal('0.00')
    
    # 4. Recent Transactions
    recent_receipts = ReceiptTransaction.objects.select_related('student').order_by('-date', '-id')[:6]
    recent_expenses = Expense.objects.select_related('category').order_by('-date', '-id')[:6]
    
    context = {
        'page_title': 'Office Finance & Fees',
        'today': today,
        'today_income_total': today_income_total,
        'today_expense_total': today_expense_total,
        'today_receipts_count': today_receipts_count,
        'month_income_total': month_income_total,
        'month_expense_total': month_expense_total,
        'month_net': month_net,
        'total_due_balance': max(Decimal('0.00'), total_due_balance),
        'recent_receipts': recent_receipts,
        'recent_expenses': recent_expenses,
    }
    return render(request, 'fees/finance_dashboard.html', context)


@login_required
@role_required(['admin', 'accountant'])
def fee_counter(request):
    """Instant student search and dues overview for office fee collection counter."""
    search_query = request.GET.get('q', '').strip()
    grade_id = request.GET.get('grade')
    division_id = request.GET.get('division')
    student_type = request.GET.get('student_type')
    
    students_qs = Student.objects.filter(is_active=True).select_related('bus_stop')
    
    if search_query:
        students_qs = students_qs.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(student_id__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
        
    if grade_id:
        students_qs = students_qs.filter(enrollments__grade_id=grade_id, enrollments__academic_year__is_active=True)
    if division_id:
        students_qs = students_qs.filter(enrollments__division_id=division_id, enrollments__academic_year__is_active=True)
    if student_type:
        students_qs = students_qs.filter(student_type=student_type)

    students_qs = students_qs.distinct().order_by('first_name', 'last_name')[:40]
    
    # Annotate total due balance for each student in the list
    student_list = []
    for st in students_qs:
        fees = st.fees.filter(status__in=['due', 'partial'])
        due_sum = Decimal('0.00')
        for f in fees:
            due_sum += f.balance
        student_list.append({
            'student': st,
            'total_due': due_sum,
            'has_due': due_sum > 0,
            'enrollment': st.current_enrollment
        })

    grades = Grade.objects.all().order_by('order', 'name')
    divisions = Division.objects.all().order_by('name')

    context = {
        'page_title': 'Fee Collection Counter',
        'student_list': student_list,
        'search_query': search_query,
        'grades': grades,
        'divisions': divisions,
        'selected_grade': int(grade_id) if grade_id else None,
        'selected_division': int(division_id) if division_id else None,
        'selected_type': student_type,
    }
    return render(request, 'fees/fee_counter.html', context)


@login_required
def student_fee_detail(request, student_id):
    """
    Detailed fee collection & account statement for a specific student.
    Automatically syncs and accumulates recurring monthly dues (Hostel & Bus).
    """
    student = get_object_or_404(Student, id=student_id)
    
    # Permission check: superuser, admin, accountant, teacher or the student themselves
    if not request.user.is_superuser:
        user_profile = getattr(request.user, 'profile', None)
        user_role = getattr(user_profile, 'role', None) if user_profile else None
        if user_role not in ['admin', 'accountant', 'teacher']:
            if user_role == 'student':
                if not user_profile.student_record or user_profile.student_record.id != student.id:
                    raise PermissionDenied("You do not have permission to view this fee ledger.")
            else:
                raise PermissionDenied("You do not have permission to view this page.")

    # Automatically synchronize elapsed monthly recurring fees up to today
    sync_student_monthly_dues(student)
    
    all_fees = student.fees.all().select_related('fee_item', 'fee_item__category', 'installment').order_by('due_date', 'id')
    
    # Calculate account aggregates
    total_billed = Decimal('0.00')
    total_concessions = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_due = Decimal('0.00')
    
    # Categorize dues cleanly
    course_fees = []
    hostel_fees = []
    bus_fees = []
    admission_fees = []
    caution_fees = []
    adhoc_fees = []
    
    for f in all_fees:
        total_billed += f.total_amount
        total_concessions += f.concession_amount
        total_paid += f.amount_paid
        total_due += f.balance
        
        ft = f.fee_item.fee_type if f.fee_item else 'other'
        if ft == 'hostel':
            hostel_fees.append(f)
        elif ft == 'bus':
            bus_fees.append(f)
        elif ft == 'course' or f.installment:
            course_fees.append(f)
        elif ft == 'admission':
            admission_fees.append(f)
        elif ft == 'caution':
            caution_fees.append(f)
        else:
            adhoc_fees.append(f)

    # Recent receipts for this student
    receipts = student.receipt_transactions.all().order_by('-date', '-id')

    fee_groups = [
        ('Course & Term Fees', course_fees),
        ('Monthly Hostel Fees', hostel_fees),
        ('Monthly Bus Fees', bus_fees),
        ('Admission Essentials', admission_fees),
        ('Caution Deposit', caution_fees),
        ('Ad-hoc & Other Dues', adhoc_fees),
    ]

    context = {
        'page_title': f'Fee Ledger - {student.full_name}',
        'student': student,
        'enrollment': student.current_enrollment,
        'all_fees': all_fees,
        'total_billed': total_billed,
        'total_concessions': total_concessions,
        'total_paid': total_paid,
        'total_due': total_due,
        'fee_groups': fee_groups,
        'course_fees': course_fees,
        'hostel_fees': hostel_fees,
        'bus_fees': bus_fees,
        'admission_fees': admission_fees,
        'caution_fees': caution_fees,
        'adhoc_fees': adhoc_fees,
        'receipts': receipts,
        'payment_settings': InstitutionPaymentSetting.get_settings(),
        'today': date.today(),
    }
    return render(request, 'fees/student_fee_detail.html', context)


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def apply_fee_reduction_submit(request, student_id):
    """Applies a fee reduction/waiver (e.g. not used bus, not used hostel, partial days) to a specific fee."""
    student = get_object_or_404(Student, id=student_id)
    fee_id = request.POST.get('fee_id')
    reduction_type = request.POST.get('reduction_type', 'fixed')  # full, fixed, percent, days, reset
    value_str = request.POST.get('reduction_value', '0').strip()
    reason_preset = request.POST.get('reason_preset', '').strip()
    reason_custom = request.POST.get('reason_custom', '').strip()
    present_days_str = request.POST.get('present_days', '').strip()
    total_days_str = request.POST.get('total_days', '30').strip()

    if not fee_id:
        messages.error(request, "Please select a fee item to apply reduction.")
        return redirect('fees:student_fee_detail', student_id=student.id)

    fee = get_object_or_404(StudentFee, id=fee_id, student=student)
    reason = reason_custom if reason_custom else reason_preset

    try:
        value = Decimal(value_str or '0')
    except Exception:
        value = Decimal('0.00')

    present_days = int(present_days_str) if present_days_str.isdigit() else None
    total_days = int(total_days_str) if total_days_str.isdigit() else 30

    apply_fee_reduction(
        student_fee=fee,
        reduction_type=reduction_type,
        value=value,
        reason=reason,
        present_days=present_days,
        total_days=total_days
    )

    if reduction_type == 'reset':
        messages.success(request, f"Fee reduction cleared for '{fee.display_title}'.")
    else:
        if fee.billing_month:
            messages.success(request, f"Fee reduction of ₹{fee.concession_amount:.2f} applied to {fee.fee_item.name if fee.fee_item else 'Fee'} strictly for {fee.billing_month.strftime('%B %Y')} only. Reason: {reason or 'Fee Concession'}")
        else:
            messages.success(request, f"Fee reduction of ₹{fee.concession_amount:.2f} applied to '{fee.display_title}'. Reason: {reason or 'Fee Concession'}")

    return redirect('fees:student_fee_detail', student_id=student.id)


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def add_adhoc_fee_submit(request, student_id):
    """Add an ad-hoc charge (medical, outside order, store borrow, etc.) directly to student."""
    student = get_object_or_404(Student, id=student_id)
    title = request.POST.get('title', '').strip()
    amount_str = request.POST.get('amount', '0').strip()
    remarks = request.POST.get('remarks', '').strip()
    due_date_str = request.POST.get('due_date')
    
    if not title:
        messages.error(request, "Please enter a charge title or reason.")
        return redirect('fees:student_fee_detail', student_id=student.id)
        
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError()
    except Exception:
        messages.error(request, "Please enter a valid positive charge amount.")
        return redirect('fees:student_fee_detail', student_id=student.id)

    due_d = None
    if due_date_str:
        try:
            due_d = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    add_adhoc_charge(student, title, amount, remarks=remarks, due_date=due_d)
    messages.success(request, f"Ad-hoc charge '{title}' of ₹{amount} added successfully.")
    return redirect('fees:student_fee_detail', student_id=student.id)


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def collect_payment_submit(request, student_id):
    """Processes fee collection and generates a printable receipt."""
    student = get_object_or_404(Student, id=student_id)
    payment_method = request.POST.get('payment_method', 'cash')
    reference_number = request.POST.get('reference_number', '').strip()
    remarks = request.POST.get('remarks', '').strip()
    collector = request.user.get_full_name() or request.user.username
    
    # Read selected items and amounts
    selected_fee_ids = request.POST.getlist('selected_fees')
    if not selected_fee_ids:
        messages.error(request, "No fee items were selected for payment.")
        return redirect('fees:student_fee_detail', student_id=student.id)

    fee_allocations = []
    for sf_id in selected_fee_ids:
        pay_str = request.POST.get(f'pay_amount_{sf_id}', '0').strip()
        conc_str = request.POST.get(f'concession_{sf_id}', '0').strip()
        try:
            pay_amt = Decimal(pay_str or '0')
            conc_amt = Decimal(conc_str or '0')
            if pay_amt > 0 or conc_amt > 0:
                fee_allocations.append({
                    'fee_id': int(sf_id),
                    'amount': pay_amt,
                    'concession': conc_amt
                })
        except Exception:
            continue

    if not fee_allocations:
        messages.error(request, "Please enter valid payment amounts for the selected items.")
        return redirect('fees:student_fee_detail', student_id=student.id)

    try:
        receipt_tx = record_fee_payment(
            student=student,
            fee_allocations=fee_allocations,
            payment_method=payment_method,
            reference_number=reference_number,
            collected_by=collector,
            remarks=remarks
        )
        messages.success(request, f"Payment of ₹{receipt_tx.total_amount} recorded successfully. Receipt generated.")
        return redirect('fees:print_receipt', receipt_id=str(receipt_tx.transaction_id))
    except Exception as e:
        messages.error(request, f"Failed to process payment: {str(e)}")
        return redirect('fees:student_fee_detail', student_id=student.id)


@login_required
def print_receipt(request, receipt_id):
    """Clean, gentle, printable receipt voucher."""
    receipt = get_object_or_404(ReceiptTransaction, transaction_id=receipt_id)
    payments = receipt.fee_payments.all().select_related('student_fee', 'student_fee__fee_item', 'student_fee__installment')
    student = receipt.student
    
    # Calculate student's overall remaining balance after this payment
    total_remaining = Decimal('0.00')
    for f in student.fees.filter(status__in=['due', 'partial']):
        total_remaining += f.balance

    context = {
        'receipt': receipt,
        'payments': payments,
        'student': student,
        'enrollment': student.current_enrollment,
        'total_remaining': total_remaining,
        'page_title': f'Receipt - {receipt.student.full_name}',
    }
    return render(request, 'fees/receipt_print.html', context)


@login_required
@role_required(['admin', 'accountant'])
def batch_monthly_billing(request):
    """Batch generator for monthly hostel and bus dues across all students."""
    today = date.today()
    if request.method == 'POST':
        month_val = int(request.POST.get('month', today.month))
        year_val = int(request.POST.get('year', today.year))
        billing_date = date(year_val, month_val, 1)
        
        result = batch_generate_monthly_fees(billing_date)
        messages.success(
            request,
            f"Generated {result['total_count']} monthly dues for {billing_date.strftime('%B %Y')} "
            f"(Hostel: {result['hostel_count']}, Bus: {result['bus_count']}) amounting to ₹{result['total_amount']}."
        )
        return redirect('fees:batch_monthly_billing')

    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = [today.year - 1, today.year, today.year + 1]

    context = {
        'page_title': 'Monthly Fee Batch Generator',
        'months': months,
        'years': years,
        'current_month': today.month,
        'current_year': today.year,
    }
    return render(request, 'fees/batch_monthly_billing.html', context)


# ==========================================
# GENERAL INCOMES & EXPENSES (OFFICE FINANCE)
# ==========================================

@login_required
@role_required(['admin', 'accountant'])
def income_list(request):
    """List of all office incomes with category & date filters."""
    incomes = Income.objects.select_related('category').order_by('-date', '-id')
    
    cat_id = request.GET.get('category')
    start_d = request.GET.get('start_date')
    end_d = request.GET.get('end_date')
    
    if cat_id:
        incomes = incomes.filter(category_id=cat_id)
    if start_d:
        incomes = incomes.filter(date__gte=start_d)
    if end_d:
        incomes = incomes.filter(date__lte=end_d)

    total_amount = incomes.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    categories = AccountCategory.objects.filter(type='income').order_by('name')

    context = {
        'page_title': 'Income Register',
        'incomes': incomes[:100],
        'total_amount': total_amount,
        'categories': categories,
        'selected_category': int(cat_id) if cat_id else None,
        'start_date': start_d,
        'end_date': end_d,
    }
    return render(request, 'fees/income_list.html', context)


@login_required
@role_required(['admin', 'accountant'])
def income_create(request):
    """Create a manual income entry (donations, grants, canteen rent, sponsorships, etc.)."""
    categories = AccountCategory.objects.filter(type='income').order_by('name')
    if not categories.exists():
        AccountCategory.objects.create(name='General Donations', type='income')
        AccountCategory.objects.create(name='Institutional Grants', type='income')
        AccountCategory.objects.create(name='Canteen / Store Rent', type='income')
        categories = AccountCategory.objects.filter(type='income').order_by('name')

    if request.method == 'POST':
        cat_id = request.POST.get('category')
        amount_str = request.POST.get('amount', '0')
        received_from = request.POST.get('received_from', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, "Please enter a valid positive income amount.")
            return render(request, 'fees/income_form.html', {'categories': categories})

        cat = get_object_or_404(AccountCategory, id=cat_id, type='income')
        collector = request.user.get_full_name() or request.user.username
        
        Income.objects.create(
            category=cat,
            amount=amount,
            received_from=received_from or "Direct Deposit",
            payment_method=payment_method,
            reference_number=reference_number,
            remarks=remarks,
            collected_by=collector,
            department=cat.department
        )
        messages.success(request, f"Income of ₹{amount} recorded successfully under {cat.name}.")
        return redirect('fees:income_list')

    return render(request, 'fees/income_form.html', {'categories': categories, 'page_title': 'Add Income Entry'})


@login_required
@role_required(['admin', 'accountant'])
def expense_list(request):
    """List of all office expenses with category & date filters."""
    expenses = Expense.objects.select_related('category').order_by('-date', '-id')
    
    cat_id = request.GET.get('category')
    start_d = request.GET.get('start_date')
    end_d = request.GET.get('end_date')
    
    if cat_id:
        expenses = expenses.filter(category_id=cat_id)
    if start_d:
        expenses = expenses.filter(date__gte=start_d)
    if end_d:
        expenses = expenses.filter(date__lte=end_d)

    total_amount = expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    categories = AccountCategory.objects.filter(type='expense').order_by('name')

    context = {
        'page_title': 'Expense Register',
        'expenses': expenses[:100],
        'total_amount': total_amount,
        'categories': categories,
        'selected_category': int(cat_id) if cat_id else None,
        'start_date': start_d,
        'end_date': end_d,
    }
    return render(request, 'fees/expense_list.html', context)


@login_required
@role_required(['admin', 'accountant'])
def expense_create(request):
    """Create a manual office expense voucher."""
    categories = AccountCategory.objects.filter(type='expense').order_by('name')
    if not categories.exists():
        AccountCategory.objects.create(name='Staff Salaries', type='expense')
        AccountCategory.objects.create(name='Hostel Food & Mess Grocery', type='expense', department='hostel')
        AccountCategory.objects.create(name='Electricity & Water Bills', type='expense')
        AccountCategory.objects.create(name='Diesel & Vehicle Maintenance', type='expense')
        AccountCategory.objects.create(name='Stationery & Printing', type='expense')
        AccountCategory.objects.create(name='Building Repairs & Maintenance', type='expense')
        categories = AccountCategory.objects.filter(type='expense').order_by('name')

    if request.method == 'POST':
        cat_id = request.POST.get('category')
        amount_str = request.POST.get('amount', '0')
        paid_to = request.POST.get('paid_to', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, "Please enter a valid positive expense amount.")
            return render(request, 'fees/expense_form.html', {'categories': categories})

        cat = get_object_or_404(AccountCategory, id=cat_id, type='expense')
        recorder = request.user.get_full_name() or request.user.username
        
        Expense.objects.create(
            category=cat,
            amount=amount,
            paid_to=paid_to or "Vendor / Payee",
            payment_method=payment_method,
            reference_number=reference_number,
            remarks=remarks,
            recorded_by=recorder,
            department=cat.department
        )
        messages.success(request, f"Expense voucher of ₹{amount} recorded successfully under {cat.name}.")
        return redirect('fees:expense_list')

    return render(request, 'fees/expense_form.html', {'categories': categories, 'page_title': 'Add Expense Voucher'})


# ==========================================
# DAY BOOK, LEDGER BOOK & FINANCE REPORTS
# ==========================================

@login_required
@role_required(['admin', 'accountant'])
def day_book(request):
    """Daily cash & bank movement day-book with chronological credit/debit transaction log."""
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    # Opening balance prior to this date
    prior_income = Income.objects.filter(date__lt=selected_date).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    prior_expense = Expense.objects.filter(date__lt=selected_date).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    opening_balance = prior_income - prior_expense

    # Incomes (Credits) of the day
    incomes = Income.objects.filter(date=selected_date).select_related('category').order_by('id')
    total_day_income = incomes.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    # Expenses (Debits) of the day
    expenses = Expense.objects.filter(date=selected_date).select_related('category').order_by('id')
    total_day_expense = expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    closing_balance = opening_balance + total_day_income - total_day_expense

    context = {
        'page_title': f'Day Book - {selected_date.strftime("%d %b %Y")}',
        'selected_date': selected_date,
        'opening_balance': opening_balance,
        'incomes': incomes,
        'expenses': expenses,
        'total_day_income': total_day_income,
        'total_day_expense': total_day_expense,
        'day_net': total_day_income - total_day_expense,
        'closing_balance': closing_balance,
    }
    return render(request, 'fees/day_book.html', context)


@login_required
@role_required(['admin', 'accountant'])
def ledger_book(request):
    """Account & Category-wise ledger statement with running balance."""
    categories = AccountCategory.objects.all().order_by('type', 'name')
    cat_id = request.GET.get('category')
    start_d = request.GET.get('start_date')
    end_d = request.GET.get('end_date')

    entries = []
    selected_category = None
    total_credit = Decimal('0.00')
    total_debit = Decimal('0.00')

    if cat_id:
        selected_category = get_object_or_404(AccountCategory, id=cat_id)
        if selected_category.type == 'income':
            qs = Income.objects.filter(category=selected_category)
            if start_d:
                qs = qs.filter(date__gte=start_d)
            if end_d:
                qs = qs.filter(date__lte=end_d)
            for inc in qs.order_by('date', 'id'):
                entries.append({
                    'date': inc.date,
                    'particulars': f"{inc.received_from} - {inc.remarks}".strip(' -'),
                    'ref': inc.reference_number,
                    'credit': inc.amount,
                    'debit': Decimal('0.00'),
                })
                total_credit += inc.amount
        else:
            qs = Expense.objects.filter(category=selected_category)
            if start_d:
                qs = qs.filter(date__gte=start_d)
            if end_d:
                qs = qs.filter(date__lte=end_d)
            for exp in qs.order_by('date', 'id'):
                entries.append({
                    'date': exp.date,
                    'particulars': f"{exp.paid_to} - {exp.remarks}".strip(' -'),
                    'ref': exp.reference_number,
                    'credit': Decimal('0.00'),
                    'debit': exp.amount,
                })
                total_debit += exp.amount

    context = {
        'page_title': 'General Ledger Book',
        'categories': categories,
        'selected_category': selected_category,
        'entries': entries,
        'total_credit': total_credit,
        'total_debit': total_debit,
        'start_date': start_d,
        'end_date': end_d,
    }
    return render(request, 'fees/ledger_book.html', context)


@login_required
@role_required(['admin', 'accountant'])
def finance_reports(request):
    """Gentle financial statements: Daily, Monthly, and Annual summaries."""
    report_type = request.GET.get('type', 'monthly')
    today = date.today()
    curr_year = int(request.GET.get('year', today.year))
    
    # 1. Monthly Breakdown for the selected year
    months_data = []
    annual_income = Decimal('0.00')
    annual_expense = Decimal('0.00')
    
    for m in range(1, 13):
        m_start = date(curr_year, m, 1)
        last_day = calendar.monthrange(curr_year, m)[1]
        m_end = date(curr_year, m, last_day)
        
        inc = Income.objects.filter(date__gte=m_start, date__lte=m_end).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        exp = Expense.objects.filter(date__gte=m_start, date__lte=m_end).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        net = inc - exp
        
        months_data.append({
            'month_number': m,
            'month_name': calendar.month_name[m],
            'income': inc,
            'expense': exp,
            'net': net,
            'is_current': (m == today.month and curr_year == today.year)
        })
        annual_income += inc
        annual_expense += exp

    # 2. Category-wise Breakdown for the year
    year_start = date(curr_year, 1, 1)
    year_end = date(curr_year, 12, 31)
    
    income_by_category = Income.objects.filter(date__gte=year_start, date__lte=year_end).values('category__name').annotate(total=Sum('amount')).order_by('-total')
    expense_by_category = Expense.objects.filter(date__gte=year_start, date__lte=year_end).values('category__name').annotate(total=Sum('amount')).order_by('-total')

    context = {
        'page_title': f'Financial Reports ({curr_year})',
        'report_type': report_type,
        'curr_year': curr_year,
        'years_list': [today.year - 2, today.year - 1, today.year, today.year + 1],
        'months_data': months_data,
        'annual_income': annual_income,
        'annual_expense': annual_expense,
        'annual_net': annual_income - annual_expense,
        'income_by_category': income_by_category,
        'expense_by_category': expense_by_category,
    }
    return render(request, 'fees/finance_reports.html', context)


# ==========================================
# CAUTION DEPOSITS & REFUNDS
# ==========================================

@login_required
@role_required(['admin', 'accountant'])
def caution_deposits(request):
    """Register of all student caution deposits and refund statuses."""
    deposits = CautionDeposit.objects.select_related('student').order_by('-date_collected')
    
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        deposits = deposits.filter(is_refunded=False)
    elif status_filter == 'refunded':
        deposits = deposits.filter(is_refunded=True)

    total_deposited = deposits.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    active_sum = CautionDeposit.objects.filter(is_refunded=False).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    context = {
        'page_title': 'Caution Deposits Register',
        'deposits': deposits,
        'total_deposited': total_deposited,
        'active_sum': active_sum,
        'status_filter': status_filter,
    }
    return render(request, 'fees/caution_deposits.html', context)


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def caution_deposit_refund_submit(request, deposit_id):
    """Execute refund of a caution deposit."""
    deposit = get_object_or_404(CautionDeposit, id=deposit_id)
    if deposit.is_refunded:
        messages.error(request, "This deposit has already been refunded.")
        return redirect('fees:caution_deposits')

    amount_str = request.POST.get('amount', str(deposit.amount))
    remarks = request.POST.get('remarks', '').strip()
    processor = request.user.get_full_name() or request.user.username

    try:
        amount = Decimal(amount_str)
        if amount <= 0 or amount > deposit.amount:
            raise ValueError()
    except Exception:
        messages.error(request, "Please enter a valid refund amount not exceeding the deposit amount.")
        return redirect('fees:caution_deposits')

    process_caution_refund(deposit, amount, processed_by=processor, remarks=remarks)
    messages.success(request, f"Refund of ₹{amount} processed for {deposit.student.full_name}.")
    return redirect('fees:caution_deposits')


# ==========================================
# FEE SETUP & CONFIGURATION
# ==========================================

@login_required
@role_required(['admin', 'accountant'])
def fee_setup(request):
    """Clean configuration hub for Fee Categories, Fee Items, and Bus Stops."""
    get_or_create_default_categories()
    
    categories = FeeCategory.objects.prefetch_related('fee_items').order_by('name')
    fee_items = FeeItem.objects.select_related('category').order_by('category__name', 'name')
    bus_stops = BusStop.objects.all().order_by('stop_name')
    payment_settings = InstitutionPaymentSetting.get_settings()
    
    context = {
        'page_title': 'Fee Structure & Rates Setup',
        'categories': categories,
        'fee_items': fee_items,
        'bus_stops': bus_stops,
        'payment_settings': payment_settings,
    }
    return render(request, 'fees/fee_setup.html', context)


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def payment_settings_update(request):
    """Updates institution bank account details, UPI VPA, and uploads payment QR code image."""
    settings_obj = InstitutionPaymentSetting.get_settings()
    
    settings_obj.institution_name = request.POST.get('institution_name', '').strip() or "Markaz Hadiya Women's College"
    settings_obj.account_holder_name = request.POST.get('account_holder_name', '').strip()
    settings_obj.bank_name = request.POST.get('bank_name', '').strip()
    settings_obj.account_number = request.POST.get('account_number', '').strip()
    settings_obj.ifsc_code = request.POST.get('ifsc_code', '').strip().upper()
    settings_obj.branch_name = request.POST.get('branch_name', '').strip()
    settings_obj.account_type = request.POST.get('account_type', '').strip() or "Current Account"
    settings_obj.upi_id = request.POST.get('upi_id', '').strip()
    settings_obj.upi_number = request.POST.get('upi_number', '').strip()
    settings_obj.helpline_phone = request.POST.get('helpline_phone', '').strip()
    settings_obj.payment_instructions = request.POST.get('payment_instructions', '').strip()
    
    if 'qr_code_image' in request.FILES:
        settings_obj.qr_code_image = request.FILES['qr_code_image']
    elif request.POST.get('clear_qr') == 'true':
        settings_obj.qr_code_image = None
        
    settings_obj.save()
    messages.success(request, "Institution bank account details and UPI QR code have been updated successfully.")
    return redirect('fees:fee_setup')




@login_required
@role_required(['admin', 'accountant'])
def bus_stop_create(request):
    """Add one or multiple bus stop destinations in a grid."""
    if request.method == 'POST':
        stop_names = request.POST.getlist('stop_name')
        fee_amounts = request.POST.getlist('fee_amount')
        
        created_stops = []
        for name, amount_str in zip(stop_names, fee_amounts):
            name = name.strip()
            amount_str = str(amount_str).strip()
            if not name:
                continue
            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    amount = Decimal('0.00')
            except Exception:
                amount = Decimal('0.00')
                
            stop = BusStop.objects.create(stop_name=name, fee_amount=amount)
            created_stops.append(f"{stop.stop_name} (₹{stop.fee_amount:.0f}/mo)")
            
        if created_stops:
            messages.success(request, f"Successfully added {len(created_stops)} bus stop(s): {', '.join(created_stops[:4])}{'...' if len(created_stops) > 4 else ''}.")
            return redirect('fees:fee_setup')
        else:
            messages.error(request, "Please enter at least one valid bus stop destination name.")
            return render(request, 'fees/bus_stop_form.html', {'page_title': 'Add Bus Stops'})

    return render(request, 'fees/bus_stop_form.html', {'page_title': 'Add Bus Stops'})



@login_required
@role_required(['admin', 'accountant'])
def fee_item_create(request):
    """Add a new fee item under a category."""
    categories = FeeCategory.objects.all().order_by('name')
    if request.method == 'POST':
        cat_id = request.POST.get('category_id')
        name = request.POST.get('name', '').strip()
        amount_str = request.POST.get('default_amount', '0').strip()
        fee_type = request.POST.get('fee_type', 'other')
        is_monthly = request.POST.get('is_monthly') == 'on' or fee_type in ['hostel', 'bus']
        target_type = request.POST.get('target_student_type', 'all')
        
        category = get_object_or_404(FeeCategory, id=cat_id)
        if not name:
            messages.error(request, "Fee item name is required.")
            return render(request, 'fees/fee_item_form.html', {'categories': categories, 'page_title': 'Add Fee Item'})

        try:
            amount = Decimal(amount_str or '0')
        except Exception:
            amount = Decimal('0.00')

        FeeItem.objects.create(
            category=category,
            name=name,
            default_amount=amount,
            fee_type=fee_type,
            is_monthly=is_monthly,
            target_student_type=target_type
        )
        messages.success(request, f"Fee item '{name}' added under {category.name}.")
        return redirect('fees:fee_setup')

    return render(request, 'fees/fee_item_form.html', {'categories': categories, 'page_title': 'Add Fee Item'})


@login_required
@role_required(['admin', 'accountant'])
def fee_item_update(request, item_id):
    """Edit an existing fee item on a dedicated form page."""
    item = get_object_or_404(FeeItem, id=item_id)
    categories = FeeCategory.objects.all().order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        amount_str = request.POST.get('default_amount', '0').strip()
        fee_type = request.POST.get('fee_type', item.fee_type)
        is_monthly = request.POST.get('is_monthly') == 'on' or fee_type in ['hostel', 'bus']
        target_type = request.POST.get('target_student_type', 'all')
        
        if not name:
            messages.error(request, "Fee item name cannot be empty.")
            return render(request, 'fees/fee_item_form.html', {'item': item, 'categories': categories, 'page_title': f'Edit Fee Item - {item.name}'})

        try:
            amount = Decimal(amount_str or '0')
        except Exception:
            amount = Decimal('0.00')

        item.name = name
        item.default_amount = amount
        item.fee_type = fee_type
        item.is_monthly = is_monthly
        item.target_student_type = target_type
        item.save()
        
        messages.success(request, f"Fee item '{name}' updated successfully.")
        return redirect('fees:fee_setup')

    return render(request, 'fees/fee_item_form.html', {
        'item': item,
        'categories': categories,
        'page_title': f'Edit Fee Item - {item.name}'
    })


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def fee_item_delete(request, item_id):
    """Delete a fee item."""
    item = get_object_or_404(FeeItem, id=item_id)
    name = item.name
    item.delete()
    messages.success(request, f"Fee item '{name}' removed.")
    return redirect('fees:fee_setup')


@login_required
@role_required(['admin', 'accountant'])
def bus_stop_update(request, stop_id):
    """Edit a bus stop destination and its rate on a dedicated form page."""
    bus_stop = get_object_or_404(BusStop, id=stop_id)

    if request.method == 'POST':
        stop_name = request.POST.get('stop_name', '').strip()
        amount_str = request.POST.get('fee_amount', '0').strip()

        if not stop_name:
            messages.error(request, "Bus stop name is required.")
            return render(request, 'fees/bus_stop_form.html', {'bus_stop': bus_stop, 'page_title': f'Edit Bus Stop - {bus_stop.stop_name}'})

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, "Please enter a valid positive bus fare amount.")
            return render(request, 'fees/bus_stop_form.html', {'bus_stop': bus_stop, 'page_title': f'Edit Bus Stop - {bus_stop.stop_name}'})

        bus_stop.stop_name = stop_name
        bus_stop.fee_amount = amount
        bus_stop.save()
        messages.success(request, f"Bus stop '{stop_name}' updated (₹{amount}/month).")
        return redirect('fees:fee_setup')

    return render(request, 'fees/bus_stop_form.html', {
        'bus_stop': bus_stop,
        'page_title': f'Edit Bus Stop - {bus_stop.stop_name}'
    })


@login_required
@role_required(['admin', 'accountant'])
@require_POST
def bus_stop_delete(request, stop_id):
    """Delete a bus stop."""
    bus_stop = get_object_or_404(BusStop, id=stop_id)
    name = bus_stop.stop_name
    bus_stop.delete()
    messages.success(request, f"Bus stop '{name}' removed.")
    return redirect('fees:fee_setup')


