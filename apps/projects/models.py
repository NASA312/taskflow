from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SoftDeleteModel, SoftDeleteQuerySet, TimeStampedModel


class ProjectQuerySet(SoftDeleteQuerySet):
    def for_user(self, user):
        """Proyectos que `user` tiene permitido ver."""
        if not user.is_authenticated or not user.company_id:
            return self.none()
        qs = self.filter(company_id=user.company_id)
        if user.is_company_admin:
            return qs
        member_of = ProjectMember.objects.filter(user=user).values("project_id")
        return qs.filter(pk__in=member_of)


class Project(TimeStampedModel, SoftDeleteModel):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planificación"
        IN_PROGRESS = "in_progress", "En progreso"
        ON_HOLD = "on_hold", "En pausa"
        COMPLETED = "completed", "Completado"
        CANCELLED = "cancelled", "Cancelado"

    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField("Nombre", max_length=150)
    description = models.TextField("Descripción", blank=True)
    client_name = models.CharField("Cliente", max_length=150, blank=True)
    status = models.CharField(
        "Estado", max_length=20, choices=Status.choices, default=Status.PLANNING
    )
    budget = models.DecimalField(
        "Presupuesto", max_digits=12, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateField("Fecha de inicio", null=True, blank=True)
    end_date = models.DateField("Fecha estimada de cierre", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_projects",
    )

    objects = ProjectQuerySet.as_manager()

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["end_date"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("project_detail", args=[self.pk])

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("La fecha de cierre no puede ser anterior a la de inicio.")

    @property
    def is_overdue(self):
        closed = (self.Status.COMPLETED, self.Status.CANCELLED)
        return bool(
            self.end_date and self.end_date < timezone.localdate() and self.status not in closed
        )

    def user_can_manage(self, user):
        """Editar, eliminar y gestionar miembros."""
        if not user.is_authenticated or user.company_id != self.company_id:
            return False
        if user.is_company_admin:
            return True
        return (
            user.role == user.Role.PM
            and self.members.filter(user=user, role=ProjectMember.Role.MANAGER).exists()
        )


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "Responsable"
        MEMBER = "member", "Miembro"
        VIEWER = "viewer", "Solo lectura"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField("Rol en el proyecto", max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Miembro del proyecto"
        verbose_name_plural = "Miembros del proyecto"
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_member")
        ]

    def __str__(self):
        return f"{self.user} en {self.project}"

    def clean(self):
        if self.project_id and self.user_id and self.user.company_id != self.project.company_id:
            raise ValidationError("El usuario pertenece a otra empresa.")