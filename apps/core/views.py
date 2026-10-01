from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from apps.projects.models import Project


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.company_id:
            projects = Project.objects.alive().for_user(user)
            ctx["active_projects"] = projects.filter(
                status__in=[Project.Status.PLANNING, Project.Status.IN_PROGRESS]
            ).count()
            ctx["recent_projects"] = projects[:5]
        return ctx