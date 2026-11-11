# Streetwise NYC

Streetwise NYC is a community calendar for events in New York City. People can browse events by month, filter them by category, and share an event without creating an account.

This guide is written for people who have not used Django or React before. Follow the steps in order.

## What you need before you start

Install these programs on your computer:

- [Git](https://git-scm.com/downloads)
- [Python 3](https://www.python.org/downloads/) (Python 3.10 or newer)
- [Node.js](https://nodejs.org/) (choose the LTS version)

You will use Terminal on macOS or Linux. On Windows, use PowerShell or Git Bash.

Check that the programs are installed:

```bash
git --version
python3 --version
node --version
npm --version
```

On Windows, use `python` instead of `python3` if `python3` is not recognized.

## 1. Download the project

Open Terminal and run:

```bash
git clone https://github.com/Natkuma01/Streetwise.git
cd Streetwise
```

The second command moves Terminal into the project folder. Run the rest of the commands from this folder unless a step says otherwise.

## 2. Set up the Django backend

Django stores the events and provides them to the calendar. First, create a private Python environment for the project.

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

When the environment is active, you should see `(.venv)` near the beginning of the Terminal line.

Install the Python packages:

```bash
pip install -r requirements.txt
```

## 3. Create the local database

The app uses SQLite. SQLite is a small database stored in a file, so you do not need to install or configure a separate database program.

Create the database tables:

```bash
python manage.py migrate
```

On macOS or Linux, use `python3 manage.py migrate` if `python` is not recognized.

This creates a local `db.sqlite3` file. It is only for your computer and is not uploaded to GitHub.

## 4. Install the React frontend

The frontend is the calendar you see in the browser. Move into the frontend folder and install its packages:

```bash
cd frontend
npm install
cd ..
```

The last command returns you to the main `Streetwise` folder.

## 5. Run the app locally

The Django backend and React frontend need to run at the same time. Use two Terminal windows.

### Terminal 1: run Django

From the main `Streetwise` folder, activate the Python environment if it is not already active, then run:

```bash
python manage.py runserver
```

On macOS or Linux, use `python3 manage.py runserver` if needed.

Keep this Terminal open. Django will run at `http://127.0.0.1:8000`.

### Terminal 2: run React

Open a second Terminal window. Go to the project frontend folder and run:

```bash
cd Streetwise/frontend
npm run dev
```

If your project is somewhere else, change `Streetwise/frontend` to its actual location.

Terminal will show a local address, usually:

```text
http://localhost:5173
```

Open that address in your web browser. You should now see the Streetwise NYC calendar.

## 6. Stop the app

In each Terminal window, press `Control + C` to stop its server.

To leave the Python environment, run:

```bash
deactivate
```

## Everyday startup

After the first setup, you do not need to reinstall everything or recreate the database. For future sessions:

1. Open Terminal in the `Streetwise` folder.
2. Activate `.venv`.
3. Run `python manage.py runserver`.
4. In a second Terminal, open `Streetwise/frontend` and run `npm run dev`.
5. Visit `http://localhost:5173`.

## Common problems

### `python` or `python3` is not recognized

Install Python, close Terminal, and open it again. Windows commonly uses `python`; macOS and Linux commonly use `python3`.

### `node` or `npm` is not recognized

Install the LTS version of Node.js, close Terminal, and open it again.

### The page opens but no events appear

Make sure the Django server is still running in the first Terminal window. The React app gets its event data from Django.

### The database reports missing tables

From the main project folder, run:

```bash
python manage.py migrate
```

### A port is already in use

Another copy of the server may already be running. Find its Terminal window and press `Control + C`, then start the server again.

## Project folders

- `frontend/` contains the React calendar and visual design.
- `events/` contains the event database model and API.
- `streetwise/` contains the main Django settings.
- `docs/` contains deployment instructions.
- `manage.py` is the command used to run Django tasks.

## Deployment

The app is designed so Django and the compiled React frontend can be hosted together on PythonAnywhere. See [the PythonAnywhere deployment guide](docs/pythonanywhere-deployment.md) when you are ready to publish it.
