from django.urls import path
from . import views

urlpatterns = [
    path("empresa/crear/", views.CompanyCreateView.as_view(), name="company_create"),
]