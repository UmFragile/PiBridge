"""Smart recommendations — informational, dismissible, never enforced.

Looks at the current hardware + AP layout and emits advisory cards. Nothing
here mutates state; the UI decides whether to show or dismiss each item.
"""
from ..hal import interfaces as hal
from . import config_manager


def recommendations():
    out = []
    ifaces = [d for d in hal.list_interfaces() if d["present"]]
    wifi = [d for d in ifaces if d["kind"].startswith("wifi")]
    aps = config_manager.current_aps()

    if len(wifi) <= 1:
        out.append({
            "id": "single-radio",
            "level": "info",
            "title": "Only one Wi-Fi radio detected",
            "body": "With a single radio the Pi must share it between uplink "
                    "and your AP, which limits throughput. A USB Wi-Fi adapter "
                    "lets you dedicate one radio to WAN and one to the AP.",
        })
    elif len(wifi) >= 2 and not any(d["role"] == "wan" for d in wifi):
        out.append({
            "id": "split-roles",
            "level": "info",
            "title": "Split WAN and AP across radios",
            "body": "You have multiple radios. Assigning one as the upstream "
                    "(WAN) client and others as APs improves stability.",
        })

    if any(d["kind"] == "wifi_usb" for d in ifaces):
        out.append({
            "id": "usb-adapter",
            "level": "info",
            "title": "USB Wi-Fi adapter available",
            "body": "Consider dedicating the USB adapter to your access point "
                    "and keeping the onboard radio for the uplink.",
        })

    if len(aps) >= 2 and not any(a.get("routing_policy") != "direct" for a in aps):
        out.append({
            "id": "per-ap-vpn",
            "level": "info",
            "title": "Assign VPN policies per AP",
            "body": "You have several APs. You can route one through a VPN "
                    "tunnel while another goes direct — useful for separating "
                    "trusted and guest traffic.",
        })

    return out
