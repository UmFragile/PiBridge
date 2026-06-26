"""sysctl adapter: forwarding + the TTL/hop-limit settings from the spec."""
from . import write, run
from .. import config

SYSCTL_CONTENT = """\
# Managed by travelrouter — do not edit by hand.
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv4.ip_default_ttl = 65
net.ipv6.conf.all.hop_limit = 65
"""


def apply():
    write(config.SYSCTL_FILE, SYSCTL_CONTENT)
    run(["sysctl", "--system"])


def health():
    return True, "sysctl ok"
