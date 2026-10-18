import csv
import json
from datetime import datetime
from datetime import timedelta, datetime, time
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
import uuid
from django.views.decorators.http import require_POST
from django.utils import timezone
from .forms import (RegisterForm, TaskForm, SettingsForm, LearningPlanForm, PhaseForm,
    ModuleForm, LessonForm, GoalForm, MilestoneForm, FocusSessionForm, RevisionForm, JobApplicationForm, PracticeEntryForm, AccountEmailForm, TaskImportForm)
from .models import (Task, profile_for, LearningPlan, Phase, Module, Lesson, Goal,
    Milestone, FocusSession, Revision, JobApplication, PracticeEntry)

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
    day_start=timezone.make_aware(datetime.combine(today, time.min), prof.tz())
    day_end=timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), prof.tz())
    focus_today=sum(x.minutes for x in FocusSession.objects.filter(owner=request.user, started_at__gte=day_start, started_at__lt=day_end))
    show = False
    if request.GET.get("briefing") == "1": show = True
    elif prof.show_briefing and prof.last_briefing_date != today:
        show = True; prof.last_briefing_date = today; prof.save(update_fields=["last_briefing_date"])
    ctx = {"today": today, "todays": todays, "overdue": overdue, "profile":prof, "focus_today":focus_today, "n_today": todays.count(),
           "n_done_today": todays.filter(status=Task.Status.COMPLETED).count(),
           "n_remaining": todays.exclude(status__in=[Task.Status.COMPLETED, Task.Status.SKIPPED]).count(),
           "wk_total": wk_total, "wk_done": wk_done, "wk_pct": int(100 * wk_done / wk_total) if wk_total else None,
           "all_total": all_tot, "all_done": all_done, "all_pct": int(100 * all_done / all_tot) if all_tot else None,
           "last7": last7, "subjects": subjects, "show_briefing": show,
           "high_today": todays.filter(priority="high").exclude(status=Task.Status.COMPLETED),
           "upcoming": qs.filter(scheduled_date__gt=today, scheduled_date__lte=today + timedelta(days=3), status__in=OPEN),
           "active_plans": LearningPlan.objects.filter(owner=request.user, status=LearningPlan.Status.ACTIVE)[:3],
           "active_goals": Goal.objects.filter(owner=request.user, status=Goal.Status.ACTIVE).order_by("target_date")[:3],
           "due_revisions": Revision.objects.filter(task__user=request.user, completed=False, due_date__lte=today + timedelta(days=3)).select_related("task").order_by("due_date")[:5]}
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
        "statuses": Task.Status.choices, "priorities": Task.Priority.choices,
        "subjects": Task.objects.filter(user=request.user).exclude(subject="").values_list("subject", flat=True).distinct().order_by("subject"),
        "imported": request.GET.get("imported")})

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
    email_form = AccountEmailForm(request.POST or None, instance=request.user, prefix="account")
    if request.method == "POST":
        if request.POST.get("section") == "account":
            if email_form.is_valid(): email_form.save(); return redirect("settings")
        elif form.is_valid():
            form.save(); return redirect("dashboard")
    return render(request, "settings.html", {"form": form, "email_form":email_form})

@login_required
def export_csv(request):
    resp = HttpResponse(content_type="text/csv"); resp["Content-Disposition"] = 'attachment; filename="tasks.csv"'
    w = csv.writer(resp); w.writerow(["date", "subject", "title", "priority", "status", "est_minutes", "completed_at"])
    for t in Task.objects.filter(user=request.user):
        w.writerow([t.scheduled_date, t.subject, t.title, t.priority, t.status, t.est_minutes, t.completed_at or ""])
    return resp

@login_required
def export_json(request):
    records=[]
    for t in Task.objects.filter(user=request.user):
        records.append({"title":t.title,"description":t.description,"subject":t.subject,"phase":t.phase,
            "resource":t.resource,"priority":t.priority,"status":t.status,"scheduled_date":t.scheduled_date.isoformat(),
            "est_minutes":t.est_minutes,"reminder_at":t.reminder_at.isoformat() if t.reminder_at else "",
            "completed_at":t.completed_at.isoformat() if t.completed_at else None})
    resp=HttpResponse(json.dumps({"format_version":1,"tasks":records}, ensure_ascii=False, indent=2), content_type="application/json")
    resp["Content-Disposition"]='attachment; filename="progresspilot-tasks.json"'
    return resp

