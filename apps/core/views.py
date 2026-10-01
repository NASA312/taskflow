from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.utils import timezone
from django.views.generic import TemplateView

from apps.projects.models import Project
from apps.tasks.models import Task


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.company_id:
            today = timezone.localdate()
            projects = Project.objects.alive().for_user(user)
            ctx["active_projects"] = projects.filter(
                status__in=[Project.Status.PLANNING, Project.Status.IN_PROGRESS]
            ).count()
            ctx["recent_projects"] = projects[:5]

            mine = Task.objects.alive().for_user(user).open_assigned_to(user)
            ctx["my_pending"] = mine.count()
            ctx["due_this_week"] = mine.filter(
                due_date__range=(today, today + timedelta(days=7))
            ).count()
            ctx["overdue"] = mine.filter(due_date__lt=today).count()
            ctx["my_tasks"] = mine.select_related("project").order_by(
                F("due_date").asc(nulls_last=True), "-priority"
            )[:6]
        return ctx