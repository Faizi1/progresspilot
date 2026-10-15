# ProgressPilot (Faiz Recovery Tracker web app) - MVP

A small multi-user Django app for daily learning/career tracking. Each user only ever sees their own tasks.

## Implemented (and tested: `python manage.py test`, 13 tests)
- Registration, login, logout (Django auth, hashed passwords); every task view/edit/delete is scoped to the logged-in user (other users get 404).
- Dashboard: tasks today, done, remaining, overdue, this-week and overall completion, last-7-days completed bar chart, progress by subject. All from the database; empty states shown.
- Daily briefing dialog: shown on the first dashboard visit of each day (in the user's timezone), reopen with "Reopen briefing", can be turned off in Settings. Closing it never changes tasks.
- Tasks: add, edit, delete (with confirmation), filter (when/status/priority), Start / Done / Skip / Reopen. Completion time is stored once; reopening clears it so counts never double-count.
- `import_plan`: loads the "60-Day Plan" sheet of the tracker workbook as your tasks. Idempotent; never overwrites progress; validates before writing.
- CSV export of your tasks, `/health/` endpoint, per-user timezone.

## NOT implemented yet (honest list)
Learning-plan hierarchy editing (phases/modules/lessons), templates and sharing, goals and milestones, focus timer and time tracking, revision scheduling, DSA / interview / job trackers, analytics page, notifications and reminders (no scheduler, no push, no email), password reset, JSON import, rate limiting, calendar view, drag-and-drop. Tasks are the only data model now; the curriculum lives as imported tasks, not editable plans.
Not deployed. Nothing here has been run on a hosting service.

## Run locally
```
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser        # or register at /register/
python manage.py import_plan YOUR_USERNAME --start 2026-10-16 --dry-run
python manage.py import_plan YOUR_USERNAME --start 2026-10-16
python manage.py runserver
```
Open http://127.0.0.1:8000/ . Set your timezone in Settings (default Asia/Karachi).

## Deploy (not performed)
Needs a host that runs Python and keeps a disk (SQLite file) or a managed Postgres (change DATABASES; not done). Set the variables in `.env.example`, then:
```
python manage.py collectstatic --noinput && python manage.py migrate
gunicorn config.wsgi
```
Put it behind HTTPS. Run `DJANGO_DEBUG=0 python manage.py check --deploy` first. Back up `db.sqlite3` regularly (copy the file while the app is idle). Free tiers may sleep and may not persist disk: verify before trusting your data to one. Static files in production need a static server or WhiteNoise (not added).

## Structure
`core/models.py` (Profile, Task), `core/views.py`, `core/management/commands/import_plan.py`, `core/tests.py`. Only Python deps: Django, openpyxl, gunicorn.
