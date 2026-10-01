from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.forms import TailwindFormMixin
from apps.projects.models import ProjectMember
from .models import Attachment, Comment, Task, TimeLog

User = get_user_model()

BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".sh", ".ps1", ".vbs", ".jar"}


class TaskForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title", "description", "status", "priority", "assignees",
            "start_date", "due_date", "estimated_hours", "blocked_by",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "assignees": forms.CheckboxSelectMultiple(attrs={"class": "space-y-1"}),
            "blocked_by": forms.SelectMultiple(attrs={"size": 5}),
        }
        help_texts = {
            "blocked_by": "No podrá iniciar hasta que las tareas elegidas estén en «Hecho». "
                          "Ctrl/Cmd para elegir varias.",
        }

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

        # Solo miembros activos del proyecto con rol Responsable o Miembro
        self.fields["assignees"].queryset = User.objects.filter(
            is_active=True,
            project_memberships__project=project,
            project_memberships__role__in=[ProjectMember.Role.MANAGER, ProjectMember.Role.MEMBER],
        ).order_by("first_name", "username")
        self.fields["assignees"].label_from_instance = lambda u: u.get_full_name() or u.username

        # Solo tareas principales del mismo proyecto
        blockers = Task.objects.alive().filter(project=project, parent__isnull=True)
        if self.instance.pk:
            blockers = blockers.exclude(pk=self.instance.pk)
        self.fields["blocked_by"].queryset = blockers

    def clean(self):
        cleaned = super().clean()
        start, due = cleaned.get("start_date"), cleaned.get("due_date")
        if start and due and due < start:
            self.add_error("due_date", "La fecha límite no puede ser anterior a la de inicio.")
        if self.instance.pk:
            for blocker in cleaned.get("blocked_by", []):
                if blocker.depends_on(self.instance.pk):
                    self.add_error(
                        "blocked_by",
                        f"«{blocker.title}» ya depende de esta tarea (dependencia circular).",
                    )
        return cleaned


class SubtaskForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title"]
        labels = {"title": "Nueva subtarea"}


class CommentForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        labels = {"body": "Escribe un comentario"}
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}


class AttachmentForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file"]
        labels = {"file": "Subir archivo"}

    def clean_file(self):
        f = self.cleaned_data["file"]
        max_mb = settings.MAX_UPLOAD_MB
        if f.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"El archivo supera el máximo de {max_mb} MB.")
        if Path(f.name).suffix.lower() in BLOCKED_EXTENSIONS:
            raise forms.ValidationError("Este tipo de archivo no está permitido.")
        return f
    
class TimeLogForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = TimeLog
        fields = ["date", "hours", "description"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hours": forms.NumberInput(attrs={"step": "0.25", "min": "0.25"}),
        }
        labels = {"description": "¿Qué hiciste? (opcional)"}

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError("No puedes registrar horas en una fecha futura.")
        return value