from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, TemplateView

from apps.core.mixins import RoleRequiredMixin
from .emails import send_invitation_email
from .forms import AcceptInvitationForm, InvitationForm
from .models import Invitation, User


class TeamListView(RoleRequiredMixin, TemplateView):
    allowed_roles = (User.Role.ADMIN,)
    template_name = "accounts/team_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.request.user.company
        ctx["members"] = User.objects.filter(company=company).select_related("team").order_by("first_name", "username")
        ctx["pending"] = Invitation.objects.filter(
            company=company, accepted_at__isnull=True, expires_at__gt=timezone.now()
        ).select_related("team")
        return ctx


class InviteCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = (User.Role.ADMIN,)
    model = Invitation
    form_class = InvitationForm
    template_name = "accounts/invite_form.html"
    success_url = reverse_lazy("team_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        company = self.request.user.company
        # Si ya había una invitación pendiente para ese correo, se reemplaza
        Invitation.objects.filter(
            company=company, email=form.cleaned_data["email"], accepted_at__isnull=True
        ).delete()
        form.instance.company = company
        form.instance.invited_by = self.request.user
        response = super().form_valid(form)
        send_invitation_email(self.request, self.object)
        messages.success(self.request, f"Invitación enviada a {self.object.email}.")
        return response


class InvitationRevokeView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.ADMIN,)
    http_method_names = ["post"]

    def post(self, request, pk):
        invitation = get_object_or_404(
            Invitation, pk=pk, company=request.user.company, accepted_at__isnull=True
        )
        invitation.delete()
        messages.success(request, "Invitación cancelada.")
        return redirect("team_list")


def accept_invitation(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if not invitation.is_pending:
        return render(request, "accounts/invitation_invalid.html", status=410)

    if request.method == "POST":
        form = AcceptInvitationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.email = invitation.email
                user.company = invitation.company
                user.role = invitation.role
                user.team = invitation.team
                user.save()
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=["accepted_at"])
            login(request, user)
            messages.success(request, f"¡Bienvenido a {invitation.company.name}!")
            return redirect("dashboard")
    else:
        form = AcceptInvitationForm()

    return render(request, "accounts/accept_invitation.html", {"form": form, "invitation": invitation})