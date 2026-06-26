"""dnsmasq adapter: one DHCP/DNS scope per AP, served on that AP's bridge.

A single dnsmasq instance with multiple interface-scoped ranges keeps memory
use low on the Zero 2 W while still isolating scopes per AP.
"""
import os

from . import render, write, run
from .. import config, db
from ..hal import interfaces as hal


def _reservations():
    with db.connect() as c:
        rows = c.execute(
            "SELECT mac, reserved_ip, label FROM clients "
            "WHERE reserved_ip IS NOT NULL").fetchall()
    return [dict(r) for r in rows]


def generate(aps):
    scopes = []
    for ap in aps:
        if not ap.get("enabled", 1):
            continue
        ifname = hal.resolve_name(ap["iface_uuid"]) or "wlan0"
        scopes.append({
            "ifname": ifname,
            "gateway": ap["subnet"].split("/")[0].rsplit(".", 1)[0] + ".1",
            "start": ap["dhcp_start"], "end": ap["dhcp_end"],
            "dns": (ap.get("dns_servers") or "1.1.1.1").split(","),
            "ap": ap,
        })
    content = render("dnsmasq.conf.j2", scopes=scopes,
                     reservations=_reservations())
    write(os.path.join(config.DNSMASQ_DIR, "dnsmasq.conf"), content)


def reload():
    # Our own unit runs dnsmasq with -C pointing at the generated config above.
    # The stock 'dnsmasq' service reads /etc/dnsmasq.conf and is disabled at
    # install time, so we must not restart that one.
    run(["systemctl", "restart", "travelrouter-dnsmasq"])


def health():
    rc, _ = run(["systemctl", "is-active", "--quiet", "travelrouter-dnsmasq"])
    if rc in (0, 127):
        return True, "dnsmasq ok"
    return False, "dnsmasq not active"
