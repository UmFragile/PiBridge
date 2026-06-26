"""Flask application factory.

Wires the blueprints, session security, and the global before-request guards.
Run in production behind the bundled systemd unit via waitress (see run.py).
"""
import datetime
import os

from flask import Flask, render_template, session, redirect, url_for

from . import config, db, security
from .hal import events
from .api import auth, system, interfaces, aps, clients, vpn, files, scripts


def _secret_key():
    config.ensure_dirs()
    if os.path.exists(config.SECRET_KEY_FILE):
        with open(config.SECRET_KEY_FILE, "rb") as f:
            return f.read()
    key = os.urandom(32)
    with open(config.SECRET_KEY_FILE, "wb") as f:
        f.write(key)
    os.chmod(config.SECRET_KEY_FILE, 0o600)
    return key


def create_app(start_hotplug=True):
    db.init_db()
    app = Flask(__name__, template_folder="web/templates",
                static_folder="web/static")
    app.secret_key = _secret_key()
    app.permanent_session_lifetime = datetime.timedelta(
        minutes=config.SESSION_LIFETIME_MIN)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("TROUTER_HTTPS") == "1",
        MAX_CONTENT_LENGTH=512 * 1024 * 1024,
    )

    for bp in (auth.bp, system.bp, interfaces.bp, aps.bp, clients.bp,
               vpn.bp, files.bp, scripts.bp):
        app.register_blueprint(bp)

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'")
        return resp

    @app.get("/")
    def index():
        if not session.get("user"):
            return redirect(url_for("login_page"))
        return render_template("dashboard.html", csrf=security.issue_csrf())

    @app.get("/login")
    def login_page():
        return render_template("login.html")

    if start_hotplug:
        try:
            events.start()
        except Exception:
            pass

    return app
