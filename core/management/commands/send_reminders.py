from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Task, profile_for


class Command(BaseCommand):
    help = "Send due task reminder emails. Schedule this command with cron or your host's scheduler."

    def handle(self, *args, **options):
        now=timezone.now(); sent=0; skipped=0; failed=0
        due=Task.objects.filter(reminder_at__lte=now, reminder_sent_at__isnull=True,
            status__in=[Task.Status.NOT_STARTED, Task.Status.IN_PROGRESS, Task.Status.BLOCKED]).select_related("user")
        for task in due.iterator():
            profile=profile_for(task.user)
            if not profile.notifications_enabled or not task.user.email:
                skipped += 1; continue
            try:
                count=send_mail(f"ProgressPilot reminder: {task.title}",
                    f"This is your reminder for: {task.title}\nScheduled for {task.scheduled_date}.\n\nSign in to ProgressPilot to update the task.",
                    None, [task.user.email], fail_silently=False)
                if count:
                    task.reminder_sent_at=now; task.save(update_fields=["reminder_sent_at"]); sent += 1
                else: failed += 1
            except Exception as exc:
                failed += 1; self.stderr.write(f"Could not send reminder for task {task.pk}: {exc}")
        self.stdout.write(f"Reminders sent: {sent}; skipped (disabled or no email): {skipped}; failed: {failed}.")
