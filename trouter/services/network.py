"""Network bring-up: rfkill, regulatory domain, and per-AP interface addressing.

This module fills the gap between hostapd and dnsmasq. hostapd starts the radio
and the BSS, but it does NOT give the wireless interface an IP address. Without
the gateway address on the interface:

  * dnsmasq (configured with ``bind-interfaces``) has nothing to bind to and
    serves no DHCP, and
  * the gateway IP clients are told to use (e.g. 10.42.0.1) does not exist,

so the "AP" appears but is unusable. We assign each enabled AP's gateway
address here and bring the link up. We also clear the rfkill soft-block and set
the regulatory domain — on a Raspberry Pi the radio refuses to start an AP
until a country is set.

All commands go through services.run, which never raises; on a dev box the
tools are simply absent and these become no-ops.
"""
import ipaddress

from . import run
from .. import config
from ..hal import interfaces as hal


def _gateway_cidr(subnet):
    """Return ('10.42.0.1/24', '10.42.0.1') for a subnet like '10.42.0.0/24'."""
    net = ipaddress.ip_network(subnet, strict=False)
    gw = next(net.hosts())
    return f"{gw}/{net.prefixlen}", str(gw)


def unblock_radio():
    """Clear rfkill and set the regulatory domain so the radio will start."""
    run(["rfkill", "unblock", "wifi"])
    run(["rfkill", "unblock", "all"])
    run(["iw", "reg", "set", config.COUNTRY_CODE])


def bring_up(aps):
    """Assign the gateway address and bring up each enabled AP interface."""
    unblock_radio()
    for ap in aps:
        if not ap.get("enabled", 1):
            continue
        ifname = hal.resolve_name(ap["iface_uuid"])
        if not ifname or not ap.get("subnet"):
            continue
        try:
            cidr, _gw = _gateway_cidr(ap["subnet"])
        except ValueError:
            continue
        # Flush first so re-applies don't stack addresses on the interface.
        run(["ip", "addr", "flush", "dev", ifname])
        run(["ip", "addr", "add", cidr, "dev", ifname])
        run(["ip", "link", "set", ifname, "up"])


def health():
    return True, "network ok"
