from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from students.models import Enrollment, Student
from .services import assign_admission_essentials, sync_student_monthly_dues
from .models import FeePayment, StudentFee, Income


@receiver(post_save, sender=Enrollment)
def trigger_fee_allocation(sender, instance, created, **kwargs):
    """
    Trigger admission essentials and monthly dues sync whenever a student is enrolled.
    """
    if created and instance.student:
        try:
            assign_admission_essentials(instance.student, enrollment=instance)
            sync_student_monthly_dues(instance.student)
        except Exception:
            pass


@receiver(post_save, sender=FeePayment)
def update_student_fee_on_save(sender, instance, **kwargs):
    """
    Automatically updates the parent StudentFee balance when a payment is created or updated.
    """
    fee = instance.student_fee
    if fee:
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
    fee = instance.student_fee
    if fee:
        total_paid = fee.payments.aggregate(total=Sum('amount'))['total'] or 0
        if fee.amount_paid != total_paid:
            fee.amount_paid = total_paid
            fee.update_status()

    if hasattr(instance, 'income_record') and instance.income_record:
        instance.income_record.delete()
