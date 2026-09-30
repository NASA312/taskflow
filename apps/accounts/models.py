from django.contrib.auth.models import AbstractUser
from django.db import models


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