@login_required
def import_tasks_json(request):
    form=TaskImportForm(request.POST or None, request.FILES or None); errors=[]; imported=None
    if request.method == "POST" and form.is_valid():
        try:
            data=json.loads(form.cleaned_data["file"].read().decode("utf-8-sig"))
            rows=data.get("tasks") if isinstance(data,dict) and data.get("format_version")==1 else None
            if not isinstance(rows,list): errors.append("Expected a ProgressPilot JSON export (format_version 1 with a tasks list).")
            elif len(rows)>5000: errors.append("A single import is limited to 5,000 tasks.")
            else:
                valid=[]; seen=set()
                for index,row in enumerate(rows, start=1):
                    if not isinstance(row,dict): errors.append(f"Row {index}: expected an object."); continue
                    form_data={k:row.get(k, "") for k in ("title","description","subject","phase","resource","priority","scheduled_date","est_minutes","reminder_at")}
                    item_form=TaskForm(form_data)
                    if not item_form.is_valid():
                        errors.append(f"Row {index}: " + "; ".join(f"{key}: {', '.join(msgs)}" for key,msgs in item_form.errors.items())); continue
                    status=row.get("status", Task.Status.NOT_STARTED)
                    if status not in Task.Status.values: errors.append(f"Row {index}: invalid status."); continue
                    cleaned=item_form.cleaned_data; key=(cleaned["title"],cleaned["scheduled_date"],cleaned.get("subject",""))
                    if key in seen: errors.append(f"Row {index}: duplicate title/date/subject in this file."); continue
                    completed_at=None
                    if status == Task.Status.COMPLETED and row.get("completed_at"):
                        try: completed_at=datetime.fromisoformat(row["completed_at"])
                        except (TypeError,ValueError): errors.append(f"Row {index}: invalid completion timestamp."); continue
                    seen.add(key); valid.append((item_form.cleaned_data,status,completed_at,key))
                if not errors:
                    from django.db import transaction
                    existing=set(Task.objects.filter(user=request.user).values_list("title","scheduled_date","subject"))
                    created=0
                    with transaction.atomic():
                        for fields,status,completed_at,key in valid:
                            if key in existing: continue
                            task=Task.objects.create(user=request.user, **fields)
                            if status != Task.Status.NOT_STARTED: task.set_status(status)
                            if status == Task.Status.COMPLETED and completed_at:
                                task.completed_at=completed_at
                                if timezone.is_naive(task.completed_at): task.completed_at=timezone.make_aware(task.completed_at)
                                task.save(update_fields=["completed_at"])
                            existing.add(key); created += 1
                    return redirect(f"/tasks/?imported={created}")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            errors.append(f"Could not read JSON file: {exc}")
    return render(request, "import_tasks.html", {"form":form,"errors":errors,"imported":imported})


@login_required
def plans(request):
    form = LearningPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False); plan.owner = request.user; plan.save()
        return redirect("plan_detail", pk=plan.pk)
    return render(request, "plans.html", {"plans": LearningPlan.objects.filter(owner=request.user), "form": form})

@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(LearningPlan.objects.prefetch_related("phases__modules__lessons"), pk=pk, owner=request.user)
    if request.method == "POST":
        kind, parent_id = request.POST.get("kind"), request.POST.get("parent")
        if kind == "plan":
            form=LearningPlanForm(request.POST, instance=plan)
            if form.is_valid(): form.save(); return redirect("plan_detail", pk=pk)
        elif kind == "phase":
            form = PhaseForm(request.POST)
            if form.is_valid():
                phase=form.save(commit=False); phase.plan=plan; phase.save(); return redirect("plan_detail", pk=pk)
        elif kind == "module":
            phase=get_object_or_404(Phase, pk=parent_id, plan=plan); form=ModuleForm(request.POST)
            if form.is_valid():
                obj=form.save(commit=False); obj.phase=phase; obj.save(); return redirect("plan_detail", pk=pk)
        elif kind == "lesson":
            module=get_object_or_404(Module, pk=parent_id, phase__plan=plan); form=LessonForm(request.POST)
            if form.is_valid():
                obj=form.save(commit=False); obj.module=module; obj.save(); return redirect("plan_detail", pk=pk)
    phases = plan.phases.all()
    return render(request, "plan_detail.html", {"plan": plan, "phases": phases, "plan_form": LearningPlanForm(instance=plan), "phase_form": PhaseForm(),
        "module_form": ModuleForm(), "lesson_form": LessonForm()})

