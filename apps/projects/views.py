from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, Sum
from apps.tasks.models import Task, TimeLog
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from apps.tasks.models import Task

from apps.core.mixins import CompanyRequiredMixin, RoleRequiredMixin
from .forms import ProjectForm, ProjectMemberForm
from .models import Project, ProjectMember

User = get_user_model()


class ProjectQuerysetMixin(CompanyRequiredMixin):
    """Solo proyectos vivos que el usuario tiene permitido ver."""
    model = Project

    def get_queryset(self):
        return Project.objects.alive().for_user(self.request.user)


class ProjectManageMixin(ProjectQuerysetMixin):
    """Además exige permiso de gestión sobre el proyecto concreto."""

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.user_can_manage(self.request.user):
            raise PermissionDenied
        return obj


def _members_ctx(project, user, form=None):
    can_manage = project.user_can_manage(user)
    return {
        "project": project,
        "members": project.members.select_related("user").order_by("user__first_name", "user__username"),
        "can_manage": can_manage,
        "form": form or (ProjectMemberForm(project=project) if can_manage else None),
    }


class ProjectListView(ProjectQuerysetMixin, ListView):
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(client_name__icontains=q))
        if status in Project.Status.values:
            qs = qs.filter(status=status)
        return qs.annotate(member_count=Count("members"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["status"] = self.request.GET.get("status", "")
        ctx["statuses"] = Project.Status.choices
        return ctx


class ProjectDetailView(ProjectQuerysetMixin, DetailView):
    template_name = "projects/project_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_members_ctx(self.object, self.request.user))

        counts = dict(
            Task.objects.alive()
            .filter(project=self.object, parent__isnull=True)
            .order_by()
            .values_list("status")
            .annotate(n=Count("id"))
        )
        total = sum(counts.values())
        done = counts.get(Task.Status.DONE, 0)
        alive_tasks = Task.objects.alive().filter(project=self.object, parent__isnull=True)
        ctx["hours_estimated"] = alive_tasks.aggregate(t=Sum("estimated_hours"))["t"] or 0
        ctx["hours_logged"] = TimeLog.objects.filter(task__in=alive_tasks).aggregate(t=Sum("hours"))["t"] or 0
        ctx["task_counts"] = [(label, counts.get(value, 0)) for value, label in Task.Status.choices]
        ctx["task_total"] = total
        ctx["task_done"] = done
        ctx["progress"] = round(done * 100 / total) if total else 0
        return ctx


class ProjectCreateView(SuccessMessageMixin, RoleRequiredMixin, CreateView):
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    allowed_roles = (User.Role.ADMIN, User.Role.PM)
    success_message = "Proyecto creado correctamente."

    @transaction.atomic
    def form_valid(self, form):
        form.instance.company = self.request.user.company
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        ProjectMember.objects.create(
            project=self.object, user=self.request.user, role=ProjectMember.Role.MANAGER
        )
        return response


class ProjectUpdateView(SuccessMessageMixin, ProjectManageMixin, UpdateView):
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_message = "Proyecto actualizado."


class ProjectDeleteView(ProjectManageMixin, DeleteView):
    template_name = "projects/project_confirm_delete.html"
    success_url = reverse_lazy("project_list")

    def form_valid(self, form):
        self.object.soft_delete()
        messages.success(self.request, "Proyecto eliminado.")
        return HttpResponseRedirect(self.get_success_url())


# ---- Miembros (respuestas parciales para HTMX) ----

class _MemberActionView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def get_project(self, request, pk):
        project = get_object_or_404(Project.objects.alive().for_user(request.user), pk=pk)
        if not project.user_can_manage(request.user):
            raise PermissionDenied
        return project


class ProjectMemberAddView(_MemberActionView):
    def post(self, request, pk):
        project = self.get_project(request, pk)
        form = ProjectMemberForm(request.POST, project=project)
        if form.is_valid():
            form.save()
            form = None  # formulario limpio en la respuesta
        return render(request, "projects/partials/members.html", _members_ctx(project, request.user, form))


class ProjectMemberRemoveView(_MemberActionView):
    def post(self, request, pk, member_pk):
        project = self.get_project(request, pk)
        get_object_or_404(project.members, pk=member_pk).delete()
        return render(request, "projects/partials/members.html", _members_ctx(project, request.user))