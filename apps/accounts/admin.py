from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Empresa y rol", {"fields": ("company", "team", "role", "avatar", "phone")}),
    )
    list_display = ("username", "email", "company", "role", "is_active")
    list_filter = ("company", "role", "is_active")