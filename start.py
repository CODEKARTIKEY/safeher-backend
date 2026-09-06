#!/usr/bin/env python3
"""
One-command launcher for SafeHer.

Usage:
    python start.py       (or python3 start.py)

This installs any missing dependencies into your current Python
environment, starts the server, and opens the app in your browser.
Works the same way on Windows, macOS and Linux.
"""
import subprocess
import sys
import threading
import time
import webbrowser


def ensure_deps():
    try:
        import flask  # noqa: F401
        import werkzeug  # noqa: F401
    except ImportError:
        print("Installing dependencies from requirements.txt ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


def open_browser_when_ready():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    ensure_deps()

    # Imported after deps are confirmed installed. Importing runs app.py's
    # module-level setup (DB init + demo admin seeding) without triggering
    # its __main__ block, so we control how the server is started here.
    import app as safeher

    print("\n  SafeHer is starting: http://127.0.0.1:5000")
    print("  Demo admin login:    admin@safeher.local / Admin@123")
    print("  Admin dashboard:     http://127.0.0.1:5000/admin")
    print("  Press CTRL+C to stop.\n")

    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    safeher.app.run(host="127.0.0.1", port=5000, debug=safeher.DEBUG)
