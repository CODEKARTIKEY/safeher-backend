import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, session, redirect
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(BASE, "instance")
DB = os.path.join(INSTANCE, "safeher.db")
UPLOAD = os.path.join(BASE, "static", "uploads")
os.makedirs(INSTANCE, exist_ok=True)
os.makedirs(UPLOAD, exist_ok=True)

# ---- App setup -------------------------------------------------------------
app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["*"])

# Cookie & Session persistence configuration
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True

# A stable random secret is generated on first run and stored locally, so
# logins survive server restarts without ever hard-coding a secret in code.
# Set the SAFEHER_SECRET environment variable to override it explicitly.
SECRET_FILE = os.path.join(INSTANCE, "secret.key")
if os.environ.get("SAFEHER_SECRET"):
    app.secret_key = os.environ["SAFEHER_SECRET"]
else:
    if not os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "w") as f:
            f.write(secrets.token_hex(32))
    with open(SECRET_FILE) as f:
        app.secret_key = f.read().strip()

# Reject uploads over 8 MB outright instead of letting them hang or crash.
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
ALLOWED_EVIDENCE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEBUG = os.environ.get("SAFEHER_DEBUG", "0") == "1"


def now_iso():
    return datetime.now().isoformat()


def bad(message, code=400):
    return jsonify(ok=False, message=message), code


