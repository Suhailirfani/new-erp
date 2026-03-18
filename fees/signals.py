from django.db.models.signals import post_save
from django.dispatch import receiver
from students.models import Enrollment
from .services import allocate_fees_for_enrollment

@receiver(post_save, sender=Enrollment)
def trigger_fee_allocation(sender, instance, created, **kwargs):
    """
    Trigger fee allocation whenever a student is enrolled or enrollment is updated.
    """
    if created:
        allocate_fees_for_enrollment(instance)
