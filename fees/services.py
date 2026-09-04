from decimal import Decimal
from datetime import date, datetime, timedelta
import calendar
import uuid
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import (
    FeeCategory, FeeItem, FeeStructure, CourseInstallment, StudentFee,
    ReceiptTransaction, FeePayment, CautionDeposit, CautionDepositRefund,
    AccountCategory, Income, Expense, BusStop
)
from students.models import Student, Enrollment, AcademicYear


def get_or_create_default_categories():
    """Ensure standard fee categories exist in the system."""
    defaults = [
        ('Course Fees', 'academic', 'Annual tuition, term installments and examination fees'),
        ('Hostel & Mess', 'hostel', 'Monthly boarding, lodging and mess charges'),
        ('Bus & Transport', 'general', 'Monthly vehicle and transport charges based on bus stops'),
        ('Admission Essentials', 'academic', 'Admission fee, uniform, books, ID card, registration, program kit'),
        ('Caution Deposits', 'general', 'Refundable security deposits'),
        ('Others & Ad-hoc', 'general', 'Store borrows, canteen/outside orders, medical charges, miscellaneous dues'),
    ]
    created_map = {}
    for name, dept, desc in defaults:
        cat, _ = FeeCategory.objects.get_or_create(
            name=name,
            defaults={'department': dept, 'description': desc}
        )
        created_map[name] = cat
    return created_map


def get_default_fee_item(fee_type='other', name=None, default_amount=0):
    """Retrieve or create standard fee item for automated operations."""
    cats = get_or_create_default_categories()
    
    if fee_type == 'hostel':
        cat = cats['Hostel & Mess']
        item_name = name or "Monthly Hostel Fee"
        is_monthly = True
    elif fee_type == 'bus':
        cat = cats['Bus & Transport']
        item_name = name or "Monthly Bus Fee"
        is_monthly = True
    elif fee_type == 'admission':
        cat = cats['Admission Essentials']
        item_name = name or "Admission Fee"
        is_monthly = False
    elif fee_type == 'caution':
        cat = cats['Caution Deposits']
        item_name = name or "Caution Deposit"
        is_monthly = False
    elif fee_type == 'course':
        cat = cats['Course Fees']
        item_name = name or "Course Tuition Fee"
        is_monthly = False
    else:
        cat = cats['Others & Ad-hoc']
        item_name = name or "Miscellaneous Fee"
        is_monthly = False

    item, _ = FeeItem.objects.get_or_create(
        name=item_name,
        category=cat,
        defaults={
            'fee_type': fee_type,
            'is_monthly': is_monthly,
            'default_amount': Decimal(str(default_amount or 0)),
            'target_student_type': 'hostel' if fee_type == 'hostel' else 'all'
        }
    )
    return item


def sync_student_monthly_dues(student, up_to_date=None):
    """
    Ensures that all elapsed monthly recurring fees (Hostel and Bus) are generated
    up to the current billing month without creating any duplicates.
    """
    if not up_to_date:
        up_to_date = date.today()
        
    active_year = AcademicYear.objects.filter(is_active=True).first()
    if active_year and active_year.start_date:
        start_date = active_year.start_date
    else:
        # Fallback to June of the current academic session year
        start_year = up_to_date.year if up_to_date.month >= 6 else (up_to_date.year - 1)
        start_date = date(start_year, 6, 1)

    # Generate list of 1st-of-month dates from start_date to up_to_date
    curr = date(start_date.year, start_date.month, 1)
    target = date(up_to_date.year, up_to_date.month, 1)
    
    billing_months = []
    while curr <= target:
        billing_months.append(curr)
        # Advance 1 month
        if curr.month == 12:
            curr = date(curr.year + 1, 1, 1)
        else:
            curr = date(curr.year, curr.month + 1, 1)

    created_count = 0

    # 1. Monthly Hostel Fees for Hostellers
    if student.student_type == 'hostel':
        hostel_item = FeeItem.objects.filter(fee_type='hostel').first()
        if not hostel_item:
            hostel_item = get_default_fee_item(fee_type='hostel', name='Hostel Fee', default_amount=6000)
            
        rate = hostel_item.default_amount if hostel_item.default_amount > 0 else Decimal('6000.00')
        
        for b_month in billing_months:
            exists = StudentFee.objects.filter(
                student=student,
                fee_item=hostel_item,
                billing_month=b_month
            ).exists()
            
            if not exists:
                # 10th of the billing month is due date
                due_d = date(b_month.year, b_month.month, min(10, calendar.monthrange(b_month.year, b_month.month)[1]))
                StudentFee.objects.create(
                    student=student,
                    fee_item=hostel_item,
                    total_amount=rate,
                    billing_month=b_month,
                    due_date=due_d,
                    remarks=f"Hostel Fee for {b_month.strftime('%B %Y')}"
                )
                created_count += 1

    # 2. Monthly Bus Fees for Bus Users
    if (student.uses_bus or student.bus_stop) and student.bus_stop:
        bus_item = FeeItem.objects.filter(fee_type='bus').first()
        if not bus_item:
            bus_item = get_default_fee_item(fee_type='bus', name='Bus Fee', default_amount=student.bus_stop.fee_amount)
            
        bus_rate = student.bus_stop.fee_amount
        
        for b_month in billing_months:
            exists = StudentFee.objects.filter(
                student=student,
                fee_item=bus_item,
                billing_month=b_month
            ).exists()
            
            if not exists:
                due_d = date(b_month.year, b_month.month, min(10, calendar.monthrange(b_month.year, b_month.month)[1]))
                StudentFee.objects.create(
                    student=student,
                    fee_item=bus_item,
                    total_amount=bus_rate,
                    billing_month=b_month,
                    due_date=due_d,
                    remarks=f"Bus Fee ({student.bus_stop.stop_name}) for {b_month.strftime('%B %Y')}"
                )
                created_count += 1

    return created_count


