from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.views.generic import CreateView

from .forms import CompanyForm
from .models import Company


class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = "companies/company_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Si el usuario ya tiene empresa, no puede crear otra
        if request.user.is_authenticated and request.user.company_id:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        company = form.save()
        user = self.request.user
        user.company = company
        user.role = user.Role.ADMIN
        user.save(update_fields=["company", "role"])
        messages.success(self.request, f"Empresa «{company.name}» creada. ¡Ya eres su administrador!")
        return redirect("dashboard")