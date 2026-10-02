import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.projects.models import Project
from apps.tasks.models import Task

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# ---------------- Calendario ----------------

def parse_month(y, m, today):
    """Año y mes desde la URL; si algo no es válido, vuelve al mes actual."""
    try:
        year, month = int(y), int(m)
        if not (2000 <= year <= 2100 and 1 <= month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        return today.year, today.month
    return year, month


def build_month(user, year, month, project=None, mine=False):
    today = timezone.localdate()
    grid = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)   # semanas desde el lunes
    first, last = grid[0][0], grid[-1][-1]

    visible = Project.objects.alive().for_user(user)
    if project:
        visible = visible.filter(pk=project.pk)

    tasks = (
        Task.objects.alive()
        .filter(project_id__in=visible.values("pk"), parent__isnull=True, due_date__range=(first, last))
        .select_related("project")
        .order_by("due_date", "-priority", "id")
    )
    if mine:
        tasks = tasks.filter(assignees=user)

    by_day, closing = defaultdict(list), defaultdict(list)
    for task in tasks:
        by_day[task.due_date].append(task)
    open_projects = visible.filter(end_date__range=(first, last)).exclude(
        status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED]
    )
    for p in open_projects:
        closing[p.end_date].append(p)

    weeks = [
        [
            {
                "date": d,
                "in_month": d.month == month,
                "is_today": d == today,
                "tasks": by_day.get(d, []),
                "projects": closing.get(d, []),
            }
            for d in week
        ]
        for week in grid
    ]
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    return {
        "year": year, "month": month,
        "title": f"{MESES[month - 1].capitalize()} {year}",
        "weeks": weeks,
        "prev_y": prev_y, "prev_m": prev_m, "next_y": next_y, "next_m": next_m,
        "today_y": today.year, "today_m": today.month,
    }


# ---------------- Gantt ----------------

ROW_H = 36
BAR_H = 22
ZOOMS = {"day": (32, 1), "week": (14, 7), "month": (5, 0)}      # (píxeles por día, días entre marcas)
STATUS_COLORS = {"todo": "#94a3b8", "in_progress": "#3b82f6", "review": "#f59e0b", "done": "#22c55e"}


def build_gantt(project, zoom="week"):
    """Posiciones (en píxeles) de barras, marcas y flechas de dependencia de un proyecto."""
    if zoom not in ZOOMS:
        zoom = "week"
    ppd, step = ZOOMS[zoom]
    today = timezone.localdate()

    alive_sub = Q(subtasks__deleted_at__isnull=True)
    tasks = (
        Task.objects.alive()
        .filter(project=project, parent__isnull=True)
        .annotate(
            sub_total=Count("subtasks", filter=alive_sub, distinct=True),
            sub_done=Count("subtasks", filter=alive_sub & Q(subtasks__status=Task.Status.DONE), distinct=True),
        )
        .order_by("id")
    )

    dated, undated = [], []
    for task in tasks:
        if task.start_date or task.due_date:
            a = task.start_date or task.due_date
            b = task.due_date or task.start_date
            dated.append((min(a, b), max(a, b), task))
        else:
            undated.append(task)
    dated.sort(key=lambda item: (item[0], item[2].pk))

    if not dated:
        return {"zoom": zoom, "rows": [], "undated": undated, "deps": []}

    first = min(s for s, _, _ in dated)
    last = max(e for _, e, _ in dated)
    if first - timedelta(days=30) <= today <= last + timedelta(days=30):
        first, last = min(first, today), max(last, today)       # que "hoy" quede dentro del rango

    start = first - timedelta(days=3)
    start -= timedelta(days=start.weekday())                    # alinear al lunes
    end = last + timedelta(days=3)
    end += timedelta(days=6 - end.weekday())                    # alinear al domingo
    total_width = ((end - start).days + 1) * ppd

    # ---- Filas / barras ----
    rows, by_pk = [], {}
    for i, (s, e, task) in enumerate(dated):
        left, width = (s - start).days * ppd, ((e - s).days + 1) * ppd
        if task.status == Task.Status.DONE:
            progress = 100
        else:
            progress = task.sub_done * 100 // task.sub_total if task.sub_total else 0
        row = {
            "task": task, "index": i, "start": s, "end": e,
            "top": i * ROW_H + (ROW_H - BAR_H) // 2,
            "left": left, "width": width,
            "color": STATUS_COLORS[task.status], "progress": progress,
            "overdue": task.is_overdue,
            "label": task.title if width >= 80 else "",
            "range_text": f"{s:%d/%m/%Y}" if s == e else f"{s:%d/%m/%Y} → {e:%d/%m/%Y}",
        }
        rows.append(row)
        by_pk[task.pk] = row

    # ---- Flechas de dependencia (bloqueadora → dependiente) ----
    deps = []
    through = Task.blocked_by.through
    ids = list(by_pk)
    for link in through.objects.filter(from_task_id__in=ids, to_task_id__in=ids):
        blocker, blocked = by_pk[link.to_task_id], by_pk[link.from_task_id]
        x1 = blocker["left"] + blocker["width"]
        y1 = blocker["index"] * ROW_H + ROW_H // 2
        x2 = blocked["left"]
        y2 = blocked["index"] * ROW_H + ROW_H // 2
        if x2 - x1 >= 10:
            d = f"M{x1} {y1} H{x1 + 6} V{y2} H{x2 - 2}"
        else:                                                   # sin espacio: rodea por entre las filas
            y_mid = y1 + ROW_H // 2 if y2 > y1 else y1 - ROW_H // 2
            d = f"M{x1} {y1} H{x1 + 6} V{y_mid} H{x2 - 8} V{y2} H{x2 - 2}"
        deps.append({"d": d, "conflict": blocked["start"] <= blocker["end"]})

    # ---- Encabezado: meses y marcas ----
    months, cursor = [], start
    while cursor <= end:
        month_end = date(cursor.year, cursor.month, calendar.monthrange(cursor.year, cursor.month)[1])
        seg_end = min(month_end, end)
        months.append({
            "label": f"{MESES[cursor.month - 1]} {cursor.year}",
            "left": (cursor - start).days * ppd,
            "width": ((seg_end - cursor).days + 1) * ppd,
        })
        cursor = seg_end + timedelta(days=1)

    ticks = []
    if step:
        day = start
        while day <= end:
            ticks.append({
                "label": str(day.day) if step == 1 else f"{day:%d/%m}",
                "left": (day - start).days * ppd,
                "width": step * ppd,
                "weekend": step == 1 and day.weekday() >= 5,
            })
            day += timedelta(days=step)

    return {
        "zoom": zoom, "ppd": ppd, "start": start, "end": end,
        "rows": rows, "undated": undated, "deps": deps,
        "months": months, "ticks": ticks,
        "total_width": total_width,
        "body_height": len(rows) * ROW_H,
        "row_h": ROW_H, "row_line": ROW_H - 1,
        "grid_size": (step or 7) * ppd,
        "today_left": (today - start).days * ppd + ppd // 2 if start <= today <= end else None,
    }