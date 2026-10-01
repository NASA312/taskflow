from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    class Kind(models.TextChoices):
        ASSIGNED = "assigned", "Asignación"
        COMMENT = "comment", "Comentario"
        STATUS = "status", "Cambio de estado"
        DUE_SOON = "due_soon", "Vence pronto"
        OVERDUE = "overdue", "Atrasada"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    task = models.ForeignKey(
        "tasks.Task", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    dedupe_key = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at", "-created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=~Q(dedupe_key=""),
                name="unique_notification_dedupe",
            )
        ]

    def __str__(self):
        return f"{self.recipient}: {self.message}"

    @property
    def is_read(self):
        return self.read_at is not None


PREF_FIELD = {
    Notification.Kind.ASSIGNED: "email_assigned",
    Notification.Kind.COMMENT: "email_comment",
    Notification.Kind.STATUS: "email_status",
    Notification.Kind.DUE_SOON: "email_deadline",
    Notification.Kind.OVERDUE: "email_deadline",
}


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    email_assigned = models.BooleanField("Cuando me asignen una tarea", default=True)
    email_comment = models.BooleanField("Cuando comenten en mis tareas", default=True)
    email_status = models.BooleanField("Cuando cambie el estado de mis tareas", default=True)
    email_deadline = models.BooleanField("Recordatorios de fechas límite", default=True)

    class Meta:
        verbose_name = "Preferencia de notificaciones"
        verbose_name_plural = "Preferencias de notificaciones"

    def __str__(self):
        return f"Preferencias de {self.user}"

    @classmethod
    def for_user(cls, user):
        return cls.objects.get_or_create(user=user)[0]

    def wants_email(self, kind):
        return getattr(self, PREF_FIELD[kind])