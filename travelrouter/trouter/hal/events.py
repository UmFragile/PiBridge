"""USB / netdev hotplug watcher.

Runs in a background thread. On any add/remove of a net device it triggers a
HAL re-discovery and pushes an event onto a shared queue that the web layer
exposes over Server-Sent Events, so the UI updates without a refresh.

Falls back to periodic polling if pyudev is unavailable (e.g. dev box).
"""
import threading
import time

from .interfaces import discover

_listeners = []
_lock = threading.Lock()


def subscribe():
    """Return a Queue that receives 'interfaces-changed' events."""
    import queue
    q = queue.Queue(maxsize=16)
    with _lock:
        _listeners.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _listeners:
            _listeners.remove(q)


def _broadcast(event):
    with _lock:
        for q in list(_listeners):
            try:
                q.put_nowait(event)
            except Exception:
                pass


def _udev_loop():
    try:
        import pyudev
    except ImportError:
        return _poll_loop()
    ctx = pyudev.Context()
    mon = pyudev.Monitor.from_netlink(ctx)
    mon.filter_by(subsystem="net")
    for action, _device in mon:
        if action in ("add", "remove", "change"):
            try:
                discover()
            finally:
                _broadcast({"type": "interfaces-changed", "action": action})


def _poll_loop():
    last = None
    while True:
        snap = tuple(sorted(d["uuid"] + str(d["present"])
                            for d in discover()))
        if snap != last:
            _broadcast({"type": "interfaces-changed", "action": "poll"})
            last = snap
        time.sleep(3)


def start():
    t = threading.Thread(target=_udev_loop, name="hal-hotplug", daemon=True)
    t.start()
    return t
