from django.urls import path
from . import views

urlpatterns = [
    path("mis-tareas/", views.MyTasksView.as_view(), name="my_tasks"),
    path("proyectos/<int:pk>/tablero/", views.ProjectBoardView.as_view(), name="project_board"),
    path("proyectos/<int:project_pk>/tareas/nueva/", views.TaskCreateView.as_view(), name="task_create"),

    path("tareas/<int:pk>/", views.TaskDetailView.as_view(), name="task_detail"),
    path("tareas/<int:pk>/editar/", views.TaskUpdateView.as_view(), name="task_update"),
    path("tareas/<int:pk>/eliminar/", views.TaskDeleteView.as_view(), name="task_delete"),
    path("tareas/<int:pk>/mover/", views.TaskMoveView.as_view(), name="task_move"),
    path("tareas/<int:pk>/estado/", views.TaskStatusView.as_view(), name="task_status"),

    path("tareas/<int:pk>/subtareas/agregar/", views.SubtaskAddView.as_view(), name="subtask_add"),
    path("tareas/<int:pk>/subtareas/<int:sub_pk>/alternar/", views.SubtaskToggleView.as_view(), name="subtask_toggle"),
    path("tareas/<int:pk>/subtareas/<int:sub_pk>/eliminar/", views.SubtaskDeleteView.as_view(), name="subtask_delete"),

    path("tareas/<int:pk>/comentarios/agregar/", views.CommentAddView.as_view(), name="comment_add"),
    path("tareas/<int:pk>/comentarios/<int:comment_pk>/eliminar/", views.CommentDeleteView.as_view(), name="comment_delete"),

    path("tareas/<int:pk>/adjuntos/agregar/", views.AttachmentAddView.as_view(), name="attachment_add"),
    path("tareas/<int:pk>/adjuntos/<int:attachment_pk>/descargar/", views.AttachmentDownloadView.as_view(), name="attachment_download"),
    path("tareas/<int:pk>/adjuntos/<int:attachment_pk>/eliminar/", views.AttachmentDeleteView.as_view(), name="attachment_delete"),
    
    path("tareas/<int:pk>/horas/agregar/", views.TimeLogAddView.as_view(), name="timelog_add"),
    path("tareas/<int:pk>/horas/<int:log_pk>/eliminar/", views.TimeLogDeleteView.as_view(), name="timelog_delete"),
]