@login_required
@require_POST
def plan_duplicate(request, pk):
    source=get_object_or_404(LearningPlan, pk=pk, owner=request.user)
    copy=source.duplicate_for(request.user)
    return redirect("plan_detail", pk=copy.pk)

@login_required
@require_POST
def plan_share_toggle(request, pk):
    plan=get_object_or_404(LearningPlan, pk=pk, owner=request.user)
    plan.share_token=None if plan.share_token else uuid.uuid4()
    plan.save(update_fields=["share_token"])
    return redirect("plan_detail", pk=pk)

def shared_plan(request, token):
    plan=get_object_or_404(LearningPlan.objects.prefetch_related("phases__modules__lessons"), share_token=token)
    return render(request, "shared_plan.html", {"plan":plan, "phases":plan.phases.all()})

@login_required
@require_POST
def shared_plan_copy(request, token):
    source=get_object_or_404(LearningPlan, share_token=token)
    copy=source.duplicate_for(request.user)
    return redirect("plan_detail", pk=copy.pk)

@login_required
@require_POST
def lesson_status(request, pk):
    lesson=get_object_or_404(Lesson, pk=pk, module__phase__plan__owner=request.user)
    lesson.status = Lesson.Status.COMPLETED if lesson.status != Lesson.Status.COMPLETED else Lesson.Status.NOT_STARTED
    lesson.completed_at = timezone.now() if lesson.status == Lesson.Status.COMPLETED else None
    lesson.save(update_fields=["status", "completed_at"])
    return redirect("plan_detail", pk=lesson.module.phase.plan_id)

@login_required
def goals(request):
    form=GoalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj=form.save(commit=False); obj.owner=request.user; obj.save(); return redirect("goals")
    return render(request, "goals.html", {"goals": Goal.objects.filter(owner=request.user).prefetch_related("milestones"), "form": form, "milestone_form": MilestoneForm()})

@login_required
@require_POST
def milestone_add(request, goal_id):
    goal=get_object_or_404(Goal, pk=goal_id, owner=request.user); form=MilestoneForm(request.POST)
    if form.is_valid():
        item=form.save(commit=False); item.goal=goal; item.save()
    return redirect("goals")

@login_required
@require_POST
def milestone_toggle(request, pk):
    item=get_object_or_404(Milestone, pk=pk, goal__owner=request.user)
    item.completed=not item.completed; item.completed_at=timezone.now() if item.completed else None
    item.save(update_fields=["completed", "completed_at"]); return redirect("goals")

@login_required
def focus(request):
    form=FocusSessionForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        session=form.save(commit=False); session.owner=request.user; session.save(); return redirect("focus")
    sessions=FocusSession.objects.filter(owner=request.user).select_related("task")[:30]
    total=sum(s.minutes for s in sessions)
    due_revisions=Revision.objects.filter(task__user=request.user, completed=False).select_related("task").order_by("due_date")
    return render(request, "focus.html", {"form": form, "sessions": sessions, "total_minutes": total, "revisions": due_revisions})

@login_required
@require_POST
def revision_add(request, task_id):
    task=get_object_or_404(Task, pk=task_id, user=request.user); form=RevisionForm(request.POST)
    if form.is_valid():
        revision=form.save(commit=False); revision.task=task; revision.save()
    return redirect("focus")

@login_required
@require_POST
def revision_toggle(request, pk):
    revision=get_object_or_404(Revision, pk=pk, task__user=request.user)
    revision.completed=not revision.completed; revision.completed_at=timezone.now() if revision.completed else None
    revision.save(update_fields=["completed", "completed_at"]); return redirect("focus")

