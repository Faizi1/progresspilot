# ProgressPilot feature status

Reviewed: 15 October 2026

## Implemented

- Registration with email, login/logout, password reset flow, profile email/name, timezone, daily study target, preferred study days, weekly review day, briefing preference, and notification preference.
- Per-user data scoping for tasks, plans, goals, practice, focus sessions, job applications, revisions, and all edit/status operations.
- Responsive dashboard with daily tasks, completion stats, weekly and overall progress, overdue work, real seven-day chart, subject progress, active plans/goals, and due revisions.
- Task create/edit/delete/reschedule, start/complete/skip/reopen, date/status/priority/subject filters, weekly calendar, CSV export, and task reminder scheduling fields.
- Per-user JSON task export/import with all-row validation, duplicate detection, and no writes when any row is invalid.
- Editable plans with phases/modules/lessons; lesson status and derived progress; private template flag; independent copies; revocable read-only share links; copying shared curriculum without copying the owner's progress.
- Goals with dated milestones, completion/reopen, and editing.
- Manual focus-session logs, task revision scheduling/completion, DSA/interview/outreach activity log, job application tracking/editing/status updates, and analytics from saved records.
- Idempotent import of the Faiz workbook into daily tasks and an editable plan tree.
- Django password reset. Locally, emails print to the console; SMTP delivery is configured with environment variables.
- Idempotent `send_reminders` management command for due open-task email reminders. A host scheduler must invoke it.

## Still incomplete or requiring operations setup

- No real-time stopwatch; focus sessions are entered after a session. No automatic time spent derivation from task status.
- Curriculum prerequisites, assessments, drag/reorder UI, archival, and mapping lessons to tasks are not implemented. Ordering positions can be edited manually.
- The practice tracker is a general activity log; it does not yet have DSA difficulty/attempt metrics, interview question banks, or a separate outreach contact pipeline.
- JSON export/import currently covers tasks only; there is no full-workspace backup/restore package for plans, goals, sessions, and career records.
- Reminder delivery requires a configured SMTP provider and external scheduler; there are no browser push notifications or in-app notification inbox.
- Read-only curriculum links are public to anyone who has the token. There are no invitations, access expiry, or template discovery catalog.
- Production deployment has not been performed. SQLite is the configured database; persistent hosting, backups, static-file serving, SMTP, HTTPS/domain, and scheduled command execution must be configured and verified for the selected host.
- No rate limiting, email verification, or automated cross-browser/mobile visual QA.

## Verification

Latest verification: `python manage.py check` and `python manage.py test` passed (20 tests). `makemigrations --check --dry-run`, `uv lock --check`, and `git diff --check` also passed. Coverage includes authentication and ownership, timezone-aware reminders, task JSON round-trip/validation, status transitions, briefing, importer idempotency, curriculum copy/share privacy, goal milestones, reminder email idempotency, and primary pages.
