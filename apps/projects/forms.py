from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TailwindFormMixin
from .models import Project, ProjectMember

User = get_user_model()


class ProjectForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "client_name", "status", "budget", "start_date", "end_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La fecha de cierre no puede ser anterior a la de inicio.")
        return cleaned


class ProjectMemberForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectMember
        fields = ["user", "role"]
        labels = {"user": "Persona", "role": "Rol en el proyecto"}

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.instance.project = project
        # Solo usuarios ACTIVOS de la MISMA empresa que aún no son miembros
        self.fields["user"].queryset = (
            User.objects.filter(company_id=project.company_id, is_active=True)
            .exclude(project_memberships__project=project)
            .order_by("first_name", "username")
        )
        self.fields["user"].label_from_instance = (
            lambda u: f"{u.get_full_name() or u.username} ({u.get_role_display()})"
        )

    def clean(self):
        cleaned = super().clean()
        user, role = cleaned.get("user"), cleaned.get("role")
        if user and role and user.role == User.Role.CLIENT and role != ProjectMember.Role.VIEWER:
            self.add_error("role", "Los clientes solo pueden tener acceso de solo lectura.")
        return cleaned