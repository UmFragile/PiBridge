"""REST API blueprints. Every mutating route is CSRF-checked and auth-gated."""
from functools import wraps
from flask import session, jsonify, request

from .. import security


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("user"):
            return jsonify({"error": "authentication required"}), 401
        return fn(*a, **kw)
    return wrapper


def mutating(fn):
    """Auth + CSRF for any state-changing endpoint."""
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            security.check_csrf()
        return fn(*a, **kw)
    return wrapper
