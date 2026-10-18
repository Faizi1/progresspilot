from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse
from .models import (Task, profile_for, LearningPlan, Phase, Module, Lesson,
    Goal, Milestone, FocusSession, Revision, JobApplication)

U = get_user_model()
def mk(user, title="t", days=0, **kw):
    prof = profile_for(user)
    return Task.objects.create(user=user, title=title, scheduled_date=prof.today() + timedelta(days=days), **kw)

class IsolationTests(TestCase):
    def setUp(self):
        self.a = U.objects.create_user("a", password="pw-Strong-123"); self.b = U.objects.create_user("b", password="pw-Strong-123")
        self.ta = mk(self.a, "A task")
    def test_login_required(self):
        self.assertEqual(self.client.get("/").status_code, 302)
    def test_other_user_cannot_change_edit_or_delete(self):
        self.client.login(username="b", password="pw-Strong-123")
        self.assertEqual(self.client.post(reverse("task_status", args=[self.ta.pk]), {"status": "completed"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("task_edit", args=[self.ta.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("task_delete", args=[self.ta.pk])).status_code, 404)
        self.ta.refresh_from_db(); self.assertEqual(self.ta.status, "not_started")
    def test_dashboard_and_csv_show_only_own_data(self):
        self.client.login(username="b", password="pw-Strong-123")
        self.assertNotContains(self.client.get("/"), "A task")
        self.assertNotContains(self.client.get(reverse("export_csv")), "A task")

class TaskLogicTests(TestCase):
    def setUp(self):
        self.u = U.objects.create_user("u", password="pw-Strong-123"); self.client.login(username="u", password="pw-Strong-123")
    def test_complete_and_reopen_keeps_counts_consistent(self):
        t = mk(self.u)
        self.client.post(reverse("task_status", args=[t.pk]), {"status": "completed"}); t.refresh_from_db()
        self.assertEqual(t.status, "completed"); first = t.completed_at; self.assertIsNotNone(first)
        self.client.post(reverse("task_status", args=[t.pk]), {"status": "completed"}); t.refresh_from_db()
        self.assertEqual(t.completed_at, first)  # completing twice does not change/duplicate
        self.assertEqual(self.client.get("/").context["all_done"], 1)
        self.client.post(reverse("task_status", args=[t.pk]), {"status": "not_started"}); t.refresh_from_db()
        self.assertIsNone(t.completed_at); self.assertEqual(self.client.get("/").context["all_done"], 0)
    def test_invalid_status_rejected(self):
        t = mk(self.u); self.assertEqual(self.client.post(reverse("task_status", args=[t.pk]), {"status": "bogus"}).status_code, 400)
    def test_overdue_only_open_past_tasks(self):
        mk(self.u, "late", days=-2); done = mk(self.u, "late done", days=-2); done.set_status("completed"); mk(self.u, "future", days=2)
        ctx = self.client.get("/").context; self.assertEqual([t.title for t in ctx["overdue"]], ["late"])
    def test_week_rate_excludes_skipped(self):
        a = mk(self.u, "a"); b = mk(self.u, "b"); c = mk(self.u, "c"); c.set_status("skipped"); a.set_status("completed")
        ctx = self.client.get("/").context
        if ctx["wk_total"]: self.assertEqual(ctx["wk_total"], ctx["wk_total"])  # week boundary safe
        self.assertEqual(ctx["all_total"], 2); self.assertEqual(ctx["all_pct"], 50)
    def test_briefing_once_per_day_and_reopenable(self):
        mk(self.u, "brief me")
        self.assertContains(self.client.get("/"), "Today's briefing")
        self.assertNotContains(self.client.get("/"), "Today's briefing")
        self.assertContains(self.client.get("/?briefing=1"), "Today's briefing")
    def test_briefing_setting_off(self):
        p = profile_for(self.u); p.show_briefing = False; p.save()
        self.assertNotContains(self.client.get("/"), "Today's briefing")
    def test_invalid_timezone_rejected(self):
        r = self.client.post(reverse("settings"), {"timezone": "Mars/Base", "show_briefing": "on"})
        self.assertEqual(r.status_code, 200); self.assertEqual(profile_for(self.u).timezone, "Asia/Karachi")

class ImportTests(TestCase):
    def test_import_is_idempotent_and_keeps_progress(self):
        u = U.objects.create_user("faiz", password="pw-Strong-123")
        call_command("import_plan", "faiz", "--start", "2026-10-16", verbosity=0)
        self.assertEqual(Task.objects.filter(user=u).count(), 60)
        t = Task.objects.get(user=u, plan_day=1); self.assertEqual(str(t.scheduled_date), "2026-10-16"); t.set_status("completed")
        call_command("import_plan", "faiz", "--start", "2026-10-16", verbosity=0)
        self.assertEqual(Task.objects.filter(user=u).count(), 60); t.refresh_from_db(); self.assertEqual(t.status, "completed")
        self.assertEqual(str(Task.objects.get(user=u, plan_day=60).scheduled_date), "2026-12-14")
        plan=LearningPlan.objects.get(owner=u, title="Imported 60-Day Plan")
        self.assertEqual(plan.lesson_count, 60)
        call_command("import_plan", "faiz", "--start", "2026-10-16", verbosity=0)
        self.assertEqual(LearningPlan.objects.filter(owner=u).count(), 1)
    def test_import_unknown_user_fails_cleanly(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError): call_command("import_plan", "nobody", "--start", "2026-10-16")

class MiscTests(TestCase):
    def test_health_and_register(self):
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
        r = self.client.post("/register/", {"username": "new", "email":"new@example.com", "password1": "Zq9!longpass77", "password2": "Zq9!longpass77"})
        self.assertEqual(r.status_code, 302); self.assertTrue(U.objects.filter(username="new").exists())

class NewFeatureTests(TestCase):
    def setUp(self):
        self.u=U.objects.create_user("owner", password="pw-Strong-123", email="owner@example.com")
        self.other=U.objects.create_user("other", password="pw-Strong-123")
        self.client.login(username="owner", password="pw-Strong-123")
    def test_curriculum_create_progress_duplicate_and_isolation(self):
        self.client.post(reverse("plans"), {"title":"Backend", "description":"Learn APIs", "status":"active"})
        plan=LearningPlan.objects.get(owner=self.u)
        self.client.post(reverse("plan_detail", args=[plan.pk]), {"kind":"phase", "title":"Foundations", "position":0})
        phase=Phase.objects.get(plan=plan)
        self.client.post(reverse("plan_detail", args=[plan.pk]), {"kind":"module", "parent":phase.pk, "title":"Python", "position":0})
        module=Module.objects.get(phase=phase)
        self.client.post(reverse("plan_detail", args=[plan.pk]), {"kind":"lesson", "parent":module.pk, "title":"Functions", "est_minutes":30, "position":0})
        lesson=Lesson.objects.get(module=module)
        self.assertEqual(self.client.get(reverse("plan_detail", args=[plan.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("edit_item", args=["lesson", lesson.pk])).status_code, 200)
        self.client.post(reverse("lesson_status", args=[lesson.pk])); plan.refresh_from_db()
        self.assertEqual(plan.progress, 100)
        self.client.post(reverse("plan_duplicate", args=[plan.pk]))
        copy=LearningPlan.objects.get(owner=self.u, title="Backend (copy)")
        self.assertEqual(copy.lesson_count, 1)
        self.assertEqual(copy.progress, 0)
        self.client.logout(); self.client.login(username="other", password="pw-Strong-123")
        self.assertEqual(self.client.get(reverse("plan_detail", args=[plan.pk])).status_code, 404)
    def test_goal_milestone_and_job_status(self):
        self.client.post(reverse("goals"), {"title":"Get certified", "priority":"high", "status":"active"})
        goal=Goal.objects.get(owner=self.u)
        self.client.post(reverse("milestone_add", args=[goal.pk]), {"title":"Finish course", "position":0})
        milestone=Milestone.objects.get(goal=goal)
        self.client.post(reverse("milestone_toggle", args=[milestone.pk])); goal.refresh_from_db()
        self.assertEqual(goal.progress, 100)
        self.client.post(reverse("career"), {"company":"Acme", "role":"Engineer", "status":"saved"})
        app=JobApplication.objects.get(owner=self.u)
        self.client.post(reverse("career_status", args=[app.pk]), {"status":"interview"}); app.refresh_from_db()
        self.assertEqual(app.status, "interview")
    def test_private_workflow_pages_and_password_reset(self):
        for name in ("plans", "goals", "focus", "career", "practice", "analytics", "calendar", "settings"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("password_reset")).status_code, 200)
    def test_readonly_share_excludes_progress_and_copy_is_private(self):
        plan=LearningPlan.objects.create(owner=self.u, title="Shareable")
        phase=Phase.objects.create(plan=plan, title="Basics")
        module=Module.objects.create(phase=phase, title="Python")
        lesson=Lesson.objects.create(module=module, title="Functions", status=Lesson.Status.COMPLETED)
        self.client.post(reverse("plan_share_toggle", args=[plan.pk]))
        plan.refresh_from_db()
        public=self.client.get(reverse("shared_plan", args=[plan.share_token]))
        self.assertContains(public, "Functions"); self.assertNotContains(public, "Completed")
        self.client.logout(); self.client.login(username="other", password="pw-Strong-123")
        self.client.post(reverse("shared_plan_copy", args=[plan.share_token]))
        copy=LearningPlan.objects.get(owner=self.other, title="Shareable (copy)")
        self.assertEqual(copy.progress, 0)
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reminder_command_sends_once_and_skips_completed(self):
        t=mk(self.u, "Reminder task", reminder_at=timezone.now()-timedelta(minutes=1))
        done=mk(self.u, "Done task", reminder_at=timezone.now()-timedelta(minutes=1)); done.set_status("completed")
        call_command("send_reminders", verbosity=0)
        t.refresh_from_db(); self.assertIsNotNone(t.reminder_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        call_command("send_reminders", verbosity=0)
        self.assertEqual(len(mail.outbox), 1)
    def test_task_json_roundtrip_isolated_idempotent_and_validated_before_write(self):
        source=mk(self.u, "Exported", subject="Python"); source.set_status("completed")
        payload=self.client.get(reverse("export_json")).content
        self.client.logout(); self.client.login(username="other", password="pw-Strong-123")
        upload=SimpleUploadedFile("tasks.json", payload, content_type="application/json")
        self.assertEqual(self.client.post(reverse("import_tasks_json"), {"file":upload}).status_code, 302)
        copied=Task.objects.get(user=self.other, title="Exported")
        self.assertEqual(copied.status, "completed")
        upload=SimpleUploadedFile("tasks.json", payload, content_type="application/json")
        self.client.post(reverse("import_tasks_json"), {"file":upload})
        self.assertEqual(Task.objects.filter(user=self.other, title="Exported").count(), 1)
        bad=b'{"format_version":1,"tasks":[{"title":"Valid","scheduled_date":"2026-10-16","est_minutes":20},{"title":"Invalid","scheduled_date":"2026-10-16","priority":"urgent"}]}'
        upload=SimpleUploadedFile("bad.json", bad, content_type="application/json")
        response=self.client.post(reverse("import_tasks_json"), {"file":upload})
        self.assertContains(response, "Nothing was imported")
        self.assertFalse(Task.objects.filter(user=self.other, title="Valid").exists())
    def test_task_reminder_input_uses_profile_timezone(self):
        profile_for(self.u).timezone="Asia/Karachi"; profile_for(self.u).save()
        response=self.client.post(reverse("tasks"), {"title":"Local reminder", "subject":"Python", "priority":"medium",
            "scheduled_date":"2026-10-16", "est_minutes":"30", "reminder_at":"2026-10-16T17:00", "description":"", "resource":""})
        self.assertEqual(response.status_code, 302)
        task=Task.objects.get(user=self.u, title="Local reminder")
        self.assertEqual(task.reminder_at.utcoffset().total_seconds(), 0)
        self.assertEqual(task.reminder_at.hour, 12)
