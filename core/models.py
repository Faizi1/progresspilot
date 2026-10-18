from datetime import date
from zoneinfo import ZoneInfo
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Karachi")
    daily_target_minutes = models.PositiveIntegerField(default=60)
    preferred_study_days = models.CharField(max_length=80, blank=True, help_text="Optional, e.g. Mon,Tue,Wed,Thu,Fri")
    weekly_review_day = models.CharField(max_length=3, default="Sun", choices=[(d,d) for d in ("Mon","Tue","Wed","Thu","Fri","Sat","Sun")])
    show_briefing = models.BooleanField(default=True)
    notifications_enabled = models.BooleanField(default=True)
    last_briefing_date = models.DateField(null=True, blank=True)

    def tz(self):
        try: return ZoneInfo(self.timezone)
        except Exception: return ZoneInfo("UTC")
    def today(self) -> date:
        return timezone.now().astimezone(self.tz()).date()

def profile_for(user):
    return Profile.objects.get_or_create(user=user)[0]

class Task(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"
        SKIPPED = "skipped", "Skipped"
    class Priority(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=80, blank=True)
    phase = models.CharField(max_length=80, blank=True)
    resource = models.CharField(max_length=300, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NOT_STARTED)
    scheduled_date = models.DateField()
    est_minutes = models.PositiveIntegerField(default=60)
    completed_at = models.DateTimeField(null=True, blank=True)
    plan_day = models.PositiveIntegerField(null=True, blank=True)
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date", "id"]
        indexes = [models.Index(fields=["user", "scheduled_date"]), models.Index(fields=["user", "status"])]
        constraints = [models.UniqueConstraint(fields=["user", "plan_day"], condition=models.Q(plan_day__isnull=False), name="uniq_user_plan_day")]

    def set_status(self, status):
        """Single place that keeps status and completed_at consistent (no double counting)."""
        if status not in self.Status.values: raise ValueError(status)
        if status == self.Status.COMPLETED and self.status != self.Status.COMPLETED:
            self.completed_at = timezone.now()
        elif status != self.Status.COMPLETED:
            self.completed_at = None
        self.status = status
        self.save(update_fields=["status", "completed_at"])


class LearningPlan(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_plans")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    is_template = models.BooleanField(default=False)
    share_token = models.UUIDField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def lesson_count(self):
        return Lesson.objects.filter(module__phase__plan=self).count()

    @property
    def completed_lessons(self):
        return Lesson.objects.filter(module__phase__plan=self, status=Lesson.Status.COMPLETED).count()

    @property
    def progress(self):
        total = self.lesson_count
        return round(self.completed_lessons * 100 / total) if total else 0

    def duplicate_for(self, owner, title=None):
        """Copy the curriculum tree as a private, editable plan."""
        from django.db import transaction
        with transaction.atomic():
            clone = LearningPlan.objects.create(owner=owner, title=title or f"{self.title} (copy)", description=self.description,
                start_date=self.start_date, target_date=self.target_date, status=self.Status.ACTIVE)
            for phase in self.phases.order_by("position", "id"):
                new_phase = Phase.objects.create(plan=clone, title=phase.title, position=phase.position)
                for module in phase.modules.order_by("position", "id"):
                    new_module = Module.objects.create(phase=new_phase, title=module.title, description=module.description, position=module.position)
                    for lesson in module.lessons.order_by("position", "id"):
                        Lesson.objects.create(module=new_module, title=lesson.title, description=lesson.description,
                            resource=lesson.resource, est_minutes=lesson.est_minutes, position=lesson.position)
        return clone


class Phase(models.Model):
    plan = models.ForeignKey(LearningPlan, on_delete=models.CASCADE, related_name="phases")
    title = models.CharField(max_length=160)
    position = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["position", "id"]


class Module(models.Model):
    phase = models.ForeignKey(Phase, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["position", "id"]


class Lesson(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource = models.URLField(blank=True)
    est_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NOT_STARTED)
    position = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["position", "id"]


class Goal(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        PAUSED = "paused", "Paused"
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=Task.Priority.choices, default=Task.Priority.MEDIUM)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    @property
    def progress(self):
        total = self.milestones.count()
        return round(self.milestones.filter(completed=True).count() * 100 / total) if total else 0


class Milestone(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=180)
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)


class FocusSession(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="focus_sessions")
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="focus_sessions")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    notes = models.CharField(max_length=300, blank=True)
    @property
    def minutes(self):
        return max(0, int((self.ended_at - self.started_at).total_seconds() // 60))


class Revision(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="revisions")
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class JobApplication(models.Model):
    class Status(models.TextChoices):
        SAVED = "saved", "Saved"
        APPLIED = "applied", "Applied"
        INTERVIEW = "interview", "Interviewing"
        OFFER = "offer", "Offer"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_applications")
    company = models.CharField(max_length=160)
    role = models.CharField(max_length=160)
    url = models.URLField(blank=True)
    applied_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SAVED)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]


class PracticeEntry(models.Model):
    class Kind(models.TextChoices):
        DSA = "dsa", "DSA practice"
        INTERVIEW = "interview", "Interview practice"
        OUTREACH = "outreach", "Career outreach"
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="practice_entries")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    title = models.CharField(max_length=200)
    platform = models.CharField(max_length=120, blank=True)
    resource = models.URLField(blank=True)
    outcome = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    happened_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-happened_at", "-id"]
