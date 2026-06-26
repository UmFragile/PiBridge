"""System dashboard + control endpoints."""
import os
import platform
import shutil
import time

from flask import Blueprint, jsonify

from . import login_required, mutating
from ..services import run

bp = Blueprint("system", __name__)


def _read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _cpu_temp():
    raw = _read("/sys/class/thermal/thermal_zone0/temp")
    try:
        return round(int(raw) / 1000.0, 1)
    except ValueError:
        return None


def _mem():
    info = {}
    for line in _read("/proc/meminfo").splitlines():
        k, _, v = line.partition(":")
        info[k] = v.strip()
    def kb(key):
        try:
            return int(info.get(key, "0 kB").split()[0])
        except (ValueError, IndexError):
            return 0
    total, avail = kb("MemTotal"), kb("MemAvailable")
    used = total - avail
    return {"total_mb": total // 1024, "used_mb": used // 1024,
            "pct": round(100 * used / total, 1) if total else 0}


@bp.get("/api/system/summary")
@login_required
def summary():
    du = shutil.disk_usage("/")
    load = os.getloadavg()
    return jsonify({
        "uptime_s": int(float(_read("/proc/uptime", "0 0").split()[0])),
        "os": _read("/etc/os-release").splitlines()[0].replace("PRETTY_NAME=", "").strip('"')
              if _read("/etc/os-release") else platform.platform(),
        "kernel": platform.release(),
        "cpu_temp_c": _cpu_temp(),
        "loadavg": [round(x, 2) for x in load],
        "mem": _mem(),
        "disk": {"total_gb": round(du.total / 1e9, 1),
                 "used_gb": round((du.total - du.free) / 1e9, 1),
                 "pct": round(100 * (du.total - du.free) / du.total, 1)},
        "time": int(time.time()),
    })


@bp.post("/api/system/reboot")
@mutating
def reboot():
    run(["systemctl", "reboot"])
    return jsonify({"ok": True})


@bp.post("/api/system/shutdown")
@mutating
def shutdown():
    run(["systemctl", "poweroff"])
    return jsonify({"ok": True})


@bp.post("/api/system/restart-networking")
@mutating
def restart_net():
    for svc in ("dnsmasq", "nftables"):
        run(["systemctl", "restart", svc])
    return jsonify({"ok": True})
