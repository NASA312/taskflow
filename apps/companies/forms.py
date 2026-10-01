from django import forms

from apps.core.forms import TailwindFormMixin
from .models import Company


class CompanyForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name"]
        labels = {"name": "Nombre de la empresa"}