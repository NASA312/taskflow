from django.contrib.auth import get_user_model
from django.views.generic import ListView

from apps.core.mixins import RoleRequiredMixin
from apps.projects.models import Project
from .models import Activity

User = get_user_model()


class ActivityListView(RoleRequiredMixin, ListView):
    allowed_roles = (User.Role.ADMIN, User.Role.PM, User.Role.EMPLOYEE)
    template_name = "activity/activity_list.html"
    context_object_name = "activities"
    paginate_by = 30

    def get_queryset(self):
        # Parte siempre de lo que el usuario puede ver: pedir un id ajeno devuelve vacío
        qs = Activity.objects.for_user(self.request.user).select_related("actor", "project", "task")
        p = self.request.GET
        if p.get("project", "").isdigit():
            qs = qs.filter(project_id=int(p["project"]))
        if p.get("actor", "").isdigit():
            qs = qs.filter(actor_id=int(p["actor"]))
        if p.get("verb") in Activity.Verb.values:
            qs = qs.filter(verb=p["verb"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user, get = self.request.user, self.request.GET
        params = get.copy()
        params.pop("page", None)
        # Solo aparecen como filtro personas que realmente figuran en actividad visible para el usuario
        visible_actors = Activity.objects.for_user(user).order_by().values("actor_id")
        ctx.update(
            filters={k: get.get(k, "") for k in ("project", "actor", "verb")},
            projects=Project.objects.alive().for_user(user).order_by("name"),
            actors=User.objects.filter(pk__in=visible_actors).order_by("first_name", "username"),
            verbs=Activity.Verb.choices,
            extra=("&" + params.urlencode()) if params else "",
        )
        return ctx