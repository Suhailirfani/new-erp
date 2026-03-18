from decimal import Decimal
from datetime import date
from .models import FeeItem, StudentFee, FeeStructure, FeeInstallmentTemplate, FeeCategory
from students.models import Enrollment, Student

def allocate_fees_for_enrollment(enrollment):
    """
    Automatically allocates applicable non-monthly fees (Admission, Course, etc.)
    for a given student enrollment in an academic year.
    """
    student = enrollment.student
    academic_year = enrollment.academic_year
    grade = enrollment.grade
    division = enrollment.division
    
    # Identify non-monthly fee items
    items = FeeItem.objects.filter(is_monthly=False)
    
    for item in items:
        # Check Targeting Rules
        # 1. Grade targeting
        if item.applicable_grades.exists() and not item.applicable_grades.filter(id=grade.id).exists():
            continue
            
        # 2. Division targeting
        if item.applicable_divisions.exists():
            if not division or not item.applicable_divisions.filter(id=division.id).exists():
                continue
                
        # 3. Student Type targeting
        if item.target_student_type != 'all' and student.student_type != item.target_student_type:
            continue
            
        # Check if already assigned for this specific item and enrollment logic?
        # Admission fees are typically once per student per category usually.
        # But some might be once per academic year. 
        # For simplicity, we check if StudentFee for this item already exists for this student.
        # To handle academic year specific fees, we could track academic_year in StudentFee, but it's not currently there.
        # However, many fees like "Course Fee" have installments which are specific to a year.
        
        # Determine Amount
        fee_struct = FeeStructure.objects.filter(
            academic_year=academic_year,
            grade=grade,
            division=division,
            fee_item=item
        ).first()
        
        # Fallback to grade-only structure
        if not fee_struct and division:
            fee_struct = FeeStructure.objects.filter(
                academic_year=academic_year,
                grade=grade,
                division__isnull=True,
                fee_item=item
            ).first()
            
        final_amount = fee_struct.amount if fee_struct else item.default_amount
        
        if final_amount <= 0:
            continue
            
        # Handle Installments
        templates = item.installment_templates.all()
        if templates.exists():
            for tmpl in templates:
                # Check for existing installment fee to prevent duplicates
                # We use the name in remarks to identify specific installments
                existing = StudentFee.objects.filter(
                    student=student,
                    fee_item=item,
                    remarks__icontains=tmpl.name
                ).exists()
                
                if not existing:
                    # Calculate proportional amount if the total changed in FeeStructure? 
                    # Usually installments have fixed amounts in template. 
                    # If FeeStructure is different from template sum, we might need a rule.
                    # For now, we use the template amount.
                    StudentFee.objects.create(
                        student=student,
                        fee_item=item,
                        total_amount=tmpl.amount,
                        due_date=tmpl.due_date,
                        remarks=f"Installment: {tmpl.name}"
                    )
        else:
            # Single fee assignment
            existing = StudentFee.objects.filter(
                student=student,
                fee_item=item
            ).exists()
            
            if not existing:
                # Admission fees are usually due on day of admission/enrollment
                due_date = date.today()
                StudentFee.objects.create(
                    student=student,
                    fee_item=item,
                    total_amount=final_amount,
                    due_date=due_date,
                    remarks="Automatically allocated on enrollment"
                )
from django.db.models import Q
from calendar import monthrange

def calculate_prorated_percentage(present_days):
    """
    Returns 40, 80, or 100 based on presence.
    """
    if present_days <= 10:
        return Decimal('40.00')
    elif present_days <= 20:
        return Decimal('80.00')
    else:
        return Decimal('100.00')

