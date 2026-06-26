"""Sandboxed file manager rooted at config.FILES_ROOT (/srv/files).

Every path is resolved through security.safe_join, which refuses anything that
escapes the sandbox — blocking directory traversal.
"""
import os
import shutil

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from . import login_required, mutating
from .. import config, security

bp = Blueprint("files", __name__)


@bp.get("/api/files")
@login_required
def listing():
    rel = request.args.get("path", "")
    target = security.safe_join(config.FILES_ROOT, rel)
    if not os.path.isdir(target):
        return jsonify({"error": "not a directory"}), 400
    entries = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        st = os.stat(full)
        entries.append({"name": name, "dir": os.path.isdir(full),
                        "size": st.st_size, "mtime": int(st.st_mtime)})
    du = shutil.disk_usage(config.FILES_ROOT)
    return jsonify({"path": rel, "entries": entries,
                    "free_mb": du.free // (1024 * 1024)})


@bp.get("/api/files/download")
@login_required
def download():
    target = security.safe_join(config.FILES_ROOT, request.args.get("path", ""))
    if not os.path.isfile(target):
        return jsonify({"error": "not found"}), 404
    return send_file(target, as_attachment=True)


@bp.post("/api/files/upload")
@mutating
def upload():
    rel = request.form.get("path", "")
    folder = security.safe_join(config.FILES_ROOT, rel)
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400
    name = secure_filename(f.filename)
    f.save(security.safe_join(folder, name))
    return jsonify({"ok": True, "name": name})


@bp.post("/api/files/mkdir")
@mutating
def mkdir():
    b = request.get_json(silent=True) or {}
    target = security.safe_join(config.FILES_ROOT, b.get("path", ""),
                                secure_filename(b.get("name", "")))
    os.makedirs(target, exist_ok=True)
    return jsonify({"ok": True})


@bp.delete("/api/files")
@mutating
def delete():
    target = security.safe_join(config.FILES_ROOT,
                                (request.get_json(silent=True) or {}).get("path", ""))
    if os.path.isdir(target):
        shutil.rmtree(target)
    elif os.path.exists(target):
        os.remove(target)
    return jsonify({"ok": True})
