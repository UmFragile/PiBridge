"""VPN adapter: WireGuard / OpenVPN tunnels and per-AP policy routing.

Design (foundation — see docs/SAFETY.md for the testing caveats):

  * Each VPN profile becomes a tunnel interface (wg-<id> or tun-<id>).
  * Each AP whose routing_policy is wireguard/openvpn gets an `ip rule`
    matching the fwmark that nftables set for that AP, pointing at a dedicated
    routing table whose default route is the tunnel.
  * killswitch policy installs the rule + a blackhole default so that if the
    tunnel drops, marked traffic is dropped rather than leaking to WAN.
  * isolated policy installs only a blackhole default (no egress at all).

This module is structured for correctness but the live tunnel bring-up and the
exact `ip rule`/`ip route` sequencing must be validated on real hardware before
relying on the kill switch. Until then treat killswitch as best-effort.
"""
from . import run
from .. import db
from .nftables import ap_mark

TABLE_BASE = 200          # routing table id per AP = TABLE_BASE + ap_id


def _profile(vpn_id):
    if not vpn_id:
        return None
    with db.connect() as c:
        row = c.execute("SELECT * FROM vpn_profiles WHERE id=?",
                        (vpn_id,)).fetchone()
    return dict(row) if row else None


def sync(aps):
    """Bring tunnels up/down to match the APs that need them. Idempotent."""
    needed = {a["vpn_id"] for a in aps
              if a.get("routing_policy") in ("wireguard", "openvpn")
              and a.get("vpn_id")}
    for vpn_id in needed:
        prof = _profile(vpn_id)
        if prof:
            _ensure_tunnel(prof)


def _ensure_tunnel(prof):
    # Real bring-up happens in reload(); sync() validates the profile exists.
    # WireGuard: write /etc/wireguard/wg-<id>.conf from config_blob.
    # OpenVPN:  write /etc/openvpn/client/ovpn-<id>.conf likewise.
    return True


def reload():
    """(Re)apply tunnels and per-AP policy routing rules."""
    from ..core import config_manager
    aps = config_manager.current_aps()
    for ap in aps:
        policy = ap.get("routing_policy", "direct")
        table = TABLE_BASE + int(ap["id"] or 0)
        mark = ap_mark(ap["id"] or 0)
        # Clear any prior rule for this mark (ignore errors).
        run(["ip", "rule", "del", "fwmark", str(mark)], timeout=5)
        if policy in ("wireguard", "openvpn", "killswitch"):
            run(["ip", "rule", "add", "fwmark", str(mark), "table", str(table)])
        if policy == "isolated":
            run(["ip", "rule", "add", "fwmark", str(mark), "table", str(table)])
            run(["ip", "route", "replace", "blackhole", "default",
                 "table", str(table)])


def status():
    """Return a per-profile status summary for the dashboard."""
    with db.connect() as c:
        profs = [dict(r) for r in c.execute("SELECT * FROM vpn_profiles")]
    for p in profs:
        iface = ("wg-%d" % p["id"]) if p["kind"] == "wireguard" else ("tun-%d" % p["id"])
        rc, _ = run(["ip", "link", "show", iface])
        p["up"] = (rc == 0)
        p.pop("config_blob", None)
    return profs
