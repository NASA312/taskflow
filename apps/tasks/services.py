from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from apps.notifications.services import notify_status_change
from apps.activity.models import Activity
from apps.activity.services import record

from .models import Task


class MoveError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def apply_filters(qs, params, user):
    q = params.get("q", "").strip()
    assignee = params.get("assignee", "")
    priority = params.get("priority", "")
    due = params.get("due", "")
    today = timezone.localdate()

    if q:
        qs = qs.filter(title__icontains=q)
    if assignee == "me":
        qs = qs.filter(assignees=user)
    elif assignee == "none":
        qs = qs.filter(assignees__isnull=True)
    elif assignee.isdigit():
        qs = qs.filter(assignees__pk=int(assignee))
    if priority in {"1", "2", "3", "4"}:
        qs = qs.filter(priority=int(priority))
    if due == "overdue":
        qs = qs.filter(due_date__lt=today).exclude(status=Task.Status.DONE)
    elif due == "week":
        qs = qs.filter(due_date__range=(today, today + timedelta(days=7)))
    elif due == "none":
        qs = qs.filter(due_date__isnull=True)
    return qs


def apply_move(task, user, status, order_ids):
    """Cambia el estado de la tarea y guarda el orden de su columna."""
    if not task.user_can_work_on(user):
        raise MoveError("No tienes permiso para mover esta tarea.", 403)
    if status not in Task.Status.values:
        raise MoveError("Estado no válido.", 400)
    if status != Task.Status.TODO:
        titles = list(task.open_blockers().values_list("title", flat=True))
        if titles:
            raise MoveError("Esta tarea está bloqueada por: " + ", ".join(titles), 409)

    with transaction.atomic():
        if task.status != status:
            old_status = task.status
            task.status = status
            task.save()
            notify_status_change(task, user, old_status)
            record(
                user, Activity.Verb.STATUS, task.project,
                f"movió «{task.title}» de {Task.Status(old_status).label} a {Task.Status(status).label}",
                task=task,
            )
        # Solo se reordenan tareas del MISMO proyecto
        valid = set(
            Task.objects.alive()
            .filter(project_id=task.project_id, parent__isnull=True, pk__in=order_ids)
            .values_list("pk", flat=True)
        )
        for position, task_id in enumerate(i for i in order_ids if i in valid):
            Task.objects.filter(pk=task_id).update(position=position)