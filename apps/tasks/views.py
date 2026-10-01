from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from decimal import Decimal
from django.db.models import Count, F, Q, Sum 
from django.utils import timezone
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django.db.models import Prefetch

from apps.core.mixins import CompanyRequiredMixin
from apps.projects.models import Project
from apps.projects.views import ProjectQuerysetMixin
from .forms import AttachmentForm, CommentForm, SubtaskForm, TaskForm, TimeLogForm
from .models import Attachment, Comment, Task, TimeLog
from .services import MoveError, apply_filters, apply_move

User = get_user_model()


def get_task_or_404(user, pk):
    """Tarea principal visible para `user`. Si no puede verla: 404 (no se filtra que existe)."""
    qs = Task.objects.alive().for_user(user).filter(parent__isnull=True).select_related("project")
    return get_object_or_404(qs, pk=pk)


# ---------- Contextos de los bloques HTMX ----------

def subtasks_ctx(task, user, form=None):
    subs = list(task.subtasks.alive().order_by("position", "id"))
    can_work = task.user_can_work_on(user)
    return {
        "task": task,
        "subtasks": subs,
        "sub_done": sum(1 for s in subs if s.status == Task.Status.DONE),
        "can_work": can_work,
        "subtask_form": form or (SubtaskForm() if can_work else None),
    }


def comments_ctx(task, user, form=None):
    can_participate = task.project.user_can_participate(user)
    return {
        "task": task,
        "comments": task.comments.select_related("author"),
        "can_manage": task.project.user_can_manage(user),
        "can_participate": can_participate,
        "comment_form": form or (CommentForm() if can_participate else None),
    }


def attachments_ctx(task, user, form=None):
    can_participate = task.project.user_can_participate(user)
    return {
        "task": task,
        "attachments": task.attachments.select_related("uploaded_by"),
        "can_manage": task.project.user_can_manage(user),
        "can_participate": can_participate,
        "attachment_form": form or (AttachmentForm() if can_participate else None),
    }

def timelogs_ctx(task, user, form=None):
    can_participate = task.project.user_can_participate(user)
    logs = list(task.time_logs.select_related("user"))
    total = sum((log.hours for log in logs), Decimal("0"))
    pct = int(total * 100 / task.estimated_hours) if task.estimated_hours else 0
    return {
        "task": task,
        "time_logs": logs,
        "total_hours": total,
        "hours_pct": pct,
        "hours_pct_bar": min(pct, 100),
        "can_manage": task.project.user_can_manage(user),
        "can_participate": can_participate,
        "timelog_form": form or (
            TimeLogForm(initial={"date": timezone.localdate()}) if can_participate else None
        ),
    }
# ---------- Tablero ----------

class ProjectBoardView(ProjectQuerysetMixin, DetailView):
    template_name = "tasks/board.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project, user = self.object, self.request.user
        can_manage = project.user_can_manage(user)
        can_participate = project.user_can_participate(user)

        sub_alive = Q(subtasks__deleted_at__isnull=True)
        open_statuses = [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.REVIEW]
        tasks = (
            apply_filters(
                Task.objects.alive().filter(project=project, parent__isnull=True),
                self.request.GET, user,
            )
            .prefetch_related("assignees")
            .annotate(
                sub_total=Count("subtasks", filter=sub_alive, distinct=True),
                sub_done=Count(
                    "subtasks", filter=sub_alive & Q(subtasks__status=Task.Status.DONE), distinct=True
                ),
                blocked_count=Count(
                    "blocked_by",
                    filter=Q(blocked_by__deleted_at__isnull=True, blocked_by__status__in=open_statuses),
                    distinct=True,
                ),
            )
            .order_by("position", "id")
        )

        by_status = {value: [] for value in Task.Status.values}
        for t in tasks:
            assigned = any(a.pk == user.pk for a in t.assignees.all())
            t.movable = can_manage or (can_participate and assigned)
            by_status[t.status].append(t)

        params = self.request.GET
        filters = {k: params.get(k, "") for k in ("q", "assignee", "priority", "due")}
        ctx.update(
            columns=[(value, label, by_status[value]) for value, label in Task.Status.choices],
            can_manage=can_manage,
            filters=filters,
            has_filters=any(filters.values()),
            priorities=Task.Priority.choices,
            project_users=User.objects.filter(project_memberships__project=project)
            .order_by("first_name", "username"),
        )
        return ctx


