from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Payment
from .services import sync_order_paid_amount


@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
def keep_order_paid_amount_in_sync(sender, instance, **kwargs):
    sync_order_paid_amount(instance.order)
