#!/usr/bin/env bash
# travelrouter installer — turns a fresh Raspberry Pi OS Lite (64-bit) into the
# appliance. Idempotent: safe to re-run for upgrades.
set -euo pipefail

PREFIX=/opt/travelrouter
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

require_root() { [ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)"; exit 1; }; }

main() {
  require_root
  echo "==> Installing system packages"
  apt-get update
  apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    hostapd dnsmasq nftables iw ethtool iproute2 \
    wireguard-tools openvpn rfkill

  # hostapd/dnsmasq are managed per-AP by us; disable their stock units.
  systemctl unmask hostapd 2>/dev/null || true
  systemctl disable --now hostapd 2>/dev/null || true
  systemctl disable --now dnsmasq 2>/dev/null || true

  echo "==> Installing application to ${PREFIX}"
  mkdir -p "$PREFIX"
  cp -r "$REPO_DIR"/{trouter,templates_system,config,VERSION} "$PREFIX"/
  python3 -m venv "$PREFIX/venv"
  "$PREFIX/venv/bin/pip" install --upgrade pip
  "$PREFIX/venv/bin/pip" install -r "$REPO_DIR/requirements.txt"

  echo "==> Creating sandboxes and state directories"
  mkdir -p /srv/files /home/pi/scripts \
           /var/lib/travelrouter /var/log/travelrouter \
           /etc/travelrouter/generated

  echo "==> Clearing Wi-Fi rfkill block and setting regulatory domain"
  # Fresh Pi OS images soft-block the radio until a country is set; hostapd
  # cannot start an AP while blocked. COUNTRY defaults to US (override below).
  rfkill unblock wifi || true
  rfkill unblock all || true
  iw reg set "${TROUTER_COUNTRY:-US}" 2>/dev/null || true

  echo "==> Installing systemd units"
  cp "$REPO_DIR"/systemd/*.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable travelrouter-boot.service travelrouter.service \
                   travelrouter-dnsmasq.service

  echo "==> Set the admin password"
  "$PREFIX/venv/bin/python" -m trouter.run set-admin admin

  echo "==> Starting services"
  systemctl start travelrouter-boot.service || true
  systemctl restart travelrouter.service

  IP=$(hostname -I | awk '{print $1}')
  cat <<EOF

============================================================
 travelrouter installed.

 Management UI:  http://${IP:-<pi-ip>}:8080
 Username:       admin

 On first boot a starter access point (SSID "TravelRouter")
 is created so you can reach the UI over Wi-Fi. Change its
 SSID/password from the UI immediately.

 Logs:   journalctl -u travelrouter -f
 Docs:   ${REPO_DIR}/docs/
============================================================
EOF
}

main "$@"
