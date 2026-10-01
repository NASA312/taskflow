import logging

from django.db import IntegrityError, transaction

from apps.projects.models import Project
from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)
Kind = Notification.Kind


def safe_delay(task, *args):
    """Encola una tarea de Celery sin romper la petición si el broker no responde."""
    try:
        task.delay(*args)
        return True
    except Exception:
        logger.exception("No se pudo encolar la tarea %s", task.name)
        return False


def _name(user):
    return (user.get_full_name() or user.username) if user else "Alguien"


def notify(recipient, kind, task, actor=None, message="", dedupe_key=""):
    """
    Crea una notificación en la app y, si el usuario lo permite, encola el correo.
    Devuelve la notificación, o None si no correspondía crearla.
    """
    if actor is not None and recipient.pk == actor.pk:
        return None                                  # no avisar a quien hizo la acción
    if not recipient.is_active:
        return None
    # Quien ya no puede ver el proyecto no debe enterarse de sus tareas
    if not Project.objects.alive().for_user(recipient).filter(pk=task.project_id).exists():
        return None

    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                recipient=recipient, actor=actor, kind=kind, task=task,
                message=message[:255], dedupe_key=dedupe_key,
            )
    except IntegrityError:
        return None                                  # misma clave de deduplicación: ya existía

    if NotificationPreference.for_user(recipient).wants_email(kind) and recipient.email:
        from .tasks import send_notification_email   # import local: evita ciclo con tasks.py

        # Se encola DESPUÉS del commit para que el worker encuentre la fila
        transaction.on_commit(lambda: safe_delay(send_notification_email, notification.pk))
    return notification


def _participants(task):
    """Asignados + quien creó la tarea."""
    people = {u.pk: u for u in task.assignees.all()}
    if task.created_by_id:
        people.setdefault(task.created_by_id, task.created_by)
    return list(people.values())


def notify_assigned(task, users, actor):
    message = f"{_name(actor)} te asignó la tarea «{task.title}»"
    for user in users:
        notify(user, Kind.ASSIGNED, task, actor, message)


def notify_status_change(task, actor, old_status):
    message = f"{_name(actor)} cambió «{task.title}» a {task.get_status_display()}"
    for user in _participants(task):
        notify(user, Kind.STATUS, task, actor, message)


def notify_comment(comment):
    task, actor = comment.task, comment.author
    message = f"{_name(actor)} comentó en «{task.title}»"
    for user in _participants(task):
        notify(user, Kind.COMMENT, task, actor, message)