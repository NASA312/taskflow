from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador de empresa"
        PM = "pm", "Project Manager"
        EMPLOYEE = "employee", "Empleado"
        CLIENT = "client", "Cliente"

    company = models.ForeignKey(
        "companies.Company", null=True, blank=True,
        on_delete=models.CASCADE, related_name="users",
    )
    team = models.ForeignKey(
        "companies.Team", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="members",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    phone = models.CharField(max_length=30, blank=True)

    @property
    def is_company_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def can_manage_projects(self):
        return self.role in (self.Role.ADMIN, self.Role.PM)
    
def generate_token():
    return secrets.token_urlsafe(32)


def default_expiry():
    return timezone.now() + timedelta(days=getattr(settings, "INVITATION_EXPIRY_DAYS", 7))


class Invitation(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField("Correo")
    role = models.CharField("Rol", max_length=20, choices=User.Role.choices, default=User.Role.EMPLOYEE)
    team = models.ForeignKey("companies.Team", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Equipo")
    token = models.CharField(max_length=64, unique=True, default=generate_token, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="sent_invitations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Invitación"
        verbose_name_plural = "Invitaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} → {self.company}"

    @property
    def is_pending(self):
        return self.accepted_at is None and self.expires_at > timezone.now()