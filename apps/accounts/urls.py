from django.urls import path
from . import views

urlpatterns = [
    path("equipo/", views.TeamListView.as_view(), name="team_list"),
    path("equipo/invitar/", views.InviteCreateView.as_view(), name="invite_create"),
    path("equipo/invitaciones/<int:pk>/cancelar/", views.InvitationRevokeView.as_view(), name="invitation_revoke"),
    path("invitacion/<str:token>/", views.accept_invitation, name="accept_invitation"),
]