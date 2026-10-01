import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator

from apps.core.models import SoftDeleteModel, SoftDeleteQuerySet, TimeStampedModel
from apps.projects.models import Project


class TaskQuerySet(SoftDeleteQuerySet):
    def for_user(self, user):
        """Tareas de los proyectos (vivos) que el usuario puede ver."""
        visible = Project.objects.alive().for_user(user).values("pk")
        return self.filter(project_id__in=visible)

    def open_assigned_to(self, user):
        return self.filter(assignees=user, parent__isnull=True).exclude(status=Task.Status.DONE)


class Task(TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        TODO = "todo", "Por hacer"
        IN_PROGRESS = "in_progress", "En proceso"
        REVIEW = "review", "En revisión"
        DONE = "done", "Hecho"

    class Priority(models.IntegerChoices):
        LOW = 1, "Baja"
        MEDIUM = 2, "Media"
        HIGH = 3, "Alta"
        URGENT = 4, "Urgente"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subtasks"
    )
    title = models.CharField("Título", max_length=200)
    description = models.TextField("Descripción", blank=True)
    status = models.CharField("Estado", max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.PositiveSmallIntegerField("Prioridad", choices=Priority.choices, default=Priority.MEDIUM)
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_tasks", verbose_name="Responsables"
    )
    blocked_by = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="blocking", verbose_name="Depende de"
    )
    start_date = models.DateField("Fecha de inicio", null=True, blank=True)
    due_date = models.DateField("Fecha límite", null=True, blank=True)
    estimated_hours = models.DecimalField("Horas estimadas", max_digits=6, decimal_places=2, null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_tasks"
    )

    objects = TaskQuerySet.as_manager()

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["project", "status", "position"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("task_detail", args=[self.pk])

    def clean(self):
        if self.parent_id:
            if self.parent.parent_id:
                raise ValidationError("Una subtarea no puede tener subtareas.")
            if self.parent.project_id != self.project_id:
                raise ValidationError("La subtarea debe pertenecer al mismo proyecto.")

    def save(self, *args, **kwargs):
        if self._state.adding and not self.position:
            last = Task.objects.filter(
                project_id=self.project_id, parent_id=self.parent_id, status=self.status
            ).aggregate(m=Max("position"))["m"]
            self.position = 0 if last is None else last + 1
        if self.status == self.Status.DONE:
            self.completed_at = self.completed_at or timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status != self.Status.DONE)

    def open_blockers(self):
        """Tareas de las que depende y que aún no están en 'Hecho'."""
        return self.blocked_by.alive().exclude(status=self.Status.DONE)

    def depends_on(self, target_id):
        """¿Depende esta tarea (directa o indirectamente) de la tarea `target_id`?"""
        seen, frontier = set(), {self.pk}
        while frontier:
            found = set(
                Task.objects.filter(pk__in=frontier).values_list("blocked_by", flat=True)
            ) - {None} - seen
            if target_id in found:
                return True
            seen |= found
            frontier = found
        return False

    def user_can_work_on(self, user):
        """Mover/cambiar estado y gestionar subtareas."""
        if self.project.user_can_manage(user):
            return True
        return self.project.user_can_participate(user) and self.assignees.filter(pk=user.pk).exists()


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="task_comments"
    )
    body = models.TextField("Comentario")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comentario"
        verbose_name_plural = "Comentarios"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comentario de {self.author} en {self.task}"


def attachment_path(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"attachments/{instance.task.project.company_id}/{uuid.uuid4().hex}{ext}"


class Attachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="task_attachments"
    )
    file = models.FileField("Archivo", upload_to=attachment_path)
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto"
        verbose_name_plural = "Adjuntos"
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename
    
class TimeLog(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_logs")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="time_logs"
    )
    date = models.DateField("Fecha", default=timezone.localdate)
    hours = models.DecimalField(
        "Horas", max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("24"))],
    )
    description = models.CharField("Descripción", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de horas"
        verbose_name_plural = "Registros de horas"
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["task", "date"]),
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.hours} h en {self.task}"