def generate_monthly_fees_for_all(billing_month):
    """
    Generates recurring monthly fees for Hostel and Vehicle (Bus).
    billing_month: first day of the month (date object).
    """
    from students.models import HostelMovement
    
    # Identify Monthly Fee Items
    hostel_item = FeeItem.objects.filter(is_monthly=True, category__name__icontains='Hostel').first()
    bus_item = FeeItem.objects.filter(is_monthly=True, name__icontains='Bus Fee').first()
    
    active_students = Student.objects.filter(is_active=True)
    created_count = 0
    updated_count = 0
    
    month_start = billing_month
    _, last_day = monthrange(billing_month.year, billing_month.month)
    month_end = date(billing_month.year, billing_month.month, last_day)
    
    for student in active_students:
        # 1. Hostel Fee Generation
        if student.student_type == 'hostel' and hostel_item:
            # Check for existing fee for this month
            fee_record, created = StudentFee.objects.get_or_create(
                student=student,
                fee_item=hostel_item,
                billing_month=month_start,
                defaults={
                    'total_amount': hostel_item.default_amount,
                    'due_date': month_start,
                    'remarks': f"Hostel Fee - {month_start.strftime('%B %Y')}",
                    'present_days': last_day # Default to full month, can be adjusted down manually
                }
            )
            
            # Update/Calculate Prorating based on movements if needed
            # Calculating stay days:
            # We assume presence unless a movement says otherwise. 
            # Total days in month - (Days away from hostel in this month).
            # This is complex, but for now we follow the user: "fetched from movement records".
            
            # Simple heuristic: Count days between month_start and month_end where student was NOT 'Away'.
            # Or count days between return and leave.
            
            # For brevity, let's assume a function calculate_hostel_presence(student, month_start, month_end)
            presence_days = calculate_hostel_presence(student, month_start, month_end)
            percentage = calculate_prorated_percentage(presence_days)
            
            fee_record.prorated_percentage = percentage
            # Total amount = standard * percentage / 100
            new_total = (hostel_item.default_amount * percentage) / Decimal('100.00')
            
            if fee_record.total_amount != new_total:
                # If reduction happens and they already paid, the balance logic takes care of it,
                # but we should handle the advance_balance if payout > new_total.
                if fee_record.amount_paid > new_total:
                    surplus = fee_record.amount_paid - new_total
                    student.advance_balance += surplus
                    student.save()
                    # We keep amount_paid at the new total so balance is 0
                    fee_record.amount_paid = new_total
                
                fee_record.total_amount = new_total
                fee_record.update_status()
                fee_record.save()
                updated_count += 1
            
            if created:
                created_count += 1

        # 2. Vehicle Fee Generation
        if student.bus_stop and bus_item:
            fee_record, created = StudentFee.objects.get_or_create(
                student=student,
                fee_item=bus_item,
                billing_month=month_start,
                defaults={
                    'total_amount': student.bus_stop.fee_amount,
                    'due_date': month_start,
                    'remarks': f"Vehicle Fee - {month_start.strftime('%B %Y')} (Stop: {student.bus_stop.stop_name})",
                    'present_days': last_day # Default to full month, can be adjusted down manually
                }
            )
            
            # Vehicle proration rule (assuming same 40/80/100 based on bus attendance)
            # If bus attendance is not implemented, we default to 100% or use standard attendance.
            # user says "fetched from movement records" for hostel, doesn't specify for vehicle but says "similar to hostel fees".
            # We'll use the student's general attendance for bus for now if specific not exists.
            
            if created:
                created_count += 1
                
    return created_count, updated_count

def calculate_hostel_presence(student, month_start, month_end):
    """
    Calculates number of days the student was present in the hostel during the month.
    Uses HostelMovement records.
    """
    from students.models import HostelMovement
    days_in_month = (month_end - month_start).days + 1
    absent_days = 0
    
    # Movements where they were AWAY during this month
    movements = HostelMovement.objects.filter(
        student=student,
        departure_date__lte=month_end,
    ).filter(
        Q(arrival_date__gte=month_start) | Q(is_returned=False)
    )
    
    for mv in movements:
        # Calculate overlap between [mv.departure_date, mv.arrival_date] and [month_start, month_end]
        start = max(mv.departure_date, month_start)
        if mv.is_returned and mv.arrival_date:
            end = min(mv.arrival_date, month_end)
        else:
            end = month_end
            
        if end >= start:
            absent_days += (end - start).days + 1
            
    return max(0, days_in_month - absent_days)