# ---------- CRUD de tareas ----------

class TaskManageMixin(CompanyRequiredMixin):
    """Queryset visible + exige permiso de gestión sobre el proyecto de la tarea."""

    def get_queryset(self):
        return (
            Task.objects.alive().for_user(self.request.user)
            .filter(parent__isnull=True).select_related("project")
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.project.user_can_manage(self.request.user):
            raise PermissionDenied
        return obj


class TaskCreateView(SuccessMessageMixin, CompanyRequiredMixin, CreateView):
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_message = "Tarea creada."

    @cached_property
    def project(self):
        project = get_object_or_404(
            Project.objects.alive().for_user(self.request.user), pk=self.kwargs["project_pk"]
        )
        if not project.user_can_manage(self.request.user):
            raise PermissionDenied
        return project

    def get_initial(self):
        status = self.request.GET.get("status")
        return {"status": status} if status in Task.Status.values else {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        return ctx

    def form_valid(self, form):
        form.instance.project = self.project
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("project_board", args=[self.project.pk])


class TaskDetailView(CompanyRequiredMixin, DetailView):
    template_name = "tasks/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        return (
            Task.objects.alive().for_user(self.request.user)
            .filter(parent__isnull=True)
            .select_related("project", "created_by")
            .prefetch_related(
                "assignees",
                Prefetch("blocked_by", queryset=Task.objects.alive()),
                Prefetch("blocking", queryset=Task.objects.alive()),
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        task, user = self.object, self.request.user
        ctx["project"] = task.project
        ctx["can_manage"] = task.project.user_can_manage(user)
        ctx["can_work"] = task.user_can_work_on(user)
        ctx["statuses"] = Task.Status.choices
        ctx.update(subtasks_ctx(task, user))
        ctx.update(comments_ctx(task, user))
        ctx.update(attachments_ctx(task, user))
        ctx.update(timelogs_ctx(task, user))
        return ctx


class TaskUpdateView(SuccessMessageMixin, TaskManageMixin, UpdateView):
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_message = "Tarea actualizada."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.object.project
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.object.project
        return ctx


class TaskDeleteView(TaskManageMixin, DeleteView):
    template_name = "tasks/task_confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.object.project
        return ctx

    def get_success_url(self):
        return reverse("project_board", args=[self.object.project_id])

    def form_valid(self, form):
        self.object.soft_delete()
        messages.success(self.request, "Tarea eliminada.")
        return HttpResponseRedirect(self.get_success_url())


class MyTasksView(CompanyRequiredMixin, ListView):
    template_name = "tasks/my_tasks.html"
    context_object_name = "tasks"
    paginate_by = 20

    def get_queryset(self):
        return (
            Task.objects.alive().for_user(self.request.user)
            .open_assigned_to(self.request.user)
            .select_related("project")
            .order_by(F("due_date").asc(nulls_last=True), "-priority")
        )


# ---------- Acciones (POST) ----------

class _TaskActionView(CompanyRequiredMixin, View):
    http_method_names = ["post"]

    def get_task(self, pk):
        return get_task_or_404(self.request.user, pk)


class TaskMoveView(_TaskActionView):
    """Lo llama el drag-and-drop del tablero (responde JSON)."""

    def post(self, request, pk):
        task = self.get_task(pk)
        order = [int(i) for i in request.POST.getlist("order") if i.isdigit()]
        try:
            apply_move(task, request.user, request.POST.get("status", ""), order)
        except MoveError as exc:
            return JsonResponse({"error": exc.message}, status=exc.status)
        return JsonResponse({"ok": True})


class TaskStatusView(_TaskActionView):
    """Cambio de estado desde la página de detalle (redirige)."""

    def post(self, request, pk):
        task = self.get_task(pk)
        try:
            apply_move(task, request.user, request.POST.get("status", ""), [])
        except MoveError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, "Estado actualizado.")
        return redirect(task)


class SubtaskAddView(_TaskActionView):
    def post(self, request, pk):
        task = self.get_task(pk)
        if not task.user_can_work_on(request.user):
            raise PermissionDenied
        form = SubtaskForm(request.POST)
        if form.is_valid():
            Task.objects.create(
                project=task.project, parent=task,
                title=form.cleaned_data["title"], created_by=request.user,
            )
            form = None
        return render(request, "tasks/partials/subtasks.html", subtasks_ctx(task, request.user, form))


class SubtaskToggleView(_TaskActionView):
    def post(self, request, pk, sub_pk):
        task = self.get_task(pk)
        if not task.user_can_work_on(request.user):
            raise PermissionDenied
        sub = get_object_or_404(task.subtasks.alive(), pk=sub_pk)
        sub.status = Task.Status.TODO if sub.status == Task.Status.DONE else Task.Status.DONE
        sub.save()
        return render(request, "tasks/partials/subtasks.html", subtasks_ctx(task, request.user))


class SubtaskDeleteView(_TaskActionView):
    def post(self, request, pk, sub_pk):
        task = self.get_task(pk)
        if not task.user_can_work_on(request.user):
            raise PermissionDenied
        get_object_or_404(task.subtasks.alive(), pk=sub_pk).soft_delete()
        return render(request, "tasks/partials/subtasks.html", subtasks_ctx(task, request.user))


class CommentAddView(_TaskActionView):
    def post(self, request, pk):
        task = self.get_task(pk)
        if not task.project.user_can_participate(request.user):
            raise PermissionDenied
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            form = None
        return render(request, "tasks/partials/comments.html", comments_ctx(task, request.user, form))


class CommentDeleteView(_TaskActionView):
    def post(self, request, pk, comment_pk):
        task = self.get_task(pk)
        comment = get_object_or_404(task.comments, pk=comment_pk)
        if not (task.project.user_can_manage(request.user) or comment.author_id == request.user.pk):
            raise PermissionDenied
        comment.delete()
        return render(request, "tasks/partials/comments.html", comments_ctx(task, request.user))


class AttachmentAddView(_TaskActionView):
    def post(self, request, pk):
        task = self.get_task(pk)
        if not task.project.user_can_participate(request.user):
            raise PermissionDenied
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            attachment = form.save(commit=False)
            attachment.task = task
            attachment.uploaded_by = request.user
            attachment.filename = upload.name
            attachment.size = upload.size
            attachment.save()
            form = None
        return render(request, "tasks/partials/attachments.html", attachments_ctx(task, request.user, form))


class AttachmentDeleteView(_TaskActionView):
    def post(self, request, pk, attachment_pk):
        task = self.get_task(pk)
        attachment = get_object_or_404(task.attachments, pk=attachment_pk)
        if not (task.project.user_can_manage(request.user) or attachment.uploaded_by_id == request.user.pk):
            raise PermissionDenied
        attachment.file.delete(save=False)
        attachment.delete()
        return render(request, "tasks/partials/attachments.html", attachments_ctx(task, request.user))


class AttachmentDownloadView(CompanyRequiredMixin, View):
    """Descarga protegida: solo quien puede ver la tarea puede bajar el archivo."""

    def get(self, request, pk, attachment_pk):
        task = get_task_or_404(request.user, pk)
        attachment = get_object_or_404(task.attachments, pk=attachment_pk)
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.filename)

class TimeLogAddView(_TaskActionView):
    def post(self, request, pk):
        task = self.get_task(pk)
        if not task.project.user_can_participate(request.user):
            raise PermissionDenied
        form = TimeLogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.task = task
            log.user = request.user
            log.save()
            form = None
        return render(request, "tasks/partials/timelogs.html", timelogs_ctx(task, request.user, form))


class TimeLogDeleteView(_TaskActionView):
    def post(self, request, pk, log_pk):
        task = self.get_task(pk)
        log = get_object_or_404(task.time_logs, pk=log_pk)
        if not (task.project.user_can_manage(request.user) or log.user_id == request.user.pk):
            raise PermissionDenied
        log.delete()
        return render(request, "tasks/partials/timelogs.html", timelogs_ctx(task, request.user))