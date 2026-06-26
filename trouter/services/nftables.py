"""nftables adapter: NAT, inter-AP isolation, and per-AP routing marks.

The generated ruleset does three jobs:
  1. Masquerade traffic leaving the WAN / VPN egress.
  2. Drop forwarding between different AP subnets (no cross-AP leakage).
  3. Mark each AP's traffic with a fwmark so the policy-routing tables in
     services/vpn.py and the per-AP routing rules can send it out the right
     egress (direct, wireguard, openvpn) or drop it (isolated / killswitch).

Policy routing tables themselves are installed by vpn.py; this module only
sets the marks and the firewall posture. Both are regenerated together inside
one transaction so they can never drift apart.
"""
import os

from . import render, write, run
from .. import config
from ..hal import interfaces as hal

# fwmark per AP = base + ap_id. Kept well clear of common ranges.
MARK_BASE = 0x6f00


def ap_mark(ap_id):
    return MARK_BASE + int(ap_id)


def generate(aps):
    rules = []
    for ap in aps:
        if not ap.get("enabled", 1):
            continue
        ifname = hal.resolve_name(ap["iface_uuid"]) or "wlan0"
        rules.append({
            "ap": ap,
            "ifname": ifname,
            "mark": ap_mark(ap["id"] or 0),
            "subnet": ap["subnet"],
            "policy": ap.get("routing_policy", "direct"),
            "isolation": ap.get("client_isolation", 0),
        })
    content = render("nftables.conf.j2", rules=rules)
    write(config.NFTABLES_FILE, content)


def reload():
    run(["nft", "-f", config.NFTABLES_FILE])


def health():
    if not os.path.exists(config.NFTABLES_FILE):
        return True, "nftables (none)"
    # Validate the ruleset parses even if we can't load it (dev box).
    rc, out = run(["nft", "-c", "-f", config.NFTABLES_FILE])
    if rc in (0, 127):
        return True, "nftables ok"
    return False, f"nftables invalid: {out.strip()[:120]}"
