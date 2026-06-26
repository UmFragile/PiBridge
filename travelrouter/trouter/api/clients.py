"""Client (DHCP lease) listing and per-client actions."""
import time

from flask import Blueprint, jsonify, request

from . import login_required, mutating
from .. import db
from ..services import run

bp = Blueprint("clients", __name__)

LEASES = "/var/lib/misc/dnsmasq.leases"


def _leases():
    out = []
    try:
        with open(LEASES) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4:
                    out.append({"expires": int(parts[0]), "mac": parts[1],
                                "ip": parts[2], "hostname": parts[3]})
    except OSError:
        pass
    return out


@bp.get("/api/clients")
@login_required
def list_clients():
    with db.connect() as c:
        meta = {r["mac"]: dict(r) for r in c.execute("SELECT * FROM clients")}
    clients = []
    for lease in _leases():
        m = meta.get(lease["mac"], {})
        clients.append({**lease,
                        "label": m.get("label"),
                        "blocked": bool(m.get("blocked")),
                        "reserved_ip": m.get("reserved_ip")})
    return jsonify(clients)


@bp.post("/api/clients/<mac>/action")
@mutating
def action(mac):
    body = request.get_json(silent=True) or {}
    act = body.get("action")
    now = int(time.time())
    with db.connect() as c:
        c.execute("INSERT OR IGNORE INTO clients(mac, first_seen, last_seen) "
                  "VALUES(?,?,?)", (mac, now, now))
        if act == "block":
            c.execute("UPDATE clients SET blocked=1 WHERE mac=?", (mac,))
        elif act == "allow":
            c.execute("UPDATE clients SET blocked=0 WHERE mac=?", (mac,))
        elif act == "rename":
            c.execute("UPDATE clients SET label=? WHERE mac=?",
                      (body.get("label"), mac))
        elif act == "reserve":
            c.execute("UPDATE clients SET reserved_ip=? WHERE mac=?",
                      (body.get("ip"), mac))
        else:
            return jsonify({"error": "unknown action"}), 400
    db.audit(request.remote_addr, f"client.{act}", {"mac": mac})
    return jsonify({"ok": True})
