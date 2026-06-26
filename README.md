# PiBridge

A travel-router appliance for the Raspberry Pi Zero 2 W (Raspberry Pi OS Lite,
64-bit). It turns a fresh OS into a Wi-Fi router managed entirely from a web UI:
dynamic interface discovery, multiple access points, per-AP VPN policy routing,
and — most importantly — a **transactional configuration system that prevents
remote lockouts** by auto-reverting any change you don't confirm in time.

This is a real, installable **foundation (v0.1)**, not a finished commercial
firmware. Read the maturity map below before deploying it anywhere you care
about.

## What works end to end

- **Layered architecture** exactly as specified: API → ConfigManager →
  Validation → Transaction → HAL → services. The UI never edits system files.
- **HAL** (`trouter/hal/`): discovers every NIC from `/sys` + `iw`/`ethtool`,
  assigns each a **stable UUID derived from its MAC**, classifies it, probes
  Wi-Fi capabilities (bands, AP support, virtual-AP limit, channels), and
  reconciles hot-plug events via `pyudev` (with a polling fallback).
- **Transactional apply with auto-rollback** (`trouter/core/transaction.py`):
  snapshot → apply → health-check → arm confirmation deadline → commit or
  auto-revert. This is the anti-lockout core; see `docs/SAFETY.md`.
- **Validation engine**: three-tier findings (block / warn / info) for AP-mode
  support, band/channel/regulatory sanity, virtual-AP ceilings, subnet overlap,
  VPN references.
- **Service generation**: Jinja2 templates render real `hostapd`, `dnsmasq`,
  and `nftables` configs (NAT, inter-AP isolation, per-AP fwmarks).
- **Web UI**: dark, pastel-orange themed dashboard with live auto-refresh,
  SSE-driven interface updates, recommendations cards, and the confirmation
  countdown overlay.
- **APIs**: system status/control, interfaces, APs (+ apply/confirm/rollback),
  clients, VPN profiles, sandboxed file manager, sandboxed script runner.
- **Security**: PBKDF2 password hashing, CSRF tokens, login throttling,
  directory-traversal-proof sandboxes, CSP + security headers.
- **Boot bring-up**: first-boot bootstrap AP + router-mode reconciliation, so
  the box is reachable with zero manual config.

## Maturity map — be honest with yourself

| Subsystem | State | Needs before "production" |
|---|---|---|
| HAL discovery / UUID mapping | Solid | Test against your specific USB dongles |
| Transaction / rollback engine | Solid (logic) | Hardware test: confirm a bad config really reverts the link |
| Validation engine | Solid | Wire live `iw reg get` into regulatory checks |
| hostapd/dnsmasq/nftables generation | Real templates | Tune per chipset; verify `nft -c` passes your ruleset |
| Per-AP VPN policy routing / kill switch | **Foundation only** | Tunnel bring-up + `ip rule`/`ip route` sequencing must be validated on hardware; treat kill switch as best-effort until then |
| Client live stats (bandwidth, signal) | Lease list only | Add `iw dev` station dump + counters |
| Backup/restore, updates UI | Schema + hooks | Implement encrypted bundle export/import |
| HTTPS | Header/flag ready | Provision a cert (self-signed or mkcert) |

## Quick start

```bash
sudo ./install.sh        # installs deps, app, systemd units; prompts for admin pw
# then browse to http://<pi-ip>:8080
```

See `docs/INSTALL.md`, `docs/ARCHITECTURE.md`, `docs/SAFETY.md`,
`docs/EXTENDING.md`.

## Dev box (no Pi)

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
export TROUTER_STATE_DIR=./.state TROUTER_GEN_DIR=./.gen \
       TROUTER_FILES_ROOT=./.files TROUTER_SCRIPTS_ROOT=./.scripts \
       TROUTER_LOG_DIR=./.logs
python -m trouter.run set-admin admin
python -m trouter.run     # http://localhost:8080
```

`systemctl`/`nft`/`iw` calls degrade gracefully when absent, so the UI, HAL DB,
validation, and template generation all work on a laptop.

## License

MIT (see LICENSE). No warranty — this controls networking and runs as root.
