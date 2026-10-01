from io import BytesIO

from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import RoleRequiredMixin
from apps.projects.models import Project
from .exports import build_excel, build_pdf
from .services import build_report, chart_payload

User = get_user_model()


class ReportMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.PM)

    def load_report(self):
        visible = Project.objects.alive().for_user(self.request.user)
        raw = self.request.GET.get("project", "")
        project = None
        if raw:
            if not raw.isdigit():
                raise Http404
            project = get_object_or_404(visible, pk=int(raw))   # otra empresa o sin acceso: 404
        return build_report(self.request.user, project), visible, project


class ReportDashboardView(ReportMixin, TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        report, visible, project = self.load_report()
        ctx.update(
            report=report,
            chart_data=chart_payload(report),
            projects=visible.order_by("name"),
            project=project,
            query=f"?project={project.pk}" if project else "",
        )
        return ctx


class ReportExportView(ReportMixin, View):
    fmt = "pdf"

    def get(self, request):
        report, _, _ = self.load_report()
        name = f"reporte-{slugify(report['scope']) or 'proyectos'}-{timezone.localdate().isoformat()}"
        if self.fmt == "excel":
            data = build_excel(report)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{name}.xlsx"
        else:
            data = build_pdf(report)
            content_type = "application/pdf"
            filename = f"{name}.pdf"
        return FileResponse(BytesIO(data), as_attachment=True, filename=filename, content_type=content_type)