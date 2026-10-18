# ProgressPilot

ProgressPilot is a multi-user Django learning and career tracker. It includes a responsive daily dashboard, tasks, editable learning curricula, goals, practice logs, job applications, revisions, and email reminders. Every private record is scoped to its owner. Current scope and limitations are listed in [FEATURE_STATUS.md](FEATURE_STATUS.md).

## Run locally

Python 3.13+ is expected by the project metadata.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and register an account with an email address. Local password reset emails are printed in the runserver console. The database defaults to `db.sqlite3`; set `DJANGO_DB_PATH` to use another SQLite file.

## Initialize the Faiz workbook

The workbook at `data/Faiz_Recovery_Tracker.xlsx` is kept unchanged. Register the account first, then preview and import its 60-Day Plan:

```powershell
python manage.py import_plan YOUR_USERNAME --start 2026-10-16 --dry-run
python manage.py import_plan YOUR_USERNAME --start 2026-10-16
```

Import is idempotent. It creates the existing 60 daily tasks and an editable curriculum tree (phases, subject modules, and lessons) once. Re-running it does not overwrite task progress or duplicate the curriculum. Change the start date to the date you want Day 1 scheduled.

## Reminders and email

Set a reminder date/time on a task and enable notifications in Settings. By default, email uses Django's console backend, so messages are printed locally. For delivery, configure the SMTP variables in `.env.example` in the hosting environment. Never commit real credentials.

The app does not run a background worker. Schedule this command every 5–15 minutes with Windows Task Scheduler, cron, or the host's scheduler:

```powershell
python manage.py send_reminders
```

The command sends due reminders for open tasks only, skips users with notifications disabled or no email address, and marks successful sends so repeated runs do not duplicate them. Failed sends remain queued for retry. The scheduler and SMTP provider must be configured by the operator.

## Tests

```powershell
python manage.py test
```

The suite covers authentication, user isolation, task state and briefing behavior, workbook import, curriculum copy/privacy, goals/milestones, email reminder idempotency, and new page rendering.

## Deployment preparation

Deployment has not been performed. The app currently uses SQLite; use a host with persistent disk, back up the database, and confirm the host's file persistence and concurrency limits before inviting other users. Set `DJANGO_DEBUG=0`, a strong generated `DJANGO_SECRET_KEY`, correct `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS`. Configure SMTP for password reset and reminders. Terminate HTTPS at the host/proxy; secure cookies and HTTPS redirect are enabled in production settings by default.

Typical host commands:

```sh
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn config.wsgi
```

Run migrations before starting the new release and take a database backup first. Static files (including Django admin assets) need a static-file server; this repository does not include WhiteNoise or a platform-specific static configuration yet. Do not treat this as a verified production deployment until that is configured and tested on the chosen host.

## Useful routes

- `/` dashboard; `/tasks/` task list; `/calendar/` weekly calendar
- `/plans/` curriculum; `/goals/`; `/focus/`; `/practice/`; `/career/`; `/analytics/`
- `/settings/`; `/export.csv`; `/export.json`; `/tasks/import-json/`; `/health/`; `/accounts/password_reset/`
- `/admin/` Django admin (staff users only)
