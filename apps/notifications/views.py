from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import ListView, UpdateView

from apps.tasks.models import Task
from .forms import PreferencesForm
from .models import Notification, NotificationPreference


def bell_context(user):
    qs = Notification.objects.filter(recipient=user)
    return {"unread_count": qs.filter(read_at__isnull=True).count(), "latest": list(qs[:6])}


@require_GET
def bell(request):
    """Fragmento HTMX de la campana (se actualiza cada 30 s)."""
    if not request.user.is_authenticated:
        return HttpResponse(status=204)     # sesión vencida: HTMX no cambia nada
    return render(request, "notifications/partials/bell.html", bell_context(request.user))


@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
    visible = (
        n.task_id
        and Task.objects.alive().for_user(request.user).filter(pk=n.task_id, parent__isnull=True).exists()
    )
    if visible:
        return redirect("task_detail", pk=n.task_id)
    messages.info(request, "Esa tarea ya no está disponible.")
    return redirect("notification_list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    if request.htmx:
        return render(request, "notifications/partials/bell.html", bell_context(request.user))
    return redirect("notification_list")


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class PreferencesView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = PreferencesForm
    template_name = "notifications/preferences.html"
    success_url = reverse_lazy("notification_preferences")
    success_message = "Preferencias guardadas."

    def get_object(self, queryset=None):
        return NotificationPreference.for_user(self.request.user)