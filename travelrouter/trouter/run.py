"""Entrypoints.

  python -m trouter.run            -> serve the appliance (waitress)
  python -m trouter.run set-admin  -> create/reset the admin user (prompts)
"""
import getpass
import sys
import time

from . import db, security, config
from .app import create_app


def set_admin(username="admin", password=None):
    db.init_db()
    if password is None:
        password = getpass.getpass(f"New password for '{username}': ")
    with db.connect() as c:
        c.execute(
            "INSERT INTO users(username, pw_hash, created) VALUES(?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET pw_hash=excluded.pw_hash",
            (username, security.hash_password(password), int(time.time())))
    print(f"admin user '{username}' set.")


def serve():
    app = create_app()
    host = "0.0.0.0"
    port = int(__import__("os").environ.get("TROUTER_PORT", "8080"))
    try:
        from waitress import serve as wserve
        print(f"travelrouter listening on {host}:{port}")
        wserve(app, host=host, port=port, threads=8)
    except ImportError:
        app.run(host=host, port=port)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "set-admin":
        set_admin(*(sys.argv[2:4]))
    else:
        serve()
