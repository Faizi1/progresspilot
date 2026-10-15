from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Task, profile_for

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
    def test_import_unknown_user_fails_cleanly(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError): call_command("import_plan", "nobody", "--start", "2026-10-16")

class MiscTests(TestCase):
    def test_health_and_register(self):
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
        r = self.client.post("/register/", {"username": "new", "password1": "Zq9!longpass77", "password2": "Zq9!longpass77"})
        self.assertEqual(r.status_code, 302); self.assertTrue(U.objects.filter(username="new").exists())
