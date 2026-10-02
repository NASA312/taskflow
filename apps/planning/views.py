from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import DetailView, TemplateView

from apps.core.mixins import CompanyRequiredMixin
from apps.projects.models import Project
from apps.projects.views import ProjectQuerysetMixin
from .services import build_gantt, build_month, parse_month


class CalendarView(CompanyRequiredMixin, TemplateView):
    template_name = "planning/calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user, params = self.request.user, self.request.GET
        year, month = parse_month(params.get("y"), params.get("m"), timezone.localdate())

        visible = Project.objects.alive().for_user(user)
        project = None
        raw = params.get("project", "")
        if raw:
            if not raw.isdigit():
                raise Http404
            project = get_object_or_404(visible, pk=int(raw))      # otra empresa o sin acceso: 404
        mine = params.get("mine") == "1"

        extra = {}
        if project:
            extra["project"] = project.pk
        if mine:
            extra["mine"] = 1
        ctx.update(
            cal=build_month(user, year, month, project, mine),
            projects=visible.order_by("name"),
            project=project,
            mine=mine,
            extra=("&" + urlencode(extra)) if extra else "",
        )
        return ctx


class GanttView(ProjectQuerysetMixin, DetailView):
    """Solo proyectos que el usuario puede ver (si no, 404)."""
    template_name = "planning/gantt.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        gantt = build_gantt(self.object, self.request.GET.get("zoom", "week"))
        ctx.update(
            gantt=gantt,
            zoom=gantt["zoom"],
            zooms=[("day", "Días"), ("week", "Semanas"), ("month", "Meses")],
        )
        return ctx