# ---- Database ---------------------------------------------------------------
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    c = conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            phone TEXT,
            relation TEXT,
            primary_contact INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS locations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lat REAL,
            lng REAL,
            accuracy REAL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lat REAL,
            lng REAL,
            status TEXT,
            created_at TEXT,
            resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS incidents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            details TEXT,
            date TEXT,
            severity TEXT,
            lat REAL,
            lng REAL,
            anonymous INTEGER,
            evidence TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS checkins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            minutes INTEGER,
            expires_at TEXT,
            status TEXT,
            created_at TEXT
        );
        """
    )
    c.commit()
    c.close()


def ensure_demo_admin():
    """Create the demo admin account on first run so the app is usable
    immediately without an extra manual setup step."""
    c = conn()
    exists = c.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone()
    if not exists:
        c.execute(
            "INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
            ("Admin", "admin@safeher.local", generate_password_hash("Admin@123"), "admin", now_iso()),
        )
        c.commit()
    c.close()


init_db()
ensure_demo_admin()


def user():
    if not session.get("uid"):
        return None
    c = conn()
    u = c.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    c.close()
    return u


def json_body():
    """Always returns a dict, even for empty/missing/non-JSON bodies."""
    return request.get_json(silent=True) or {}


# ---- Pages --------------------------------------------------------------
@app.get("/")
def home():
    return render_template("index.html", user=user())


# ---- Auth -----------------------------------------------------------------
@app.post("/api/register")
def register():
    d = json_body()
    name = str(d.get("name", "")).strip()
    email = str(d.get("email", "")).lower().strip()
    pw = str(d.get("password", ""))

    if not name:
        return bad("Please enter your name")
    if not email or not EMAIL_RE.match(email):
        return bad("Please enter a valid email address")
    if len(pw) < 6:
        return bad("Password must be at least 6 characters")

    c = conn()
    try:
        cur = c.execute(
            "INSERT INTO users(name,email,password,created_at) VALUES(?,?,?,?)",
            (name, email, generate_password_hash(pw), now_iso()),
        )
        c.commit()
        user_id = cur.lastrowid
        session.permanent = True
        session["uid"] = user_id
    except sqlite3.IntegrityError:
        c.close()
        return bad("Email already registered", 409)
    c.close()

    return jsonify(
        ok=True,
        name=name,
        user={"id": user_id, "name": name, "email": email, "role": "user"}
    )


@app.post("/api/login")
def login():
    d = json_body()
    email = str(d.get("email", "")).strip().lower()
password = str(d.get("password", ""))

c = conn()

u = c.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
c.close()

if not u or not check_password_hash(u["password"], password):
    return bad("Invalid credentials", 401)
    session.permanent = True
    session["uid"] = u["id"]

    return jsonify(
        ok=True,
        name=u["name"],
        role=u["role"],
        user={"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]}
    )


@app.post("/api/forgot-password")
def forgot_password():
    d = json_body()
    email = str(d.get("email", "")).lower().strip()
    new_password = str(d.get("new_password", "")).strip()

    if not email or not new_password:
        return bad("Email and new password are required")
    if len(new_password) < 6:
        return bad("Password must be at least 6 characters long")

    c = conn()
    u = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not u:
        c.close()
        return bad("No account found with this email address", 404)

    c.execute(
        "UPDATE users SET password=? WHERE id=?",
        (generate_password_hash(new_password), u["id"])
    )
    c.commit()
    c.close()

    return jsonify(ok=True, message="Password updated successfully. You can now sign in.")


@app.route("/api/logout", methods=["POST", "GET"])
def api_logout():
    session.clear()
    return jsonify(ok=True, message="Logged out successfully")


@app.get("/api/me")
def me():
    u = user()
    return jsonify(ok=True, user=dict(u) if u else None)


# ---- Trusted contacts -----------------------------------------------------
@app.route("/api/contacts", methods=["GET", "POST"])
def contacts():
    u = user()
    # Fallback to guest user ID 0 if session cookie isn't present
    user_id = u["id"] if u else 0

    c = conn()
    if request.method == "POST":
        d = json_body()
        name = str(d.get("name", "")).strip()
        phone = str(d.get("phone", "")).strip()
        if not name or not phone:
            c.close()
            return bad("Name and phone number are required")
        c.execute(
            "INSERT INTO contacts(user_id,name,phone,relation,primary_contact) VALUES(?,?,?,?,?)",
            (user_id, name, phone, str(d.get("relation", "")).strip(), int(bool(d.get("primary", False)))),
        )
        c.commit()
    rows = c.execute(
        "SELECT * FROM contacts WHERE user_id=? ORDER BY primary_contact DESC,id", (user_id,)
    ).fetchall()
    c.close()
    return jsonify(ok=True, contacts=[dict(x) for x in rows])


@app.delete("/api/contacts/<int:cid>")
def del_contact(cid):
    u = user()
    user_id = u["id"] if u else 0
    c = conn()
    c.execute("DELETE FROM contacts WHERE id=? AND user_id=?", (cid, user_id))
    c.commit()
    c.close()
    return jsonify(ok=True)


# ---- Live location ----------------------------------------------------------
@app.post("/api/location")
def location():
    u = user()
    user_id = u["id"] if u else 0
    d = json_body()
    try:
        lat = float(d["lat"])
        lng = float(d["lng"])
    except (KeyError, TypeError, ValueError):
        return bad("Valid lat/lng coordinates are required")
    accuracy = d.get("accuracy")
    try:
        accuracy = float(accuracy) if accuracy is not None else None
    except (TypeError, ValueError):
        accuracy = None

    c = conn()
    c.execute(
        "INSERT INTO locations(user_id,lat,lng,accuracy,created_at) VALUES(?,?,?,?,?)",
        (user_id, lat, lng, accuracy, now_iso()),
    )
    c.commit()
    c.close()
    return jsonify(ok=True)


# ---- SOS --------------------------------------------------------------------
@app.post("/api/sos")
def sos():
    u = user()
    d = json_body()

    def to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    lat, lng = to_float(d.get("lat")), to_float(d.get("lng"))
    c = conn()
    cur = c.execute(
        "INSERT INTO sos(user_id,lat,lng,status,created_at) VALUES(?,?,?,?,?)",
        (u["id"] if u else None, lat, lng, "ACTIVE", now_iso()),
    )
    c.commit()
    aid = cur.lastrowid
    c.close()
    return jsonify(ok=True, id=aid)


@app.post("/api/sos/<int:aid>/resolve")
def resolve(aid):
    u = user()
    if not u:
        return bad("Please login", 401)
    c = conn()
    c.execute(
        "UPDATE sos SET status='RESOLVED',resolved_at=? WHERE id=? AND user_id=?",
        (now_iso(), aid, u["id"]),
    )
    c.commit()
    c.close()
    return jsonify(ok=True)


# ---- Incident reports -------------------------------------------------------
def allowed_evidence(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EVIDENCE_EXT


@app.route("/api/incidents", methods=["GET", "POST"])
def incidents():
    u = user()
    user_id = u["id"] if u else 0
    if request.method == "POST":
        d = request.form
        itype = d.get("type", "").strip()
        details = d.get("details", "").strip()
        date = d.get("date", "").strip()
        if not itype or not details or not date:
            return bad("Incident type, date and description are required")

        evidence_name = ""
        f = request.files.get("evidence")
        if f and f.filename:
            if not allowed_evidence(f.filename):
                return bad("Evidence must be an image or PDF file")
            evidence_name = uuid.uuid4().hex + "_" + secure_filename(f.filename)
            f.save(os.path.join(UPLOAD, evidence_name))

        def to_float(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        c = conn()
        c.execute(
            """INSERT INTO incidents(user_id,type,details,date,severity,lat,lng,anonymous,evidence,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id,
                itype,
                details,
                date,
                d.get("severity", "medium"),
                to_float(d.get("lat")),
                to_float(d.get("lng")),
                int(d.get("anonymous") == "true"),
                evidence_name,
                now_iso(),
            ),
        )
        c.commit()
        c.close()
        return jsonify(ok=True)

    c = conn()
    rows = c.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 50").fetchall()
    c.close()
    return jsonify(ok=True, incidents=[dict(x) for x in rows])


