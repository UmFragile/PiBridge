"""Configuration manager.

The single funnel between the API and the rest of the system. The API stages a
desired set of access points here; this module validates them, and (if the
caller asks to apply) drives a Transaction that regenerates every service
config and reloads the services behind a confirmation deadline.
"""
import time

from .. import db
from . import validation, transaction
from ..services import hostapd, dnsmasq, nftables, vpn, sysctl


def current_aps():
    with db.connect() as c:
        rows = c.execute("SELECT * FROM access_points ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def validate(aps):
    findings = validation.validate(aps)
    return [f.as_dict() for f in findings], validation.has_blocking(findings)


def _generate_all(aps):
    """Render every service config from the staged AP set. Pure file output."""
    hostapd.generate(aps)
    dnsmasq.generate(aps)
    nftables.generate(aps)
    sysctl.apply()        # idempotent; writes /etc/sysctl.d + sysctl --system
    vpn.sync(aps)


def _reload_services():
    hostapd.reload()
    dnsmasq.reload()
    nftables.reload()
    vpn.reload()


def _health():
    checks = [
        nftables.health(),
        dnsmasq.health(),
        hostapd.health(),
    ]
    failed = [d for ok, d in checks if not ok]
    return (len(failed) == 0, "; ".join(failed) if failed else "ok")


def apply_aps(aps, actor="admin", require_confirm=True):
    """Validate, then transactionally apply. Returns a dict the API hands back.

    On success with require_confirm the transaction is *armed*: the caller must
    POST a commit before the deadline or everything reverts.
    """
    findings, blocking = validate(aps)
    if blocking:
        return {"ok": False, "findings": findings, "blocked": True}

    # Persist the staged set first so a successful apply is durable, but keep
    # the previous rows recoverable through the snapshot.
    _persist_aps(aps)

    tx = transaction.Transaction(
        summary=f"apply {len(aps)} access point(s)",
        reload_fn=_reload_services,
        health_fn=_health,
    ).begin()
    try:
        tx.apply(lambda: _generate_all(aps))
        tx.health()
    except transaction.TransactionError as e:
        return {"ok": False, "error": str(e), "rolledback": True,
                "findings": findings}

    if require_confirm:
        deadline = tx.arm()
        return {"ok": True, "txid": tx.id, "deadline": deadline,
                "confirm_required": True, "findings": findings}
    tx.commit()
    return {"ok": True, "txid": tx.id, "confirm_required": False,
            "findings": findings}


def confirm(txid):
    tx_row = transaction.get(txid)
    if not tx_row or tx_row["state"] != "applied":
        return {"ok": False, "error": "no armed transaction with that id"}
    # Rebuild a lightweight Transaction shell to commit.
    shell = transaction.Transaction("confirm", _reload_services, _health)
    shell.id = txid
    shell.snapshot = tx_row["snapshot"]
    shell.commit()
    return {"ok": True}


def rollback(txid, reason="manual"):
    tx_row = transaction.get(txid)
    if not tx_row:
        return {"ok": False, "error": "unknown transaction"}
    shell = transaction.Transaction("rollback", _reload_services, _health)
    shell.id = txid
    shell.snapshot = tx_row["snapshot"]
    shell.rollback(reason)
    return {"ok": True}


def _persist_aps(aps):
    now = int(time.time())
    with db.connect() as c:
        for ap in aps:
            if ap.get("id"):
                c.execute(
                    "UPDATE access_points SET name=?, iface_uuid=?, ssid=?, psk=?,"
                    " band=?, channel=?, hidden=?, client_isolation=?, max_clients=?,"
                    " subnet=?, dhcp_start=?, dhcp_end=?, dns_servers=?,"
                    " routing_policy=?, vpn_id=?, enabled=?, schedule=? WHERE id=?",
                    (ap["name"], ap["iface_uuid"], ap["ssid"], ap.get("psk"),
                     ap.get("band", "2.4"), ap.get("channel", 6),
                     ap.get("hidden", 0), ap.get("client_isolation", 0),
                     ap.get("max_clients", 32), ap.get("subnet"),
                     ap.get("dhcp_start"), ap.get("dhcp_end"),
                     ap.get("dns_servers"), ap.get("routing_policy", "direct"),
                     ap.get("vpn_id"), ap.get("enabled", 1),
                     ap.get("schedule"), ap["id"]),
                )
            else:
                c.execute(
                    "INSERT INTO access_points(name, iface_uuid, ssid, psk, band,"
                    " channel, hidden, client_isolation, max_clients, subnet,"
                    " dhcp_start, dhcp_end, dns_servers, routing_policy, vpn_id,"
                    " enabled, schedule, created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ap["name"], ap["iface_uuid"], ap["ssid"], ap.get("psk"),
                     ap.get("band", "2.4"), ap.get("channel", 6),
                     ap.get("hidden", 0), ap.get("client_isolation", 0),
                     ap.get("max_clients", 32), ap.get("subnet"),
                     ap.get("dhcp_start"), ap.get("dhcp_end"),
                     ap.get("dns_servers"), ap.get("routing_policy", "direct"),
                     ap.get("vpn_id"), ap.get("enabled", 1),
                     ap.get("schedule"), now),
                )
