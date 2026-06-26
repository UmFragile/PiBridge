"""Capability probing for network interfaces.

Parses `iw`, `iw list`, and `ethtool` output to learn what a NIC can actually
do. All parsing is defensive: if a tool is missing or output is unexpected we
return conservative defaults rather than raising, because the appliance must
keep running on whatever odd USB dongle the user plugged in.
"""
import re
import subprocess


def _run(args, timeout=5):
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=timeout)
        return out.stdout if out.returncode == 0 else ""
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def driver_of(name):
    """Best-effort driver name via /sys."""
    try:
        import os
        link = os.readlink(f"/sys/class/net/{name}/device/driver")
        return link.rsplit("/", 1)[-1]
    except OSError:
        return None


def phy_of(name):
    """Return the phyN backing a wireless interface, if any."""
    try:
        with open(f"/sys/class/net/{name}/phy80211/name") as f:
            return f.read().strip()
    except OSError:
        return None


def is_wireless(name):
    import os
    return os.path.isdir(f"/sys/class/net/{name}/wireless") or \
        phy_of(name) is not None


def is_usb(name):
    """True if the device sits on the USB bus."""
    import os
    try:
        path = os.path.realpath(f"/sys/class/net/{name}/device")
        return "/usb" in path
    except OSError:
        return False


def wifi_capabilities(phy):
    """Probe a phy via `iw phy <phy> info`. Returns a capability dict."""
    caps = {
        "bands": [], "standards": [], "max_vifs": 1,
        "ap_supported": False, "monitor": False, "channels": [],
    }
    if not phy:
        return caps
    out = _run(["iw", "phy", phy, "info"])
    if not out:
        return caps
    if re.search(r"Band 1:", out):
        caps["bands"].append("2.4")
    if re.search(r"Band 2:", out):
        caps["bands"].append("5")
    if "VHT" in out:
        caps["standards"].append("ac")
    if "HE" in out:
        caps["standards"].append("ax")
    if "HT20" in out or "HT40" in out:
        caps["standards"].append("n")
    caps["ap_supported"] = "* AP" in out
    caps["monitor"] = "* monitor" in out
    # "valid interface combinations" gives the real virtual-AP ceiling.
    m = re.search(r"#\{ AP.*?\} <= (\d+)", out)
    if m:
        caps["max_vifs"] = int(m.group(1))
    # Channels (frequency lines like "* 2412 MHz [1]").
    for freq, ch in re.findall(r"\* (\d+) MHz \[(\d+)\]", out):
        if "(disabled)" not in out.split(f"[{ch}]")[0][-40:]:
            caps["channels"].append(int(ch))
    return caps


def link_speed(name):
    out = _run(["ethtool", name])
    m = re.search(r"Speed:\s*([0-9]+)Mb/s", out)
    return int(m.group(1)) if m else None
