"""Security primitives shared across the API.

  * Password hashing with PBKDF2-HMAC-SHA256 (stdlib only — no native deps to
    fight on the Pi).
  * CSRF tokens bound to the session.
  * In-memory login rate limiting / lockout.
  * Path-safety helper used by the file manager and script runner to prevent
    directory traversal outside their sandboxes.
"""
import hashlib
import hmac
import os
import secrets
import time

from flask import session, request, abort

_PBKDF_ROUNDS = 200_000
_login_attempts = {}      # ip -> [timestamps]


# -- passwords ----------------------------------------------------------
def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password, stored):
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# -- CSRF ---------------------------------------------------------------
def issue_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    sent = request.headers.get("X-CSRF-Token")
    if not sent and request.is_json:
        sent = (request.get_json(silent=True) or {}).get("_csrf")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(403, "CSRF token missing or invalid")


# -- login throttling ---------------------------------------------------
def login_allowed(ip):
    from .config import LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_SEC
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_LOCKOUT_SEC]
    _login_attempts[ip] = attempts
    return len(attempts) < LOGIN_MAX_ATTEMPTS


def record_failed_login(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


def reset_login(ip):
    _login_attempts.pop(ip, None)


# -- path safety --------------------------------------------------------
def safe_join(root, *parts):
    """Join under root, refusing any path that escapes it. Returns abs path."""
    root = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root, *parts))
    if target != root and not target.startswith(root + os.sep):
        abort(400, "path escapes sandbox")
    return target
