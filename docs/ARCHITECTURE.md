# Architecture

```
Web UI (templates + static)
   │  fetch() / SSE
API blueprints (trouter/api/*)          auth, CSRF, rate-limit at this edge
   │
ConfigManager (core/config_manager.py)  single funnel for changes
   │
ValidationEngine (core/validation.py)   block / warn / info findings
   │
TransactionManager (core/transaction.py) snapshot → apply → health → confirm
   │
Service adapters (services/*)           render templates, reload services
   │
HAL (hal/*)                             the only layer that knows wlan0/eth0
   │
Linux: hostapd, dnsmasq, nftables, ip, sysctl, systemd
```

## Why UUIDs, not interface names
A USB Wi-Fi dongle may appear as `wlan1` today and `wlan2` tomorrow. The HAL
derives a UUID with `uuid5(namespace, mac)`, so the same adapter always maps to
the same identity and its AP bindings survive replug/reboot. Nothing above the
HAL references kernel names; `hal.resolve_name(uuid)` is called only at the
moment of rendering a service config.

## Why every change is a transaction
The single biggest risk in a remotely-managed router is locking yourself out:
you change the channel, the radio resets, your laptop drops, and now you can't
reach the UI to undo it. The TransactionManager makes that recoverable — see
SAFETY.md.

## Extensibility seam
New interface types are added by extending `hal/interfaces.py::_classify` and
`hal/capabilities.py`. New VPN providers implement bring-up in
`services/vpn.py` and a routing policy keyword recognised by the nftables
template + `vpn.reload()`. Core routing logic does not change. See EXTENDING.md.
