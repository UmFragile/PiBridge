"""Per-AP interface pre-start helper, invoked by hostapd@<inst>.service.

hostapd can only bring up an AP if it can put the radio into master mode. On a
fresh Raspberry Pi OS image several things routinely prevent that, and each one
makes hostapd exit immediately and the unit crash-loop:

  * the Wi-Fi radio is rfkill **soft-blocked** until a country is configured;
  * the regulatory domain is unset, so the radio refuses to start a BSS;
  * ``wpa_supplicant`` is already using the interface as a **station** (this is
    the usual case when you reach the Pi over its onboard Wi-Fi), and two
    masters cannot own one netdev;
  * ``dhcpcd`` is holding an address/route on the interface.

This helper runs as ``ExecStartPre`` so it executes on *every* (re)start of the
hostapd instance, clearing all four conditions for the one interface that AP
will use. It reads the interface name straight out of the generated conf so it
stays correct no matter which radio the AP was bound to.

Usage:  python -m trouter.apctl prestart ap1
"""
import os
import subprocess
import sys

from . import config


def _run(cmd):
    """Best-effort; never raise. A missing tool or absent process is fine."""
    try:
        subprocess.run(cmd, check=False, capture_output=True, timeout=10)
    except Exception:
        pass


def _iface_from_conf(inst):
    path = os.path.join(config.HOSTAPD_DIR, f"{inst}.conf")
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("interface="):
                    return line.strip().split("=", 1)[1] or None
    except OSError:
        return None
    return None


def prestart(inst):
    # 1. Make the radio legal to use at all.
    _run(["rfkill", "unblock", "wifi"])
    _run(["rfkill", "unblock", "all"])
    _run(["iw", "reg", "set", config.COUNTRY_CODE])

    iface = _iface_from_conf(inst)
    if not iface:
        # No interface line means a malformed/empty conf — let hostapd fail
        # loudly rather than masking it here.
        return 0

    # 2. Evict any station-mode manager from this specific interface. We do NOT
    #    stop wpa_supplicant globally: an upstream Wi-Fi *client* link may live
    #    on a different radio and must survive.
    _run(["wpa_cli", "-i", iface, "terminate"])
    _run(["pkill", "-f", f"wpa_supplicant.*-i ?{iface}"])
    _run(["dhcpcd", "-k", iface])

    # 3. Clear stale addressing and hand a clean, downed link to hostapd, which
    #    will set master mode and bring it up itself.
    _run(["ip", "addr", "flush", "dev", iface])
    _run(["ip", "link", "set", iface, "down"])
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "prestart":
        sys.exit(prestart(sys.argv[2]))
    sys.exit(0)
