"""hostapd adapter: one config file + one systemd instance per AP.

We use a templated systemd instance (hostapd@<ap>.service) so multiple APs run
as independent units and a single AP failing doesn't take the others down.
"""
import glob
import os

from . import render, write, run
from .. import config
from ..hal import interfaces as hal


def _conf_path(ap_id):
    return os.path.join(config.HOSTAPD_DIR, f"ap{ap_id}.conf")


def generate(aps):
    # Clear stale configs.
    for f in glob.glob(os.path.join(config.HOSTAPD_DIR, "ap*.conf")):
        os.remove(f)
    for ap in aps:
        if not ap.get("enabled", 1):
            continue
        ifname = hal.resolve_name(ap["iface_uuid"]) or "wlan0"
        content = render("hostapd.conf.j2", ap=ap, ifname=ifname,
                         country=config.COUNTRY_CODE)
        write(_conf_path(ap["id"] or ap["ssid"]), content)


def reload():
    # Reload each AP instance. On a real Pi these are hostapd@apN units.
    for f in glob.glob(os.path.join(config.HOSTAPD_DIR, "ap*.conf")):
        unit = "hostapd@" + os.path.basename(f)[:-5]
        run(["systemctl", "restart", unit])


def health():
    # Healthy if every generated AP unit is active. Absence of units = no APs,
    # which is also fine.
    for f in glob.glob(os.path.join(config.HOSTAPD_DIR, "ap*.conf")):
        unit = "hostapd@" + os.path.basename(f)[:-5]
        rc, _ = run(["systemctl", "is-active", "--quiet", unit])
        if rc not in (0, 127):     # 127 = systemctl absent (dev box)
            return False, f"{unit} not active"
    return True, "hostapd ok"
