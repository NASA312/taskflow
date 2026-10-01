from django import forms

from apps.core.forms import TailwindFormMixin
from .models import NotificationPreference


class PreferencesForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ["email_assigned", "email_comment", "email_status", "email_deadline"]