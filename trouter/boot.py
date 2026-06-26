"""Boot-time reconciliation — runs once per boot before the web service.

Responsibilities:
  * initialise the DB and directories,
  * run HAL discovery so interface UUIDs are fresh,
  * apply sysctl (forwarding + TTL/hop-limit),
  * on first boot only, create the bootstrap AP from config/default.yaml so the
    appliance is reachable over Wi-Fi immediately with no manual setup,
  * regenerate every service config from the stored APs and reload, bringing
    the box up in router mode.

Boot reconciliation deliberately does NOT use the confirmation watchdog: there
is no admin session to lock out at boot, and the goal is to converge to the
last committed configuration.
"""
import sys

from . import db, config
from .hal import interfaces as hal
from .core import config_manager
from .services import sysctl


def _load_yaml(path):
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _first_boot():
    with db.connect() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM access_points").fetchone()["n"]
    return n == 0


def _create_bootstrap_ap():
    cfg = _load_yaml(config.DEFAULT_CONFIG).get("bootstrap_ap")
    if not cfg:
        return
    # Pick the first present, AP-capable wireless interface.
    target = None
    for d in hal.list_interfaces():
        if d["present"] and d["kind"].startswith("wifi") and \
           (d["capabilities"].get("ap_supported", True)):
            target = d
            break
    if not target:
        print("boot: no AP-capable wireless interface found; skipping bootstrap AP")
        return
    ap = dict(cfg)
    ap["iface_uuid"] = target["uuid"]
    ap["enabled"] = 1
    config_manager._persist_aps([ap])
    print(f"boot: created bootstrap AP '{ap['ssid']}' on {target['last_name']}")


def main():
    db.init_db()
    config.ensure_dirs()
    hal.discover()
    sysctl.apply()

    if _first_boot():
        _create_bootstrap_ap()

    aps = config_manager.current_aps()
    if aps:
        # Apply without the confirmation watchdog (no session to protect).
        res = config_manager.apply_aps(aps, actor="boot", require_confirm=False)
        print(f"boot: router mode {'up' if res.get('ok') else 'FAILED'}: {res}")
    else:
        print("boot: no access points configured yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
