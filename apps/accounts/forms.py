from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.companies.models import Team
from apps.core.forms import TailwindFormMixin
from .models import Invitation, User


class InvitationForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["email", "role", "team"]

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["team"].queryset = Team.objects.filter(company=company)
        self.fields["team"].required = False
        self.fields["team"].empty_label = "Sin equipo"
        # No se invitan administradores desde aquí
        self.fields["role"].choices = [
            (value, label) for value, label in User.Role.choices if value != User.Role.ADMIN
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(company=self.company, email__iexact=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo en tu empresa.")
        return email


class AcceptInvitationForm(TailwindFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True