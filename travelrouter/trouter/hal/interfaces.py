"""Interface discovery and stable-UUID mapping.

Discovery walks /sys/class/net, classifies each device, and reconciles it with
the `interfaces` table keyed by MAC. A NIC's UUID is derived deterministically
from its MAC so the same dongle always resolves to the same identity — that is
what lets per-AP config survive a replug or a kernel renaming wlan1 -> wlan2.
"""
import json
import os
import time
import uuid as _uuid

from .. import db
from . import capabilities as caps

# Stable namespace so uuid5(MAC) is reproducible across installs.
_NS = _uuid.UUID("6f6e1b1e-0000-4000-8000-72747200beef")


def uuid_for_mac(mac):
    return str(_uuid.uuid5(_NS, mac.lower()))


def _mac_of(name):
    try:
        with open(f"/sys/class/net/{name}/address") as f:
            mac = f.read().strip()
        return mac if mac and mac != "00:00:00:00:00:00" else None
    except OSError:
        return None


def _classify(name):
    wireless = caps.is_wireless(name)
    usb = caps.is_usb(name)
    if wireless and usb:
        return "wifi_usb"
    if wireless:
        return "wifi_builtin"
    if usb and name.startswith(("eth", "enx", "usb")):
        return "eth_usb"
    if name.startswith(("wwan", "ww")):
        return "modem"
    if name.startswith("eth") or name.startswith("en"):
        return "eth"
    return "generic"


def _kernel_interfaces():
    """All real (non-loopback, non-virtual) interfaces present right now."""
    result = []
    for name in sorted(os.listdir("/sys/class/net")):
        if name == "lo":
            continue
        # Skip our own bridges/veths created by the AP layer.
        if name.startswith(("br-", "veth", "wg", "tun", "tap")):
            continue
        if not os.path.exists(f"/sys/class/net/{name}/device"):
            # No backing device (e.g. dummy). Still allow real wireless soft-mac.
            if not caps.is_wireless(name):
                continue
        result.append(name)
    return result


def probe(name):
    """Build a fresh descriptor for one kernel interface."""
    mac = _mac_of(name)
    if not mac:
        return None
    kind = _classify(name)
    phy = caps.phy_of(name)
    cap = caps.wifi_capabilities(phy) if kind.startswith("wifi") else {}
    cap["link_speed"] = caps.link_speed(name)
    cap["usb"] = caps.is_usb(name)
    return {
        "uuid": uuid_for_mac(mac),
        "mac": mac,
        "kind": kind,
        "last_name": name,
        "driver": caps.driver_of(name),
        "phy": phy,
        "capabilities": cap,
    }


def discover():
    """Reconcile live hardware with the DB. Returns list of descriptor dicts.

    Marks vanished interfaces present=0 but never deletes them, so their AP
    bindings survive an unplug.
    """
    now = int(time.time())
    live = {}
    for name in _kernel_interfaces():
        d = probe(name)
        if d:
            live[d["uuid"]] = d

    with db.connect() as c:
        known = {r["uuid"]: r for r in c.execute("SELECT * FROM interfaces")}
        for u, d in live.items():
            if u in known:
                c.execute(
                    "UPDATE interfaces SET mac=?, kind=?, last_name=?, driver=?, "
                    "phy=?, capabilities=?, last_seen=?, present=1 WHERE uuid=?",
                    (d["mac"], d["kind"], d["last_name"], d["driver"], d["phy"],
                     json.dumps(d["capabilities"]), now, u),
                )
            else:
                c.execute(
                    "INSERT INTO interfaces(uuid, mac, kind, last_name, driver, "
                    "phy, capabilities, role, first_seen, last_seen, present) "
                    "VALUES(?,?,?,?,?,?,?, 'unused', ?, ?, 1)",
                    (u, d["mac"], d["kind"], d["last_name"], d["driver"],
                     d["phy"], json.dumps(d["capabilities"]), now, now),
                )
        for u in known:
            if u not in live:
                c.execute("UPDATE interfaces SET present=0 WHERE uuid=?", (u,))

    return list_interfaces()


def list_interfaces():
    with db.connect() as c:
        rows = c.execute("SELECT * FROM interfaces ORDER BY present DESC, kind").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["capabilities"] = json.loads(d["capabilities"] or "{}")
        except json.JSONDecodeError:
            d["capabilities"] = {}
        out.append(d)
    return out


def resolve_name(uuid):
    """UUID -> current kernel name, or None if the NIC is absent."""
    for d in list_interfaces():
        if d["uuid"] == uuid and d["present"]:
            return d["last_name"]
    return None
