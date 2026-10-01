from django.urls import path
from . import views

urlpatterns = [
    path("proyectos/", views.ProjectListView.as_view(), name="project_list"),
    path("proyectos/nuevo/", views.ProjectCreateView.as_view(), name="project_create"),
    path("proyectos/<int:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path("proyectos/<int:pk>/editar/", views.ProjectUpdateView.as_view(), name="project_update"),
    path("proyectos/<int:pk>/eliminar/", views.ProjectDeleteView.as_view(), name="project_delete"),
    path("proyectos/<int:pk>/miembros/agregar/", views.ProjectMemberAddView.as_view(), name="project_member_add"),
    path("proyectos/<int:pk>/miembros/<int:member_pk>/quitar/", views.ProjectMemberRemoveView.as_view(), name="project_member_remove"),
]