def batch_generate_monthly_fees(billing_month):
    """
    Batch generate recurring fees for all active students for a specific month.
    billing_month must be a date object pointing to 1st of month.
    """
    hostel_item = FeeItem.objects.filter(fee_type='hostel').first()
    if not hostel_item:
        hostel_item = get_default_fee_item(fee_type='hostel', name='Hostel Fee', default_amount=6000)
    hostel_rate = hostel_item.default_amount if hostel_item.default_amount > 0 else Decimal('6000.00')

    bus_item = FeeItem.objects.filter(fee_type='bus').first()
    if not bus_item:
        bus_item = get_default_fee_item(fee_type='bus', name='Bus Fee', default_amount=1000)

    due_d = date(billing_month.year, billing_month.month, min(10, calendar.monthrange(billing_month.year, billing_month.month)[1]))
    
    hostel_count = 0
    bus_count = 0
    total_amount = Decimal('0.00')

    with transaction.atomic():
        # Active Hostellers
        hostel_students = Student.objects.filter(is_active=True, student_type='hostel')
        for st in hostel_students:
            exists = StudentFee.objects.filter(
                student=st,
                fee_item=hostel_item,
                billing_month=billing_month
            ).exists()
            if not exists:
                StudentFee.objects.create(
                    student=st,
                    fee_item=hostel_item,
                    total_amount=hostel_rate,
                    billing_month=billing_month,
                    due_date=due_d,
                    remarks=f"Hostel Fee for {billing_month.strftime('%B %Y')}"
                )
                hostel_count += 1
                total_amount += hostel_rate

        # Active Bus Riders
        bus_students = Student.objects.filter(is_active=True, bus_stop__isnull=False)
        for st in bus_students:
            exists = StudentFee.objects.filter(
                student=st,
                fee_item=bus_item,
                billing_month=billing_month
            ).exists()
            if not exists:
                b_amount = st.bus_stop.fee_amount
                StudentFee.objects.create(
                    student=st,
                    fee_item=bus_item,
                    total_amount=b_amount,
                    billing_month=billing_month,
                    due_date=due_d,
                    remarks=f"Bus Fee ({st.bus_stop.stop_name}) for {billing_month.strftime('%B %Y')}"
                )
                bus_count += 1
                total_amount += b_amount

    return {
        'hostel_count': hostel_count,
        'bus_count': bus_count,
        'total_count': hostel_count + bus_count,
        'total_amount': total_amount,
        'billing_month': billing_month
    }


def add_adhoc_charge(student, title, amount, remarks="", due_date=None):
    """
    Directly add an ad-hoc charge to a student (e.g. food order from outside, store borrow, medical).
    """
    adhoc_item = FeeItem.objects.filter(fee_type__in=['adhoc', 'other', 'medical']).first()
    if not adhoc_item:
        adhoc_item = get_default_fee_item(fee_type='other', name='Ad-hoc Charges')

    return StudentFee.objects.create(
        student=student,
        fee_item=adhoc_item,
        custom_title=title,
        total_amount=Decimal(str(amount)),
        remarks=remarks,
        due_date=due_date or date.today()
    )


