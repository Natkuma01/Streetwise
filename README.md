# Streetwise

Skeleton for the Streetwise Sharing Platform. React on the front, Django on the back, PostgreSQL underneath. No features yet. This branch exists to prove the three pieces talk to each other.

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

Run the migrations. These only create Django's own tables. There are no project models yet.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Check that it works: open http://127.0.0.1:8000/api/health/ and you should see `{"status": "ok"}`.

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
  urls.py              Admin plus a health check
frontend/              React app built with Vite
  src/
  vite.config.js       Dev server and /api proxy
requirements.txt       Python packages
.env.example           Template for your .env
```
