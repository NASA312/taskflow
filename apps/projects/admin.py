from django.contrib import admin
from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "status", "end_date", "deleted_at")
    list_filter = ("company", "status")
    search_fields = ("name", "client_name")
    inlines = [ProjectMemberInline]