from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("message", "recipient", "kind", "created_at", "read_at", "emailed_at")
    list_filter = ("kind",)
    search_fields = ("message", "recipient__username")


admin.site.register(NotificationPreference)