from django.urls import path
from . import views

urlpatterns = [
    path("notificaciones/", views.NotificationListView.as_view(), name="notification_list"),
    path("notificaciones/campana/", views.bell, name="notification_bell"),
    path("notificaciones/marcar-leidas/", views.mark_all_read, name="notification_mark_all"),
    path("notificaciones/preferencias/", views.PreferencesView.as_view(), name="notification_preferences"),
    path("notificaciones/<int:pk>/abrir/", views.notification_open, name="notification_open"),
]