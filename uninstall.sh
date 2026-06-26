#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
systemctl disable --now travelrouter.service travelrouter-boot.service 2>/dev/null || true
rm -f /etc/systemd/system/travelrouter*.service /etc/systemd/system/hostapd@.service
systemctl daemon-reload
rm -rf /opt/travelrouter /etc/travelrouter
echo "Removed app. Left /var/lib/travelrouter (state), /srv/files and /home/pi/scripts intact."
echo "Delete them manually if you want a full wipe."