def assign_admission_essentials(student, enrollment=None):
    """
    Assigns admission essentials (Uniform, Books, Registration, ID, Admission Fee, Caution Deposit)
    to a newly enrolled or existing student without duplicates.
    """
    get_or_create_default_categories()
    admission_items = FeeItem.objects.filter(fee_type__in=['admission', 'caution'])
    
    assigned = []
    grade = enrollment.grade if enrollment else (student.current_enrollment.grade if student.current_enrollment else None)
    division = enrollment.division if enrollment else (student.current_enrollment.division if student.current_enrollment else None)

    for item in admission_items:
        # Check grade targeting
        if item.applicable_grades.exists() and grade and not item.applicable_grades.filter(id=grade.id).exists():
            continue
        # Check division targeting
        if item.applicable_divisions.exists() and division and not item.applicable_divisions.filter(id=division.id).exists():
            continue
        # Check student type targeting
        if item.target_student_type != 'all' and item.target_student_type != student.student_type:
            continue

        # Prevent duplicate assignment of the same fee item
        exists = StudentFee.objects.filter(student=student, fee_item=item).exists()
        if not exists and item.default_amount > 0:
            sf = StudentFee.objects.create(
                student=student,
                fee_item=item,
                total_amount=item.default_amount,
                due_date=date.today(),
                remarks=f"Initial Admission: {item.name}"
            )
            assigned.append(sf)

    return assigned


def record_fee_payment(student, fee_allocations, payment_method='cash', reference_number='', collected_by='Office Accountant', remarks=''):
    """
    Processes fee payment for multiple student fee items in a single unified transaction.
    fee_allocations: list of dicts [{'fee_id': int, 'amount': Decimal, 'concession': Decimal}]
    """
    if not fee_allocations:
        raise ValueError("No fee items provided for collection.")

    with transaction.atomic():
        # Compute total collected amount
        total_payment = Decimal('0.00')
        valid_items = []
        
        for alloc in fee_allocations:
            sf_id = alloc.get('fee_id')
            pay_amt = Decimal(str(alloc.get('amount', 0)))
            conc_amt = Decimal(str(alloc.get('concession', 0)))
            
            if pay_amt <= 0 and conc_amt <= 0:
                continue
                
            sf = StudentFee.objects.select_for_update().get(id=sf_id, student=student)
            total_payment += pay_amt
            valid_items.append((sf, pay_amt, conc_amt))

        if not valid_items:
            raise ValueError("Payment amount must be greater than zero.")

        # Create Unified Receipt Transaction
        receipt_tx = ReceiptTransaction.objects.create(
            student=student,
            total_amount=total_payment,
            payment_method=payment_method,
            reference_number=reference_number,
            collected_by=collected_by,
            remarks=remarks
        )

        # Create or fetch AccountCategory for student fee income
        acc_cat, _ = AccountCategory.objects.get_or_create(
            name='Student Fees',
            type='income',
            defaults={'department': 'general', 'description': 'Office fee collection receipts'}
        )

        # Create Income Record in General Ledger
        income_rec = Income.objects.create(
            category=acc_cat,
            amount=total_payment,
            received_from=f"{student.full_name} ({student.student_id})",
            payment_method=payment_method,
            reference_number=reference_number or f"Txn-{str(receipt_tx.transaction_id)[:8]}",
            remarks=f"Fee collection receipt {str(receipt_tx.transaction_id)[:8]}. {remarks}".strip(),
            collected_by=collected_by,
            department='general'
        )

        # Apply to each StudentFee & record FeePayment
        for sf, pay_amt, conc_amt in valid_items:
            if conc_amt > 0:
                sf.concession_amount += conc_amt
                
            if pay_amt > 0:
                sf.amount_paid += pay_amt
                
                FeePayment.objects.create(
                    student_fee=sf,
                    amount=pay_amt,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    collected_by=collected_by,
                    remarks=remarks,
                    receipt_transaction=receipt_tx,
                    income=income_rec
                )

                # If this item was a caution deposit, record it in CautionDeposit model
                if sf.fee_item and sf.fee_item.fee_type == 'caution':
                    CautionDeposit.objects.create(
                        student=student,
                        amount=pay_amt,
                        date_collected=date.today(),
                        receipt_number=str(receipt_tx.transaction_id)[:8],
                        remarks=f"Paid via Receipt {str(receipt_tx.transaction_id)[:8]}"
                    )

            sf.update_status()

    return receipt_tx


