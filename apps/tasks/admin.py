from django.contrib import admin
from .models import Attachment, Comment, Task, TimeLog

admin.site.register(TimeLog)


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "parent", "status", "priority", "due_date", "deleted_at")
    list_filter = ("status", "priority", "project__company")
    search_fields = ("title",)
    inlines = [CommentInline]


admin.site.register(Attachment)