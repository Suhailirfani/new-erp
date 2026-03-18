from django.db import models
from decimal import Decimal
import uuid

class FeeCategory(models.Model):
    """Categories like Admission, Course, Hostel, Transport, etc."""
    DEPARTMENT_CHOICES = [
        ('academic', 'Academic'),
        ('hostel', 'Hostel'),
        ('general', 'General/Institutional'),
    ]
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default='general')

    class Meta:
        verbose_name_plural = "Fee Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

class FeeItem(models.Model):
    """Specific fees like Admission Fee, Uniform, Books"""
    category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='fee_items')
    name = models.CharField(max_length=100)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_refundable = models.BooleanField(default=False)
    is_monthly = models.BooleanField(default=False, help_text="Generation happens 1st of every month (e.g., Hostel/Vehicle)")
    description = models.TextField(blank=True)
    
    # Targeting
    applicable_grades = models.ManyToManyField('students.Grade', blank=True, related_name='applicable_fees', help_text="If none selected, applies to all grades.")
    applicable_divisions = models.ManyToManyField('students.Division', blank=True, related_name='applicable_fees', help_text="If none selected, applies to all divisions.")

    STUDENT_TYPE_TARGET_CHOICES = [
        ('all', 'All Students'),
        ('hostel', 'Hostel Students Only'),
        ('day_scholar', 'Day Scholars Only'),
    ]
    target_student_type = models.CharField(max_length=20, choices=STUDENT_TYPE_TARGET_CHOICES, default='all')
    department = models.CharField(
        max_length=20, 
        choices=FeeCategory.DEPARTMENT_CHOICES, 
        default='academic',
        help_text="The department this fee belongs to (Academic vs Hostel)"
    )

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.category})"

class BusStop(models.Model):
    """Bus stops and their associated fee"""
    stop_name = models.CharField(max_length=100)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['stop_name']

    def __str__(self):
        return f"{self.stop_name} (₹{self.fee_amount})"


class CourseInstallment(models.Model):
    """Installments for course fees"""
    name = models.CharField(max_length=100, help_text="e.g., 1st Installment, 2nd Installment")
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['due_date', 'name']

    def __str__(self):
        return f"{self.name} (Due: {self.due_date})"

class StudentFee(models.Model):
    """Fee entry assigned to a specific student"""
    STATUS_CHOICES = [
        ('due', 'Due'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='fees')
    fee_item = models.ForeignKey(FeeItem, on_delete=models.CASCADE, null=True, blank=True)
    installment = models.ForeignKey(CourseInstallment, on_delete=models.CASCADE, null=True, blank=True)
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='due')
    remarks = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Concessions
    concession_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    concession_remark = models.TextField(blank=True)
    
    # Prorating for Monthly Fees (Hostel/Vehicle)
    prorated_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100, help_text="e.g., 40, 80, 100")
    present_days = models.PositiveIntegerField(null=True, blank=True, help_text="Manual adjustment of days present in the billing month")
    billing_month = models.DateField(null=True, blank=True, help_text="The month this recurring fee covers")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'status']

    def __str__(self):
        item_name = self.fee_item.name if self.fee_item else (self.installment.name if self.installment else 'Fee')
        return f"{self.student} - {item_name} - {self.status}"

    @property
    def balance(self):
        # Effective total is amount minus any concession
        effective_total = self.total_amount - self.concession_amount
        return max(Decimal('0.00'), effective_total - self.amount_paid)

    def update_status(self):
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        else:
            self.status = 'due'
        self.save()

class FeePayment(models.Model):
    """Payment record"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('card', 'Card'),
    ]

    receipt_number = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = models.CharField(max_length=100, blank=True, help_text="Transaction ID/Cheque No.")
    collected_by = models.CharField(max_length=100)
    remarks = models.TextField(blank=True)
    income = models.ForeignKey('Income', on_delete=models.CASCADE, related_name='fee_payments', null=True, blank=True, help_text="The overarching Income record this payment belongs to")

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.student_fee.student} - ₹{self.amount}"

class AccountCategory(models.Model):
    """Categories for income and expense (e.g., Donations, Salary, Maintenance)"""
    CATEGORY_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=CATEGORY_TYPES)
    department = models.CharField(max_length=20, choices=FeeCategory.DEPARTMENT_CHOICES, default='general')
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Account Categories"
        ordering = ['type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Income(models.Model):
    """General income records"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('card', 'Card'),
    ]

    category = models.ForeignKey(AccountCategory, on_delete=models.RESTRICT, limit_choices_to={'type': 'income'}, related_name='incomes')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    received_from = models.CharField(max_length=200, help_text="Person or organization who paid")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    fee_payment_ref = models.OneToOneField(FeePayment, null=True, blank=True, on_delete=models.SET_NULL, related_name='income_record', help_text="Linked to a student fee payment if applicable")
    collected_by = models.CharField(max_length=100)
    department = models.CharField(max_length=20, choices=FeeCategory.DEPARTMENT_CHOICES, default='general')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Income: {self.category.name} - ₹{self.amount} on {self.date}"


class Expense(models.Model):
    """General expense records"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('card', 'Card'),
    ]

    category = models.ForeignKey(AccountCategory, on_delete=models.RESTRICT, limit_choices_to={'type': 'expense'}, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    paid_to = models.CharField(max_length=200, help_text="Person or organization receiving payment")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    recorded_by = models.CharField(max_length=100)
    department = models.CharField(max_length=20, choices=FeeCategory.DEPARTMENT_CHOICES, default='general')

    class Meta:
        ordering = ['-date']


class FeeStructure(models.Model):
    """Specific fee amounts for combinations of Academic Year, Grade, and Division"""
    academic_year = models.ForeignKey('students.AcademicYear', on_delete=models.CASCADE, related_name='fee_structures')
    grade = models.ForeignKey('students.Grade', on_delete=models.CASCADE, related_name='fee_structures')
    division = models.ForeignKey('students.Division', on_delete=models.CASCADE, null=True, blank=True, related_name='fee_structures')
    fee_item = models.ForeignKey(FeeItem, on_delete=models.CASCADE, related_name='fee_structures')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['academic_year', 'grade', 'division', 'fee_item']]
        verbose_name = "Fee Structure"
        verbose_name_plural = "Fee Structures"

    def __str__(self):
        div_name = f" - {self.division.name}" if self.division else ""
        return f"{self.fee_item.name}: {self.grade.name}{div_name} ({self.academic_year.name}) - ₹{self.amount}"

class FeeInstallmentTemplate(models.Model):
    """Template for breaking a FeeItem into multiple installments"""
    fee_item = models.ForeignKey(FeeItem, on_delete=models.CASCADE, related_name='installment_templates')
    installment_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, help_text="e.g., 1st Installment")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount for this specific installment")

    class Meta:
        ordering = ['installment_number']
        unique_together = [['fee_item', 'installment_number']]

    def __str__(self):
        return f"{self.fee_item.name} - {self.name} (₹{self.amount})"
