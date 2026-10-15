from datetime import date
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import models
from django.utils import timezone

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    timezone = models.CharField(max_length=64, default="Asia/Karachi")
    show_briefing = models.BooleanField(default=True)
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
