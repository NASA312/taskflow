from django.conf import settings
from django.db import models

from apps.projects.models import Project


class ActivityQuerySet(models.QuerySet):
    def for_user(self, user):
        """Actividad de los proyectos que `user` puede ver. Los clientes no ven nada."""
        if not user.is_authenticated or not user.company_id or user.role == user.Role.CLIENT:
            return self.none()
        visible = Project.objects.alive().for_user(user).values("pk")
        return self.filter(project_id__in=visible)


class Activity(models.Model):
    class Verb(models.TextChoices):
        CREATED = "created", "Creación"
        UPDATED = "updated", "Edición"
        STATUS = "status", "Cambio de estado"
        DELETED = "deleted", "Eliminación"
        MEMBER = "member", "Equipo"
        SUBTASK = "subtask", "Subtareas"
        COMMENT = "comment", "Comentarios"
        FILE = "file", "Archivos"
        HOURS = "hours", "Horas"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activities")
    task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="activities"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ActivityQuerySet.as_manager()

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividad"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["project", "-created_at"]),
            models.Index(fields=["task", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.actor}: {self.message}"