"""Python script runner sandboxed to config.SCRIPTS_ROOT.

Only files that already exist under the scripts root may be executed, and they
are run with the interpreter directly (never through a shell), so there is no
arbitrary-command surface. Output is captured and truncated.
"""
import os
import subprocess
import time

from flask import Blueprint, jsonify, request

from . import login_required, mutating
from .. import config, db, security

bp = Blueprint("scripts", __name__)
MAX_OUTPUT = 64 * 1024
RUN_TIMEOUT = 30


@bp.get("/api/scripts")
@login_required
def list_scripts():
    files = []
    if os.path.isdir(config.SCRIPTS_ROOT):
        for name in sorted(os.listdir(config.SCRIPTS_ROOT)):
            if name.endswith(".py"):
                files.append(name)
    with db.connect() as c:
        meta = {r["name"]: dict(r) for r in c.execute("SELECT * FROM scripts")}
    return jsonify([{"name": n, **meta.get(n, {"enabled": 0})} for n in files])


@bp.post("/api/scripts/run")
@mutating
def run_script():
    name = (request.get_json(silent=True) or {}).get("name", "")
    if not name.endswith(".py") or "/" in name or "\\" in name:
        return jsonify({"error": "invalid script name"}), 400
    path = security.safe_join(config.SCRIPTS_ROOT, name)
    if not os.path.isfile(path):
        return jsonify({"error": "not found"}), 404
    try:
        p = subprocess.run(["python3", path], capture_output=True, text=True,
                           timeout=RUN_TIMEOUT, cwd=config.SCRIPTS_ROOT)
        output = (p.stdout + p.stderr)[:MAX_OUTPUT]
        rc = p.returncode
    except subprocess.TimeoutExpired:
        output, rc = "(timed out)", 124
    with db.connect() as c:
        c.execute("INSERT OR IGNORE INTO scripts(name) VALUES(?)", (name,))
        c.execute("UPDATE scripts SET last_run=?, last_rc=? WHERE name=?",
                  (int(time.time()), rc, name))
    db.audit(request.remote_addr, "script.run", {"name": name, "rc": rc})
    return jsonify({"ok": rc == 0, "rc": rc, "output": output})


@bp.post("/api/scripts/toggle")
@mutating
def toggle():
    b = request.get_json(silent=True) or {}
    name, enabled = b.get("name"), int(bool(b.get("enabled")))
    with db.connect() as c:
        c.execute("INSERT OR IGNORE INTO scripts(name) VALUES(?)", (name,))
        c.execute("UPDATE scripts SET enabled=? WHERE name=?", (enabled, name))
    return jsonify({"ok": True})