@login_required
def career(request):
    form=JobApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item=form.save(commit=False); item.owner=request.user; item.save(); return redirect("career")
    return render(request, "career.html", {"applications": JobApplication.objects.filter(owner=request.user), "form": form, "job_statuses": JobApplication.Status.choices})

@login_required
@require_POST
def career_status(request, pk):
    item=get_object_or_404(JobApplication, pk=pk, owner=request.user)
    if request.POST.get("status") in JobApplication.Status.values:
        item.status=request.POST["status"]; item.save(update_fields=["status"])
    return redirect("career")

@login_required
def practice(request):
    form=PracticeEntryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        entry=form.save(commit=False); entry.owner=request.user; entry.save(); return redirect("practice")
    kind=request.GET.get("kind")
    entries=PracticeEntry.objects.filter(owner=request.user)
    if kind in PracticeEntry.Kind.values: entries=entries.filter(kind=kind)
    return render(request, "practice.html", {"form":form, "entries":entries[:100], "kinds":PracticeEntry.Kind.choices, "selected_kind":kind})

@login_required
def analytics(request):
    tasks=Task.objects.filter(user=request.user)
    completed=tasks.filter(status=Task.Status.COMPLETED)
    sessions=list(FocusSession.objects.filter(owner=request.user)[:500])
    apps=JobApplication.objects.filter(owner=request.user)
    return render(request, "analytics.html", {"total_tasks":tasks.count(), "completed_tasks":completed.count(),
        "completion_pct":round(completed.count()*100/tasks.exclude(status=Task.Status.SKIPPED).count()) if tasks.exclude(status=Task.Status.SKIPPED).exists() else 0,
        "focus_minutes":sum(x.minutes for x in sessions), "application_count":apps.count(),
        "apps_by_status":apps.values("status").annotate(total=Count("id")).order_by("status"),
        "subject_stats":tasks.exclude(subject="").values("subject").annotate(total=Count("id"), done=Count("id", filter=Q(status=Task.Status.COMPLETED))).order_by("subject")})

@login_required
def calendar(request):
    today=profile_for(request.user).today()
    try: offset=max(-52, min(52, int(request.GET.get("week", "0"))))
    except (TypeError, ValueError): offset=0
    start=today-timedelta(days=today.weekday())+timedelta(weeks=offset)
    days=[]
    qs=Task.objects.filter(user=request.user, scheduled_date__range=(start, start+timedelta(days=6)))
    for i in range(7):
        day=start+timedelta(days=i)
        days.append({"date":day, "tasks":qs.filter(scheduled_date=day)})
    return render(request, "calendar.html", {"days":days, "week":offset, "prev":offset-1, "next":offset+1})

@login_required
def edit_item(request, kind, pk):
    config={
        "phase":(Phase, PhaseForm, {"plan__owner":request.user}),
        "module":(Module, ModuleForm, {"phase__plan__owner":request.user}),
        "lesson":(Lesson, LessonForm, {"module__phase__plan__owner":request.user}),
        "goal":(Goal, GoalForm, {"owner":request.user}),
        "milestone":(Milestone, MilestoneForm, {"goal__owner":request.user}),
        "application":(JobApplication, JobApplicationForm, {"owner":request.user}),
    }
    if kind not in config: return HttpResponse("Not found", status=404)
    model, form_type, scope=config[kind]
    obj=get_object_or_404(model, pk=pk, **scope)
    if kind == "phase": back=redirect("plan_detail", pk=obj.plan_id)
    elif kind == "module": back=redirect("plan_detail", pk=obj.phase.plan_id)
    elif kind == "lesson": back=redirect("plan_detail", pk=obj.module.phase.plan_id)
    elif kind == "goal": back=redirect("goals")
    elif kind == "milestone": back=redirect("goals")
    else: back=redirect("career")
    if request.method == "POST":
        if request.POST.get("action") == "delete": obj.delete(); return back
        form=form_type(request.POST, instance=obj)
        if form.is_valid(): form.save(); return back
    else: form=form_type(instance=obj)
    return render(request, "edit_item.html", {"form":form, "kind":kind, "obj":obj})
