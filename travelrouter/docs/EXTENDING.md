# Extending the appliance

## Add a new interface type
1. Teach the classifier: extend `hal/interfaces.py::_classify`.
2. Add capability probing in `hal/capabilities.py` if the type has special
   attributes (e.g. an LTE modem's bands/IMEI).
That's it — discovery, persistence, UUID mapping, and the UI list pick it up.

## Add a new VPN provider / routing policy
1. Store the provider config as a `vpn_profiles` row (`kind` = your keyword).
2. Implement bring-up/teardown in `services/vpn.py` (`_ensure_tunnel`,
   `reload`).
3. Recognise the policy keyword in `templates_system/nftables.conf.j2` (it just
   needs the AP's fwmark set) and in `vpn.reload()`'s `ip rule` handling.
Core routing logic in ConfigManager/Transaction does **not** change — policies
are data, not code branches in the core.

## Add a dashboard panel
Add a `views.<name>` function in `web/static/js/app.js` and a nav link in
`dashboard.html`. Back it with a new blueprint under `trouter/api/` registered
in `app.py`.

## Captive portal / mesh (future)
Both fit the same seam: a captive portal is an nftables redirect rule keyed on
the AP's fwmark plus a tiny auth endpoint; mesh is a new interface role plus a
routing policy. Neither requires touching the transaction core.
