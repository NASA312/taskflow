from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.accounts.forms import AsyncPasswordResetForm, TailwindSetPasswordForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Recuperación de contraseña
    path("recuperar/", auth_views.PasswordResetView.as_view(form_class=AsyncPasswordResetForm), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("restablecer/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(form_class=TailwindSetPasswordForm),
         name="password_reset_confirm"),
    path("restablecer/listo/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    path("", include("apps.accounts.urls")),
    path("", include("apps.companies.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.tasks.urls")),
    path("", include("apps.reports.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.planning.urls")),
    path("", include("apps.activity.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)