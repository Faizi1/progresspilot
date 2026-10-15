import csv
from datetime import timedelta
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import RegisterForm, TaskForm, SettingsForm
from .models import Task, profile_for

def health(request):
    return JsonResponse({"status": "ok"})

def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(); profile_for(user); login(request, user)
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})

OPEN = [Task.Status.NOT_STARTED, Task.Status.IN_PROGRESS, Task.Status.BLOCKED]

@login_required
def dashboard(request):
    prof = profile_for(request.user); today = prof.today()
    qs = Task.objects.filter(user=request.user)
    todays = qs.filter(scheduled_date=today)
    overdue = qs.filter(scheduled_date__lt=today, status__in=OPEN)
    week_start = today - timedelta(days=today.weekday()); week_end = week_start + timedelta(days=6)
    wk = qs.filter(scheduled_date__range=(week_start, week_end)).exclude(status=Task.Status.SKIPPED)
    wk_total, wk_done = wk.count(), wk.filter(status=Task.Status.COMPLETED).count()
    all_tot = qs.exclude(status=Task.Status.SKIPPED).count(); all_done = qs.filter(status=Task.Status.COMPLETED).count()
    last7 = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        n = sum(1 for t in qs.filter(completed_at__isnull=False, completed_at__date__range=(d - timedelta(days=1), d + timedelta(days=1))) if t.completed_at.astimezone(prof.tz()).date() == d)
        last7.append({"day": d, "n": n})
    mx = max([x["n"] for x in last7] + [1])
    for x in last7: x["pct"] = int(100 * x["n"] / mx)
    subjects = qs.exclude(subject="").values("subject").annotate(total=Count("id"), done=Count("id", filter=Q(status=Task.Status.COMPLETED))).order_by("subject")
    for s in subjects: s["pct"] = int(100 * s["done"] / s["total"]) if s["total"] else 0
    show = False
    if request.GET.get("briefing") == "1": show = True
    elif prof.show_briefing and prof.last_briefing_date != today:
        show = True; prof.last_briefing_date = today; prof.save(update_fields=["last_briefing_date"])
    ctx = {"today": today, "todays": todays, "overdue": overdue, "n_today": todays.count(),
           "n_done_today": todays.filter(status=Task.Status.COMPLETED).count(),
           "n_remaining": todays.exclude(status__in=[Task.Status.COMPLETED, Task.Status.SKIPPED]).count(),
           "wk_total": wk_total, "wk_done": wk_done, "wk_pct": int(100 * wk_done / wk_total) if wk_total else None,
           "all_total": all_tot, "all_done": all_done, "all_pct": int(100 * all_done / all_tot) if all_tot else None,
           "last7": last7, "subjects": subjects, "show_briefing": show,
           "high_today": todays.filter(priority="high").exclude(status=Task.Status.COMPLETED),
           "upcoming": qs.filter(scheduled_date__gt=today, scheduled_date__lte=today + timedelta(days=3), status__in=OPEN)}
    return render(request, "dashboard.html", ctx)

@login_required
def task_list(request):
    prof = profile_for(request.user); today = prof.today()
    qs = Task.objects.filter(user=request.user)
    when = request.GET.get("when", "week")
    if when == "today": qs = qs.filter(scheduled_date=today)
    elif when == "overdue": qs = qs.filter(scheduled_date__lt=today, status__in=OPEN)
    elif when == "week":
        ws = today - timedelta(days=today.weekday()); qs = qs.filter(scheduled_date__range=(ws, ws + timedelta(days=6)))
    for key in ("status", "priority", "subject"):
        v = request.GET.get(key)
        if v: qs = qs.filter(**{key: v})
    form = TaskForm(request.POST or None, initial={"scheduled_date": today})
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False); t.user = request.user; t.save()
        return redirect("tasks")
    from django.core.paginator import Paginator
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "tasks.html", {"page": page, "form": form, "when": when, "today": today,
        "statuses": Task.Status.choices, "priorities": Task.Priority.choices})

@login_required
@require_POST
def set_status(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)  # 404 for other users' tasks
    status = request.POST.get("status")
    if status not in Task.Status.values: return HttpResponse("Invalid status", status=400)
    task.set_status(status)
    nxt = request.POST.get("next") or "dashboard"
    return redirect(nxt if nxt in ("dashboard", "tasks") else "dashboard")

@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    form = TaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save(); return redirect("tasks")
    return render(request, "task_edit.html", {"form": form, "task": task})

@login_required
@require_POST
def task_delete(request, pk):
    get_object_or_404(Task, pk=pk, user=request.user).delete()
    return redirect("tasks")

@login_required
def settings_view(request):
    form = SettingsForm(request.POST or None, instance=profile_for(request.user))
    if request.method == "POST" and form.is_valid():
        form.save(); return redirect("dashboard")
    return render(request, "settings.html", {"form": form})

@login_required
def export_csv(request):
    resp = HttpResponse(content_type="text/csv"); resp["Content-Disposition"] = 'attachment; filename="tasks.csv"'
    w = csv.writer(resp); w.writerow(["date", "subject", "title", "priority", "status", "est_minutes", "completed_at"])
    for t in Task.objects.filter(user=request.user):
        w.writerow([t.scheduled_date, t.subject, t.title, t.priority, t.status, t.est_minutes, t.completed_at or ""])
    return resp
