from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class CompanyQuerysetMixin(LoginRequiredMixin):
    """
    Para vistas de lista/detalle/edición/borrado.
    Filtra SIEMPRE por la empresa del usuario en sesión.
    El modelo debe tener un campo `company`.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.company_id:
            return qs.none()
        return qs.filter(company=self.request.user.company)


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in self.allowed_roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)