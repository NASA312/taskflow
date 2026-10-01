from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from apps.tasks.models import Task
from .models import Notification
from .services import notify

Kind = Notification.Kind
RETRY = {"autoretry_for": (Exception,), "retry_backoff": True, "retry_kwargs": {"max_retries": 3}}


@shared_task(**RETRY)
def send_notification_email(notification_id):
    try:
        n = Notification.objects.select_related("recipient").get(pk=notification_id)
    except Notification.DoesNotExist:
        return "no existe"
    if n.emailed_at or not n.recipient.email or not n.recipient.is_active:
        return "omitida"                                  # idempotente: nunca se envía dos veces

    base = settings.SITE_URL.rstrip("/")
    link = base + reverse("notification_open", args=[n.pk])
    prefs = base + reverse("notification_preferences")
    body = (
        f"Hola {n.recipient.get_full_name() or n.recipient.username},\n\n"
        f"{n.message}\n\n"
        f"Ábrela aquí:\n{link}\n\n"
        f"—\nPuedes elegir qué correos recibir en:\n{prefs}\n"
    )
    send_mail(f"[TaskFlow] {n.message}"[:120], body, settings.DEFAULT_FROM_EMAIL, [n.recipient.email])
    Notification.objects.filter(pk=n.pk).update(emailed_at=timezone.now())
    return "enviada"


@shared_task(**RETRY)
def send_plain_email(subject, body, to_email):
    """Correo genérico (lo usa la recuperación de contraseña)."""
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email])


def _when(due, today):
    days = (due - today).days
    return "hoy" if days == 0 else "mañana" if days == 1 else f"el {due:%d/%m}"


@shared_task
def send_deadline_reminders():
    """Corre una vez al día (Celery Beat). Devuelve cuántas notificaciones creó."""
    today = timezone.localdate()
    horizon = today + timedelta(days=settings.DEADLINE_REMINDER_DAYS)
    base = (
        Task.objects.alive()
        .filter(parent__isnull=True, project__deleted_at__isnull=True, due_date__isnull=False)
        .exclude(status=Task.Status.DONE)
        .select_related("project", "created_by")
        .prefetch_related("assignees")
    )
    created = 0

    for task in base.filter(due_date__gte=today, due_date__lte=horizon):
        message = f"«{task.title}» vence {_when(task.due_date, today)}"
        key = f"due_soon:{task.pk}:{task.due_date.isoformat()}"
        for user in task.assignees.all():
            if notify(user, Kind.DUE_SOON, task, message=message, dedupe_key=key):
                created += 1

    for task in base.filter(due_date__lt=today):
        message = f"«{task.title}» está atrasada (venció el {task.due_date:%d/%m/%Y})"
        key = f"overdue:{task.pk}:{task.due_date.isoformat()}"
        people = {u.pk: u for u in task.assignees.all()}
        if task.created_by_id:
            people.setdefault(task.created_by_id, task.created_by)
        for user in people.values():
            if notify(user, Kind.OVERDUE, task, message=message, dedupe_key=key):
                created += 1
    return created


@shared_task
def cleanup_old_notifications():
    """Borra notificaciones ya leídas hace más de 60 días."""
    limit = timezone.now() - timedelta(days=60)
    return Notification.objects.filter(read_at__lt=limit).delete()[0]