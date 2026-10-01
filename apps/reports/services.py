from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from apps.projects.models import Project
from apps.tasks.models import Task, TimeLog

User = get_user_model()

DONE = Task.Status.DONE
OPEN_STATUSES = [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.REVIEW]
WEEKS = 8


def _pct(part, total):
    return round(part * 100 / total) if total else 0


def _h(value):
    return round(float(value or 0), 2)


def _as_date(value):
    return value.date() if isinstance(value, datetime) else value


def _conds(prefix, today):
    """
    Condiciones reutilizables. `prefix` es "" sobre Task y "task__" sobre la
    tabla intermedia de responsables. Se evitan negaciones (~Q) a propósito.
    """
    p = prefix
    done = Q(**{f"{p}status": DONE})
    has_due = Q(**{f"{p}due_date__isnull": False})
    return {
        "done": done,
        "overdue": Q(**{f"{p}due_date__lt": today, f"{p}status__in": OPEN_STATUSES}),
        "on_time": done & has_due & Q(**{f"{p}completed_at__date__lte": F(f"{p}due_date")}),
        "late": done & has_due & Q(**{f"{p}completed_at__date__gt": F(f"{p}due_date")}),
    }


def build_report(user, project=None):
    """
    Datos del reporte para `user`. Solo considera proyectos que el usuario
    puede ver; si se indica `project`, se limita a ese.
    """
    today = timezone.localdate()
    projects_qs = Project.objects.alive().for_user(user)
    if project:
        projects_qs = projects_qs.filter(pk=project.pk)

    tasks = Task.objects.alive().filter(
        project_id__in=projects_qs.values("pk"), parent__isnull=True
    )
    logs = TimeLog.objects.filter(task_id__in=tasks.values("pk"))

    # ---- Resumen ----
    c = _conds("", today)
    agg = tasks.aggregate(
        total=Count("id"),
        done=Count("id", filter=c["done"]),
        overdue=Count("id", filter=c["overdue"]),
        on_time=Count("id", filter=c["on_time"]),
        late=Count("id", filter=c["late"]),
        estimated=Sum("estimated_hours"),
    )
    logged = logs.aggregate(t=Sum("hours"))["t"]
    closed_with_due = agg["on_time"] + agg["late"]
    summary = {
        "total": agg["total"],
        "done": agg["done"],
        "pending": agg["total"] - agg["done"],
        "progress": _pct(agg["done"], agg["total"]),
        "overdue": agg["overdue"],
        "on_time": agg["on_time"],
        "late": agg["late"],
        "punctuality": _pct(agg["on_time"], closed_with_due) if closed_with_due else None,
        "estimated": _h(agg["estimated"]),
        "logged": _h(logged),
    }

    # ---- Tareas por estado ----
    counts = dict(tasks.order_by().values_list("status").annotate(n=Count("id")))
    status = [(label, counts.get(value, 0)) for value, label in Task.Status.choices]

    # ---- Por proyecto ----
    alive_parent = Q(tasks__parent__isnull=True, tasks__deleted_at__isnull=True)
    estimated_by_project = dict(
        tasks.order_by().values_list("project_id").annotate(e=Sum("estimated_hours"))
    )
    logged_by_project = dict(
        logs.order_by().values_list("task__project_id").annotate(h=Sum("hours"))
    )
    project_rows = []
    annotated = projects_qs.annotate(
        t_total=Count("tasks", filter=alive_parent),
        t_done=Count("tasks", filter=alive_parent & Q(tasks__status=DONE)),
        t_overdue=Count(
            "tasks",
            filter=alive_parent & Q(tasks__due_date__lt=today, tasks__status__in=OPEN_STATUSES),
        ),
    ).order_by("name")
    for p in annotated:
        project_rows.append({
            "name": p.name,
            "status": p.get_status_display(),
            "total": p.t_total,
            "done": p.t_done,
            "progress": _pct(p.t_done, p.t_total),
            "overdue": p.t_overdue,
            "estimated": _h(estimated_by_project.get(p.pk)),
            "logged": _h(logged_by_project.get(p.pk)),
        })

    # ---- Por empleado ----
    c2 = _conds("task__", today)
    through = Task.assignees.through
    per_user = {}
    rows = (
        through.objects.filter(task_id__in=tasks.values("pk"))
        .order_by()
        .values("user_id")
        .annotate(
            assigned=Count("id"),
            done=Count("id", filter=c2["done"]),
            overdue=Count("id", filter=c2["overdue"]),
            on_time=Count("id", filter=c2["on_time"]),
            late=Count("id", filter=c2["late"]),
        )
    )
    for r in rows:
        per_user[r["user_id"]] = r
    hours_by_user = {
        uid: h
        for uid, h in logs.order_by().values_list("user_id").annotate(h=Sum("hours"))
        if uid is not None
    }
    users = User.objects.in_bulk(set(per_user) | set(hours_by_user))
    employee_rows = []
    for uid, u in users.items():
        r = per_user.get(uid, {})
        on_time, late = r.get("on_time", 0), r.get("late", 0)
        assigned, done = r.get("assigned", 0), r.get("done", 0)
        employee_rows.append({
            "user_id": uid,
            "name": u.get_full_name() or u.username,
            "assigned": assigned,
            "done": done,
            "pending": assigned - done,
            "overdue": r.get("overdue", 0),
            "on_time": on_time,
            "late": late,
            "punctuality": _pct(on_time, on_time + late) if (on_time + late) else None,
            "hours": _h(hours_by_user.get(uid)),
        })
    employee_rows.sort(key=lambda e: e["name"].lower())

    # ---- Horas por semana (últimas 8) ----
    monday = today - timedelta(days=today.weekday())
    start = monday - timedelta(weeks=WEEKS - 1)
    raw = {
        _as_date(week): hours
        for week, hours in logs.filter(date__gte=start)
        .order_by()
        .annotate(w=TruncWeek("date"))
        .values_list("w")
        .annotate(h=Sum("hours"))
    }
    weeks = []
    for i in range(WEEKS):
        day = start + timedelta(weeks=i)
        weeks.append((day.strftime("%d/%m"), _h(raw.get(day))))

    return {
        "scope": project.name if project else "Todos los proyectos",
        "generated_at": timezone.localtime(),
        "summary": summary,
        "status": status,
        "projects": project_rows,
        "employees": employee_rows,
        "weeks": weeks,
    }


def chart_payload(report):
    """Datos listos para Chart.js (se inyectan con json_script)."""
    s = report["summary"]
    emps, projs = report["employees"], report["projects"]
    return {
        "status": {
            "labels": [label for label, _ in report["status"]],
            "values": [n for _, n in report["status"]],
        },
        "punctuality": {"labels": ["A tiempo", "Con retraso"], "values": [s["on_time"], s["late"]]},
        "employees": {
            "labels": [e["name"] for e in emps],
            "done": [e["done"] for e in emps],
            "pending": [e["pending"] for e in emps],
        },
        "projects": {
            "labels": [p["name"] for p in projs],
            "estimated": [p["estimated"] for p in projs],
            "logged": [p["logged"] for p in projs],
        },
        "weeks": {
            "labels": [label for label, _ in report["weeks"]],
            "values": [h for _, h in report["weeks"]],
        },
    }