from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone


def send_invitation_email(request, invitation):
    link = request.build_absolute_uri(reverse("accept_invitation", args=[invitation.token]))
    inviter = invitation.invited_by.get_full_name() or invitation.invited_by.username
    expires = timezone.localtime(invitation.expires_at)
    message = (
        f"Hola,\n\n"
        f"{inviter} te invitó a unirte a {invitation.company.name} en TaskFlow "
        f"como {invitation.get_role_display()}.\n\n"
        f"Crea tu cuenta aquí (el enlace vence el {expires:%d/%m/%Y}):\n{link}\n\n"
        f"Si no esperabas este correo, puedes ignorarlo."
    )
    send_mail(
        subject=f"Te invitaron a {invitation.company.name} en TaskFlow",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
    )