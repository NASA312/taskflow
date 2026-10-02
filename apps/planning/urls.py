from django.urls import path
from . import views

urlpatterns = [
    path("calendario/", views.CalendarView.as_view(), name="calendar_view"),
    path("proyectos/<int:pk>/gantt/", views.GanttView.as_view(), name="project_gantt"),
]