# Deploying Streetwise NYC to PythonAnywhere

PythonAnywhere can host the Django API and the compiled React frontend together. React is built into static files; Django serves the app shell and API.

1. Create a PythonAnywhere account and open a Bash console.
2. Clone or upload this project into `/home/<username>/Streetwise`.
3. Create a virtual environment and install `requirements.txt`.
4. Build the React app in `frontend/` with `npm install && npm run build`. If Node is unavailable on the selected plan, build locally and upload `frontend/dist/` with the project.
5. From the project root, run `python manage.py migrate` and `python manage.py collectstatic --noinput`.
6. Create a Manual Configuration web app using a supported Python version.
7. Set its virtualenv path and edit the WSGI file to add the project directory to `sys.path`, set `DJANGO_SETTINGS_MODULE=streetwise.settings`, and load `get_wsgi_application()`.
8. Add a static mapping from `/static/` to `/home/<username>/Streetwise/staticfiles`.
9. Configure the production values listed in the main README, then reload the web app.

SQLite is appropriate for this low-volume first version. Back up `db.sqlite3` regularly. A later authenticated or higher-traffic version should move to a managed database and add moderation controls.
