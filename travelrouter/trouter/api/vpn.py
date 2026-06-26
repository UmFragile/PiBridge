"""VPN profile management."""
import time

from flask import Blueprint, jsonify, request

from . import login_required, mutating
from .. import db
from ..services import vpn

bp = Blueprint("vpn", __name__)


@bp.get("/api/vpn")
@login_required
def list_vpn():
    return jsonify(vpn.status())


@bp.post("/api/vpn")
@mutating
def create_vpn():
    b = request.get_json(silent=True) or {}
    if b.get("kind") not in ("wireguard", "openvpn") or not b.get("config_blob"):
        return jsonify({"error": "kind and config_blob required"}), 400
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO vpn_profiles(name, kind, config_blob, kill_switch, "
            "auto_reconnect, created) VALUES(?,?,?,?,?,?)",
            (b.get("name", "vpn"), b["kind"], b["config_blob"],
             int(b.get("kill_switch", 1)), int(b.get("auto_reconnect", 1)),
             int(time.time())))
        vid = cur.lastrowid
    db.audit(request.remote_addr, "vpn.create", {"id": vid})
    return jsonify({"ok": True, "id": vid})


@bp.delete("/api/vpn/<int:vid>")
@mutating
def delete_vpn(vid):
    with db.connect() as c:
        c.execute("DELETE FROM vpn_profiles WHERE id=?", (vid,))
    return jsonify({"ok": True})
