# Streetwise

The Streetwise Sharing Platform. React on the front, Django on the back, PostgreSQL underneath.

Version 1.0 lets anyone submit an event. New events start as Pending and show faded on the calendar. The admin approves them in Django admin, and the submitter gets an email. There are no user accounts in this version.

The API format for the frontend is in [docs/api.md](docs/api.md).

## What you need

- Python 3.10 or newer
- Node.js 20 or newer
- PostgreSQL 14 or newer, running locally

## 1. Create the database

PostgreSQL must be installed and running first. On macOS with Homebrew:

```bash
brew install postgresql@16
brew services start postgresql@16
```

Then make the database and its user:

```bash
createdb streetwise
psql -d streetwise -c "CREATE USER streetwise WITH PASSWORD 'change-me';"
psql -d streetwise -c "GRANT ALL PRIVILEGES ON DATABASE streetwise TO streetwise;"
psql -d streetwise -c "GRANT ALL ON SCHEMA public TO streetwise;"
```

The last line matters on PostgreSQL 15 and newer. Without it, migrations fail with a permission error.

## 2. Set up the backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the example environment file and fill it in:

```bash
cp .env.example .env
```

Open `.env` and set `POSTGRES_PASSWORD` to the password you used above. Generate a secret key and paste it into `DJANGO_SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Run the migrations. These create Django's own tables, the event tables, and the eight starting categories.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Check that it works:

- http://127.0.0.1:8000/api/health/ shows `{"status": "ok"}`.
- http://127.0.0.1:8000/api/categories/ lists the eight categories.
- http://127.0.0.1:8000/admin/ lets you log in with the superuser you just made. This is where the admin approves events. The admin never logs in through the React site.

### Emails

With no `EMAIL_HOST_PASSWORD` in `.env`, emails print in the terminal where `runserver` is running. That is enough for local work.

To send real email, put the Gmail app password in `.env`. Ask Nat for it. The site sends from `streetwisefall2026cohort@gmail.com` over SMTP on port 587. Port 25 will not work on AWS.

A failed email never blocks saving or approving an event. It is only logged, so check the server log when testing email.

### Approving events

In Django admin, open **Events**. Pending events are listed first. Use the **Status** filter on the right, or select events and pick an action:

- **Approve** sets the status to Approved and emails the submitter.
- **Reject** and **Cancel** hide the event and send no email. The row stays in the database.

You can also open one event and change its Status dropdown. Moving it to Approved sends the same email.

### Spam protection

Two layers protect the add event form. A hidden `fax_number` field catches bots (the frontend must include it, see `docs/api.md`). A rate limit allows 10 submits an hour from one visitor address. Both are on in local development. If you test the form a lot and hit the limit, either wait or raise `EVENT_SUBMIT_RATE` in `.env`.

The limit counters are kept in files in a `.cache/` folder in the project. Delete that folder to reset them.

### Reminders

Events that stay Pending for more than 24 hours trigger one email to the project inbox. Run it by hand to test:

```bash
python manage.py send_pending_reminders --dry-run   # show what would be sent
python manage.py send_pending_reminders             # send it
python manage.py send_pending_reminders --hours 1   # try it with a shorter wait
```

On the server, cron runs it every hour (see `docs/deploy-aws.md`).

### Tests

```bash
python manage.py test events
```

Tests run on PostgreSQL. Django makes its own temporary test database, so the `streetwise` database user needs the `CREATEDB` right:

```bash
psql -d streetwise -c "ALTER USER streetwise CREATEDB;"
```

## 3. Set up the frontend

In a second Terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. You should see the Streetwise heading.

The dev server forwards anything starting with `/api` to Django on port 8000. That is set in `frontend/vite.config.js`.

## Layout

```
manage.py              Django entry point
streetwise/            Django project settings and root URLs
  settings.py          Reads config from .env
  urls.py              Admin, health check, and the /api/ routes
events/                The events app
  models.py            Event and Category
  serializers.py       What the API accepts and returns
  views.py             The events, categories and private-link (manage) endpoints
  throttles.py         Rate limits for submit and manage calls
  management/commands/ send_pending_reminders (24 hour reminder email)
  admin.py             Approve, reject and cancel in Django admin
  emails.py            Receipt, new-event and approval emails
  tests.py
docs/api.md            API format for the frontend
docs/deploy-aws.md     Step-by-step server setup on AWS Lightsail
deploy/                Server config files (gunicorn, nginx, cron, backup)
frontend/              React app built with Vite
  src/
  vite.config.js       Dev server and /api proxy
requirements.txt       Python packages
.env.example           Template for your .env
```
