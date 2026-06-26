"""Validation engine.

Given a proposed set of access points (the staged config), produce a list of
findings before anything is written. Findings are classified so the UI can
block, warn, or merely inform — matching the spec's three-tier model.

    BLOCK  -> configuration is rejected
    WARN   -> risky but allowed if the user insists
    INFO   -> performance/quality note only
"""
import ipaddress

from ..hal import interfaces as hal

BLOCK, WARN, INFO = "block", "warn", "info"


class Finding:
    def __init__(self, level, code, message):
        self.level = level
        self.code = code
        self.message = message

    def as_dict(self):
        return {"level": self.level, "code": self.code, "message": self.message}


def _net(ap):
    try:
        return ipaddress.ip_network(ap["subnet"], strict=False)
    except (KeyError, ValueError):
        return None


def validate(aps):
    """aps: list of dicts (proposed access_points rows). Returns [Finding]."""
    findings = []
    ifaces = {d["uuid"]: d for d in hal.list_interfaces()}

    # --- per-AP checks --------------------------------------------------
    vif_count = {}
    for ap in aps:
        if not ap.get("enabled", 1):
            continue
        u = ap.get("iface_uuid")
        dev = ifaces.get(u)
        if dev is None:
            findings.append(Finding(BLOCK, "iface_unknown",
                f"AP '{ap['name']}' references an unknown interface."))
            continue
        if not dev["present"]:
            findings.append(Finding(BLOCK, "iface_absent",
                f"AP '{ap['name']}' needs interface {dev['last_name']} "
                "which is not currently plugged in."))
        cap = dev.get("capabilities") or {}
        if dev["kind"].startswith("wifi") and cap.get("ap_supported") is False:
            findings.append(Finding(BLOCK, "no_ap_mode",
                f"{dev['last_name']} ({dev.get('driver')}) does not support "
                "AP mode."))
        band = str(ap.get("band", "2.4"))
        if band == "5" and "5" not in (cap.get("bands") or ["2.4"]):
            findings.append(Finding(BLOCK, "band_unsupported",
                f"AP '{ap['name']}' requests 5 GHz but {dev['last_name']} "
                "is 2.4 GHz only."))
        # SSID / PSK sanity.
        if not ap.get("ssid"):
            findings.append(Finding(BLOCK, "ssid_empty",
                f"AP '{ap['name']}' has an empty SSID."))
        psk = ap.get("psk") or ""
        if psk and not (8 <= len(psk) <= 63):
            findings.append(Finding(BLOCK, "psk_length",
                f"AP '{ap['name']}' WPA2 passphrase must be 8–63 characters."))
        if not psk:
            findings.append(Finding(WARN, "open_network",
                f"AP '{ap['name']}' is open (no encryption)."))
        vif_count[u] = vif_count.get(u, 0) + 1

    # --- virtual-AP ceiling per radio ----------------------------------
    for u, n in vif_count.items():
        cap = (ifaces.get(u) or {}).get("capabilities") or {}
        maxv = cap.get("max_vifs", 1)
        if n > maxv:
            findings.append(Finding(BLOCK, "vif_limit",
                f"Interface {ifaces[u]['last_name']} supports {maxv} AP(s) "
                f"but {n} are assigned to it."))

    # --- channel conflict on the same radio ----------------------------
    chan_by_iface = {}
    for ap in aps:
        if not ap.get("enabled", 1):
            continue
        chan_by_iface.setdefault(ap["iface_uuid"], set()).add(ap.get("channel"))
    for u, chans in chan_by_iface.items():
        if len([c for c in chans if c is not None]) > 1:
            findings.append(Finding(WARN, "channel_split",
                f"Multiple channels requested on one radio "
                f"({ifaces.get(u, {}).get('last_name','?')}); a single radio "
                "can only be on one channel at a time."))

    # --- subnet overlap across APs -------------------------------------
    nets = [(ap["name"], _net(ap)) for ap in aps if ap.get("enabled", 1)]
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            a, b = nets[i][1], nets[j][1]
            if a and b and a.overlaps(b):
                findings.append(Finding(BLOCK, "subnet_overlap",
                    f"AP '{nets[i][0]}' and '{nets[j][0]}' have overlapping "
                    f"subnets ({a} / {b})."))

    # --- VPN policy references -----------------------------------------
    for ap in aps:
        if ap.get("routing_policy") in ("wireguard", "openvpn") and not ap.get("vpn_id"):
            findings.append(Finding(BLOCK, "vpn_missing",
                f"AP '{ap['name']}' uses a VPN policy but no tunnel is selected."))

    return findings


def has_blocking(findings):
    return any(f.level == BLOCK for f in findings)
