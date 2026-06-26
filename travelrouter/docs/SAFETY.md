# Safety model (anti-lockout)

Any change that can affect connectivity (access points, routing, firewall) runs
through `core/transaction.py` with this lifecycle:

1. **begin** — acquire the single global change lock, tar the current
   `generated/` config into a snapshot, journal a `staged` row.
2. **apply** — regenerate all service configs, reload services. Any exception
   triggers immediate rollback.
3. **health** — run service health probes (`nft -c`, `systemctl is-active`,
   dnsmasq/hostapd status). A failure triggers immediate rollback.
4. **arm** — set a confirmation deadline (default 90s) and start a watchdog
   timer. The API returns `{txid, deadline}`; the UI shows a countdown.
5. **commit** — the admin clicks "Keep changes" → watchdog cancelled, changes
   kept, lock released.
6. **auto-revert** — if the deadline passes with no commit (because the admin
   got disconnected and can't click anything), the watchdog restores the
   snapshot, reloads services, and releases the lock.

### Rollback triggers
- apply exception (hostapd/dnsmasq/nft failure)
- health-check failure
- user clicks "Revert now"
- confirmation timeout (the lockout case)

### Honest limitations
- The health probe runs **on the Pi**. It can detect that services failed to
  start; it cannot by itself detect "the admin's laptop lost the link." That is
  exactly why the human-confirm deadline is mandatory and non-optional.
- The VPN kill switch and per-AP policy routing are a **foundation**. The
  `ip rule`/`ip route` and tunnel bring-up sequences in `services/vpn.py` must
  be validated on real hardware before you rely on the kill switch to prevent
  leaks. Until then, assume traffic *may* fall back to WAN if a tunnel drops.
- The boot path (`trouter/boot.py`) applies the last committed config **without**
  the watchdog, because there is no session to protect at boot.
