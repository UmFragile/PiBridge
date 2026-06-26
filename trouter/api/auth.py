"""Authentication endpoints."""
import time

from flask import Blueprint, request, session, jsonify

from .. import db, security

bp = Blueprint("auth", __name__)


@bp.post("/api/login")
def login():
    ip = request.remote_addr or "?"
    if not security.login_allowed(ip):
        return jsonify({"error": "too many attempts; try again later"}), 429
    data = request.get_json(silent=True) or {}
    user, pw = data.get("username", ""), data.get("password", "")
    with db.connect() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
    if row and security.verify_password(pw, row["pw_hash"]):
        security.reset_login(ip)
        session.clear()
        session["user"] = user
        session.permanent = True
        security.issue_csrf()
        db.audit(user, "login.ok")
        return jsonify({"ok": True, "csrf": session["csrf"]})
    security.record_failed_login(ip)
    db.audit(user or "?", "login.fail")
    return jsonify({"error": "invalid credentials"}), 401


@bp.post("/api/logout")
def logout():
    user = session.get("user")
    session.clear()
    db.audit(user, "logout")
    return jsonify({"ok": True})


@bp.get("/api/session")
def whoami():
    if session.get("user"):
        return jsonify({"user": session["user"], "csrf": security.issue_csrf()})
    return jsonify({"user": None}), 401
