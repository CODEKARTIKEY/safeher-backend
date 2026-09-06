# SafeHer — Personal Safety Command Center

A full-stack women-safety web app: emergency SOS, live GPS sharing, trusted
contacts, incident reporting, safety check-in timers, a nearby-help map, a
safety guide, and an admin analytics dashboard.

**Backend:** Flask + SQLite + hashed passwords.
**Frontend:** Vanilla HTML/CSS/JS (no build step).

---

## Quick start (any OS)

Requires Python 3.9+.

```bash
python start.py
```
*(use `python3 start.py` if your system's `python` points to Python 2)*

This installs Flask automatically if it isn't already present, starts the
server, and opens **http://127.0.0.1:5000** in your browser for you.

### Alternative: manual venv setup

**Windows** — double-click `run_windows.bat`, or:
```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**macOS / Linux** — run `./run_mac_linux.sh`, or:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000

## Demo login

A demo admin account is created automatically the first time the app runs:

```
Email:    admin@safeher.local
Password: Admin@123
```

Admin dashboard: http://127.0.0.1:5000/admin
(You can also register your own regular-user account from the app's login modal.)

## Live location

Open the **Live Location** page and allow the browser's GPS permission
prompt. It uses `navigator.geolocation.watchPosition()` and posts updates to
`/api/location`.

## Configuration (optional)

| Environment variable | Purpose | Default |
|---|---|---|
| `SAFEHER_SECRET` | Flask session signing key | auto-generated once and stored in `instance/secret.key` |
| `SAFEHER_DEBUG` | Set to `1` to enable Flask's debug reloader while developing | `0` (off) |

## Project structure

```
app.py                  Flask app: routes, API, database
requirements.txt        Python dependencies
start.py                One-command cross-platform launcher
run_windows.bat          Windows setup + run script
run_mac_linux.sh        macOS/Linux setup + run script
templates/index.html    Main app UI
templates/admin.html    Admin analytics page
static/css/style.css    Styling
static/js/app.js        Frontend logic (auth, GPS, SOS, forms)
static/uploads/         Uploaded incident-report evidence
instance/               SQLite database + session secret (created on first run)
```

## Important — read before real-world use

This is an educational/demo project, **not** a certified emergency service.
It has been hardened for correctness (input validation, no debug traceback
pages, safer file-upload handling — see below) but real deployment still
requires, at minimum: HTTPS, CSRF protection, rate limiting, a production
WSGI server (e.g. gunicorn/waitress) instead of Flask's dev server, a
production-grade database, stricter upload scanning, privacy/consent
controls, and verified integrations with real emergency services.

## What's in this build

Starting from the original prototype, this pass fixed several bugs found by
exercising the API directly, so the app behaves correctly under real-world
(not just happy-path) use:

- **Input validation on every API endpoint.** Missing/invalid fields (e.g. a
  contact with no phone number, a location update with no coordinates) used
  to crash the server with a raw Python traceback page. They now return a
  clean `400` JSON error the frontend already knows how to display.
- **Fixed the admin dashboard's "Active Tracking" count**, which could
  overcount because it compared two differently-formatted timestamps; it now
  compares like-for-like and reports the right number of users with a
  location update in the last 10 minutes.
- **Debug mode is off by default** (it previously exposed Werkzeug's
  interactive debugger — including a Python console — on every unhandled
  error). Set `SAFEHER_DEBUG=1` if you want the reloader while developing.
- **Session secret persists across restarts** instead of using a fixed
  fallback string, so logins survive a server restart without any setup.
- **Demo admin account is seeded automatically** on first run — no need to
  visit `/seed-admin` manually (that route still exists if you ever need to
  recreate it).
- **Evidence uploads are now validated**: only image/PDF file types are
  accepted, and total upload size is capped at 8&nbsp;MB.
- **Cross-platform launch scripts** (`start.py`, `run_mac_linux.sh`, an
  updated `run_windows.bat`) so setup is a single command on any OS.