def process_caution_refund(deposit, amount_refunded, processed_by='Office Accountant', remarks=''):
    """
    Process refund of a refundable caution deposit.
    """
    with transaction.atomic():
        refund = CautionDepositRefund.objects.create(
            deposit=deposit,
            amount_refunded=Decimal(str(amount_refunded)),
            processed_by=processed_by,
            remarks=remarks
        )
        
        # Post Expense to Ledger
        exp_cat, _ = AccountCategory.objects.get_or_create(
            name='Caution Deposit Refund',
            type='expense',
            defaults={'department': 'general', 'description': 'Security deposit refunds to students'}
        )
        
        Expense.objects.create(
            category=exp_cat,
            amount=Decimal(str(amount_refunded)),
            paid_to=f"{deposit.student.full_name} ({deposit.student.student_id})",
            payment_method='cash',
            reference_number=f"CD-REF-{deposit.id}",
            remarks=f"Caution Deposit Refund: {remarks}".strip(),
            recorded_by=processed_by,
            department='general'
        )
        
    return refund


def get_financial_summary(start_date=None, end_date=None):
    """
    Calculates total income, total expense, and net balance for a date range.
    """
    income_qs = Income.objects.all()
    expense_qs = Expense.objects.all()

    if start_date:
        income_qs = income_qs.filter(date__gte=start_date)
        expense_qs = expense_qs.filter(date__gte=start_date)
    if end_date:
        income_qs = income_qs.filter(date__lte=end_date)
        expense_qs = expense_qs.filter(date__lte=end_date)

    total_income = income_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_flow = total_income - total_expense

    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_flow': net_flow,
        'income_count': income_qs.count(),
        'expense_count': expense_qs.count(),
    }


def apply_fee_reduction(student_fee, reduction_type, value=0, reason='', present_days=None, total_days=30):
    """
    Applies a fee reduction/concession/waiver to a StudentFee.
    Supports:
      - 'full': 100% full waiver (e.g. not used bus/hostel)
      - 'fixed': Fixed reduction amount (e.g. ₹1000 discount)
      - 'percent': Percentage reduction (e.g. 50%)
      - 'days': Prorated based on days present vs total days
      - 'reset': Removes the reduction
    """
    with transaction.atomic():
        if reduction_type == 'reset':
            student_fee.concession_amount = Decimal('0.00')
            student_fee.concession_remark = ''
            student_fee.present_days = None
            student_fee.prorated_percentage = Decimal('100.00')
        elif reduction_type == 'full':
            # Full waiver of total fee (or remaining balance if partially paid)
            student_fee.concession_amount = student_fee.total_amount - student_fee.amount_paid
            if student_fee.concession_amount < Decimal('0.00'):
                student_fee.concession_amount = Decimal('0.00')
            student_fee.concession_remark = reason or "100% Full Waiver / Not Used"
            student_fee.prorated_percentage = Decimal('0.00')
        elif reduction_type == 'percent':
            pct = Decimal(str(value or 0))
            if pct > Decimal('100.00'):
                pct = Decimal('100.00')
            if pct < Decimal('0.00'):
                pct = Decimal('0.00')
            concession = (student_fee.total_amount * pct) / Decimal('100.00')
            max_concession = max(Decimal('0.00'), student_fee.total_amount - student_fee.amount_paid)
            student_fee.concession_amount = min(concession, max_concession)
            student_fee.concession_remark = reason or f"{pct}% Reduction"
            student_fee.prorated_percentage = Decimal('100.00') - pct
        elif reduction_type == 'days':
            p_days = int(present_days or 0)
            t_days = int(total_days or 30)
            if t_days <= 0:
                t_days = 30
            if p_days < 0:
                p_days = 0
            if p_days > t_days:
                p_days = t_days
            # Pro-rated payable amount based on present days
            payable = round((student_fee.total_amount / Decimal(str(t_days))) * Decimal(str(p_days)), 2)
            concession = max(Decimal('0.00'), student_fee.total_amount - payable)
            max_concession = max(Decimal('0.00'), student_fee.total_amount - student_fee.amount_paid)
            student_fee.concession_amount = min(concession, max_concession)
            student_fee.present_days = p_days
            pct = round((Decimal(str(p_days)) / Decimal(str(t_days))) * Decimal('100.00'), 2)
            student_fee.prorated_percentage = pct
            student_fee.concession_remark = reason or f"Prorated: {p_days}/{t_days} days present"
        else: # 'fixed'
            amt = Decimal(str(value or 0))
            if amt < Decimal('0.00'):
                amt = Decimal('0.00')
            max_concession = max(Decimal('0.00'), student_fee.total_amount - student_fee.amount_paid)
            student_fee.concession_amount = min(amt, max_concession)
            student_fee.concession_remark = reason or f"Fee Reduction: ₹{amt}"
            
        student_fee.update_status()
        return student_fee

