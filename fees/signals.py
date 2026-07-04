from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from students.models import Enrollment
from .services import allocate_fees_for_enrollment
from .models import FeePayment, StudentFee, Income

@receiver(post_save, sender=Enrollment)
def trigger_fee_allocation(sender, instance, created, **kwargs):
    """
    Trigger fee allocation whenever a student is enrolled or enrollment is updated.
    """
    if created:
        allocate_fees_for_enrollment(instance)


@receiver(post_save, sender=FeePayment)
def update_student_fee_on_save(sender, instance, **kwargs):
    """
    Automatically updates the parent StudentFee balance when a payment is created or updated.
    """
    fee = instance.student_fee
    total_paid = fee.payments.aggregate(total=Sum('amount'))['total'] or 0
    if fee.amount_paid != total_paid:
        fee.amount_paid = total_paid
        fee.update_status()


@receiver(post_delete, sender=FeePayment)
def update_student_fee_on_delete(sender, instance, **kwargs):
    """
    Automatically recalculates the parent StudentFee balance and deletes the associated
    Income ledger entry when a payment is deleted/revoked.
    """
    # 1. Update parent StudentFee balance
    fee = instance.student_fee
    total_paid = fee.payments.aggregate(total=Sum('amount'))['total'] or 0
    if fee.amount_paid != total_paid:
        fee.amount_paid = total_paid
        fee.update_status()

    # 2. Automatically delete associated general ledger Income entry if it exists
    if hasattr(instance, 'income_record') and instance.income_record:
        instance.income_record.delete()

