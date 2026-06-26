"""hostapd adapter: one config file + one systemd instance per AP.

We use a templated systemd instance (hostapd@<ap>.service) so multiple APs run
as independent units and a single AP failing doesn't take the others down.
"""
import glob
import os
import time

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


def _desired_units():
    units = set()
    for f in glob.glob(os.path.join(config.HOSTAPD_DIR, "ap*.conf")):
        units.add("hostapd@" + os.path.basename(f)[:-5] + ".service")
    return units


def _running_units():
    rc, out = run(["systemctl", "list-units", "--all", "--no-legend",
                   "--plain", "hostapd@*.service"])
    units = set()
    for line in (out or "").splitlines():
        parts = line.split()
        if parts and parts[0].startswith("hostapd@"):
            units.add(parts[0])
    return units


def reload():
    desired = _desired_units()
    # Stop + disable any AP unit that no longer has a config. Without this, a
    # unit started for an AP that later vanished (e.g. a rolled-back apply that
    # deleted the conf) keeps looping on "could not open configuration file".
    for unit in _running_units() - desired:
        run(["systemctl", "stop", unit])
        run(["systemctl", "disable", unit])
    for unit in desired:
        run(["systemctl", "enable", unit])
        run(["systemctl", "restart", unit])


def health():
    # Absence of units = no APs, which is fine.
    desired = _desired_units()
    if not desired:
        return True, "hostapd (no APs)"
    # hostapd needs a second or two to bring up the BSS; polling avoids a race
    # where is-active is checked before startup completes and we wrongly fail.
    deadline = time.time() + 8
    pending = set(desired)
    while pending and time.time() < deadline:
        still = set()
        for unit in pending:
            rc, _ = run(["systemctl", "is-active", "--quiet", unit])
            if rc == 127:          # systemctl absent (dev box) -> treat as ok
                continue
            if rc != 0:
                still.add(unit)
        pending = still
        if pending:
            time.sleep(1)
    if pending:
        return False, ", ".join(sorted(pending)) + " not active"
    return True, "hostapd ok"