# ---- Safety check-in timer --------------------------------------------------
@app.post("/api/checkin")
def checkin():
    u = user()
    user_id = u["id"] if u else 0
    d = json_body()
    try:
        mins = int(d.get("minutes", 15))
    except (TypeError, ValueError):
        mins = 15
    mins = max(1, min(mins, 24 * 60))
    expires = (datetime.now() + timedelta(minutes=mins)).isoformat()

    c = conn()
    cur = c.execute(
        "INSERT INTO checkins(user_id,minutes,expires_at,status,created_at) VALUES(?,?,?,?,?)",
        (user_id, mins, expires, "ACTIVE", now_iso()),
    )
    c.commit()
    c.close()
    return jsonify(ok=True, id=cur.lastrowid, expires=expires)


# ---- Admin ------------------------------------------------------------------
@app.get("/api/dashboard")
def dashboard():
    u = user()
    if not u or u["role"] != "admin":
        return bad("Forbidden", 403)
    c = conn()
    cutoff = (datetime.now() - timedelta(minutes=10)).isoformat()
    out = {
        "users": c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"],
        "sos": c.execute("SELECT COUNT(*) n FROM sos").fetchone()["n"],
        "active": c.execute("SELECT COUNT(*) n FROM sos WHERE status='ACTIVE'").fetchone()["n"],
        "reports": c.execute("SELECT COUNT(*) n FROM incidents").fetchone()["n"],
        "tracking": c.execute(
            "SELECT COUNT(DISTINCT user_id) n FROM locations WHERE created_at>=?", (cutoff,)
        ).fetchone()["n"],
        "types": [
            dict(x)
            for x in c.execute(
                "SELECT type,COUNT(*) count FROM incidents GROUP BY type ORDER BY count DESC"
            ).fetchall()
        ],
    }
    c.close()
    return jsonify(ok=True, **out)


@app.get("/admin")
def admin():
    u = user()
    if not u or u["role"] != "admin":
        return redirect("/")
    return render_template("admin.html", user=u)


@app.get("/seed-admin")
def seed():
    c = conn()
    try:
        c.execute(
            "INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
            ("Admin", "admin@safeher.local", generate_password_hash("Admin@123"), "admin", now_iso()),
        )
        c.commit()
        msg = "Admin created"
    except sqlite3.IntegrityError:
        msg = "Admin already exists"
    c.close()
    return msg + " — admin@safeher.local / Admin@123"


# ---- Error handlers ---------------------------------------------------------
@app.errorhandler(413)
def too_large(e):
    return bad("File is too large (max 8 MB)", 413)


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return bad("Not found", 404)
    return redirect("/")


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return bad("Something went wrong on the server", 500)
    raise e


if __name__ == "__main__":
    print("\n  SafeHer is running: http://127.0.0.1:5000")
    print("  Demo admin login:   admin@safeher.local / Admin@123")
    print("  Admin dashboard:    http://127.0.0.1:5000/admin\n")
    app.run(host="127.0.0.1", port=5000, debug=DEBUG)