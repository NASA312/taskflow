from django.urls import path
from . import views

urlpatterns = [
    path("actividad/", views.ActivityListView.as_view(), name="activity_list"),
]