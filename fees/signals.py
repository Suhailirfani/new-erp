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

        # 3. Generate Hostel Fee
        if instance.student_type == 'hostel':
            try:
                hostel_category = FeeCategory.objects.get(name__icontains='Hostel')
                hostel_items = FeeItem.objects.filter(category=hostel_category)
                for item in hostel_items:
                    if item.default_amount > 0:
                        StudentFee.objects.create(
                            student=instance,
                            fee_item=item,
                            total_amount=item.default_amount,
                            due_date=date.today()
                        )
            except FeeCategory.DoesNotExist:
                pass

    # For both Created and Updated (e.g. bus stop assigned later)
    # 4. Generate Bus Fee if assigned
    if hasattr(instance, 'bus_stop') and instance.bus_stop:
        # Check if bus fee already assigned to avoid duplicates
        bus_fee_exists = StudentFee.objects.filter(
            student=instance, 
            fee_item__name__icontains='Bus Fee'
        ).exists()
        
        if not bus_fee_exists:
            # Ensure we have a Transport category and Bus Fee item
            transport_cat, _ = FeeCategory.objects.get_or_create(name='Transport', defaults={'description': 'Transportation/Bus Fees'})
            bus_item, _ = FeeItem.objects.get_or_create(
                category=transport_cat, 
                name='Bus Fee', 
                defaults={'default_amount': 0} # Real amount comes from stop
            )
            
            StudentFee.objects.create(
                student=instance,
                fee_item=bus_item,
                total_amount=instance.bus_stop.fee_amount,
                due_date=date.today(),
                remarks=f"Bus Stop: {instance.bus_stop.stop_name}"
            )
    else:
        # If student's bus_stop is removed, do we delete the un-paid bus fee?
        # That's a business logic decision. Usually, yes or kept as cancelled.
        pass
