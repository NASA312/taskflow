from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class CompanyRequiredMixin(LoginRequiredMixin):
    """Exige sesión iniciada y que el usuario pertenezca a una empresa."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.company_id:
            raise PermissionDenied("Tu usuario no pertenece a ninguna empresa.")
        return super().dispatch(request, *args, **kwargs)


class CompanyQuerysetMixin(CompanyRequiredMixin):
    """Para modelos con campo `company`: filtra siempre por la empresa del usuario."""

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class RoleRequiredMixin(CompanyRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in self.allowed_roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)