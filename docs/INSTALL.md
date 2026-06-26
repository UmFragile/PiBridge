# Installation

## Requirements
- Raspberry Pi Zero 2 W
- Raspberry Pi OS Lite (64-bit), freshly flashed, with SSH enabled
- Internet for the first install (to fetch apt + pip packages)

## Steps
```bash
git clone <this-repo> travelrouter && cd travelrouter
sudo ./install.sh
```
The installer:
1. installs `hostapd dnsmasq nftables iw ethtool wireguard-tools openvpn`,
2. disables the stock hostapd/dnsmasq units (we manage them per-AP),
3. copies the app to `/opt/travelrouter` in its own venv,
4. installs and enables `travelrouter-boot.service` and `travelrouter.service`,
5. prompts for the admin password,
6. starts everything.

Browse to `http://<pi-ip>:8080`. A starter AP (SSID `TravelRouter`) is created
on first boot so you can connect over Wi-Fi; change its credentials immediately.

## Upgrade
Re-run `sudo ./install.sh` (idempotent). State in `/var/lib/travelrouter` is
preserved.

## Uninstall
`sudo ./uninstall.sh`
