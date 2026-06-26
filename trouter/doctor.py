"""Diagnostic dump — answers "why is there no AP?" without guesswork.

Run on the Pi:

    sudo /opt/travelrouter/venv/bin/python -m trouter.doctor

It prints what the HAL detected, which radios are AP-capable, what APs are
persisted, and whether the hostapd configs actually generate — pinpointing
whether a missing conf is a detection, persistence, or generation problem.
"""
import json
import os
import sys
import traceback

from . import config, db
from .hal import interfaces as hal
from .hal import capabilities as caps
from .services import hostapd


def _line(c="-"):
    print(c * 60)


def main():
    db.init_db()
    config.ensure_dirs()

    print("travelrouter doctor")
    _line("=")
    print(f"country_code     : {config.COUNTRY_CODE}")
    print(f"hostapd dir      : {config.HOSTAPD_DIR}")
    print(f"db               : {config.DB_PATH}")
    _line()

    # 1. Raw kernel interfaces, before any DB reconciliation.
    print("KERNEL INTERFACES (iw/sysfs):")
    try:
        for name in hal._kernel_interfaces():
            wl = caps.is_wireless(name)
            usb = caps.is_usb(name)
            phy = caps.phy_of(name) if wl else None
            cap = caps.wifi_capabilities(phy) if (wl and phy is not None) else {}
            apcap = cap.get("ap_supported")
            print(f"  {name:8} wireless={wl} usb={usb} phy={phy} "
                  f"ap_supported={apcap} bands={cap.get('bands')}")
    except Exception:
        print("  ERROR enumerating kernel interfaces:")
        traceback.print_exc()
    _line()

    # 2. HAL discovery result (what the DB now believes).
    print("HAL DISCOVER -> DB:")
    try:
        hal.discover()
        for d in hal.list_interfaces():
            print(f"  {d['last_name']:8} kind={d['kind']:9} present={d['present']} "
                  f"ap_supported={d['capabilities'].get('ap_supported')} "
                  f"usb={d['capabilities'].get('usb')} uuid={d['uuid'][:8]}")
    except Exception:
        print("  ERROR during discover:")
        traceback.print_exc()
    _line()

    # 3. Which radio the bootstrap logic would choose.
    try:
        from .boot import _pick_ap_iface
        pick = _pick_ap_iface(prefer_usb=True)
        print(f"BOOTSTRAP would bind AP to: "
              f"{pick['last_name'] if pick else 'NONE — no AP-capable radio found'}")
    except Exception:
        print("BOOTSTRAP pick ERROR:")
        traceback.print_exc()
    _line()

    # 4. Persisted APs.
    from .core import config_manager
    aps = config_manager.current_aps()
    print(f"PERSISTED APs: {len(aps)}")
    for ap in aps:
        ifname = hal.resolve_name(ap["iface_uuid"])
        print(f"  id={ap['id']} ssid={ap['ssid']!r} enabled={ap['enabled']} "
              f"iface_uuid={ap['iface_uuid'][:8]} -> resolves to {ifname!r}")
    _line()

    # 5. Dry-run generation and report any exception.
    print("GENERATE (dry run):")
    try:
        hostapd.generate(aps)
        confs = sorted(os.listdir(config.HOSTAPD_DIR)) if os.path.isdir(config.HOSTAPD_DIR) else []
        print(f"  hostapd dir now contains: {confs or '(empty)'}")
        if not confs and aps:
            print("  -> APs exist but no conf written. Likely all APs disabled, "
                  "or iface_uuid does not resolve to a present interface.")
        if not aps:
            print("  -> No APs persisted, so nothing to generate. The bootstrap "
                  "AP was never created (see BOOTSTRAP line above).")
    except Exception:
        print("  ERROR during generate:")
        traceback.print_exc()
    _line("=")
    print("Send this entire output back for diagnosis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
