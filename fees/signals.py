from django.db.models.signals import post_save
from django.dispatch import receiver
from students.models import Student
from .models import FeeItem, CourseInstallment, StudentFee, FeeCategory, BusStop
from datetime import date

@receiver(post_save, sender=Student)
def generate_student_fees(sender, instance, created, **kwargs):
    if created:
        # 1. Generate Admission Related Fees
        try:
            admission_category = FeeCategory.objects.get(name__icontains='Admission')
            admission_items = FeeItem.objects.filter(category=admission_category)
            for item in admission_items:
                if item.default_amount > 0:
                    StudentFee.objects.create(
                        student=instance,
                        fee_item=item,
                        total_amount=item.default_amount,
                        due_date=date.today()
                    )
        except FeeCategory.DoesNotExist:
            pass # Admission category not set up yet

        # 2. Generate Course Fee Installments
        installments = CourseInstallment.objects.all()
        # You might want to link Course to Fee, but for now we assign all general installments
        # Alternatively, create a 'Course Fee' item first. Let's assume installment implies course fee directly
        for inst in installments:
            # Getting default course fee amount? We need a way to know amount for installment.
            # Let's see, if we have a FeeItem for Course Fee, we can use that, else we might not know the amount.
            # A simple approach: we create StudentFee for installments with 0 amount to be updated by admin,
            # or we fetch a FeeItem named 'Course Fee'.
            pass # We'll handle this manually or via a different model if needed, 
                 # or let's create a 'Course Fee' installment with 0 amount to show it's due.
            StudentFee.objects.create(
                student=instance,
                installment=inst,
                total_amount=0, # Admin will set this or we define a default course fee per grade later
                due_date=inst.due_date
            )

        # 3. Monthly Fees (Hostel, Vehicle) are now handled by the Monthly Fee Generator tool
        # to ensure consistency and proper monthly billing cycles.
        pass
    
    # 4. Bus Fee updates are also handled by the Monthly Generator
    pass
