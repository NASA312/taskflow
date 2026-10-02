from .models import Activity


def person(user):
    return (user.get_full_name() or user.username) if user else "Alguien"


def record(actor, verb, project, message, task=None):
    """Guarda un evento. El texto no incluye al autor: la plantilla lo muestra aparte."""
    return Activity.objects.create(
        project=project,
        task=task,
        actor=actor if getattr(actor, "pk", None) else None,
        verb=verb,
        message=message[:255],
    )


def changed_fields(form):
    """Nombres (en minúsculas) de los campos que cambió el formulario, separados por coma."""
    return ", ".join(str(form.fields[name].label or name).lower() for name in form.changed_data)