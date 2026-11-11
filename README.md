# Streetwise NYC

A community-powered NYC events calendar. Anyone can share an event; submissions appear immediately. Version one intentionally has no accounts or authentication.

## Stack

- Django + SQLite JSON API
- React + Vite frontend
- One-app deployment suitable for PythonAnywhere

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
cd frontend && npm install && npm run build && cd ..
python manage.py runserver
```

For frontend development, run `npm run dev` inside `frontend/` while Django runs on port 8000. Vite proxies `/api` requests to Django.

## Production environment

Set these variables in the PythonAnywhere WSGI configuration or environment:

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<a-long-random-value>
DJANGO_ALLOWED_HOSTS=<yourusername>.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://<yourusername>.pythonanywhere.com
```

Build the frontend before reloading the web app:

```bash
cd ~/Streetwise/frontend
npm install
npm run build
cd ..
python manage.py migrate
python manage.py collectstatic --noinput
```

In PythonAnywhere, configure the source directory as the repository root, point the WSGI file at `streetwise.wsgi`, and map `/static/` to the `staticfiles` directory. See `docs/pythonanywhere-deployment.md` for the complete checklist.

