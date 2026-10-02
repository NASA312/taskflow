from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Activity


@shared_task
def cleanup_old_activity():
    """Borra eventos más antiguos que ACTIVITY_RETENTION_DAYS. Devuelve cuántos borró."""
    limit = timezone.now() - timedelta(days=settings.ACTIVITY_RETENTION_DAYS)
    return Activity.objects.filter(created_at__lt=limit).delete()[0]