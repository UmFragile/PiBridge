# Troubleshooting

## `hostapd@apN.service` keeps restarting / the AP never appears

hostapd exits the instant it cannot put the radio into AP (master) mode, and
the unit's `Restart=on-failure` then loops it. Get the real reason first:

```sh
# The decisive command — runs hostapd in the foreground with full debug.
sudo systemctl stop hostapd@ap1
sudo hostapd -dd /etc/travelrouter/generated/hostapd/ap1.conf
```

The last handful of lines name the cause. The common ones, and their fixes:

### 1. The radio is busy as a Wi-Fi *client* (most common on Pi Zero 2 W)

The Pi Zero 2 W has **one** radio. If you reach the Pi over its onboard Wi-Fi,
`wpa_supplicant` owns `wlan0` as a station and hostapd cannot also run an AP on
it. Symptoms in the debug log: `Could not set interface wlan0 to master mode`,
`nl80211: Could not configure driver mode`, or `interface wlan0 wasn't started`.

You cannot be a client and an AP on the same single radio at once. Pick one:

* **Reach the Pi over Ethernet** (a USB Ethernet adapter, or the USB-OTG gadget)
  and let the onboard `wlan0` become the AP. This is the simplest setup.
* **Add a USB Wi-Fi adapter** for the AP and keep `wlan0` as your upstream
  client uplink. Assign the AP to the USB radio in the web UI.

`trouter.apctl` (run automatically before hostapd starts) will evict
`wpa_supplicant` from the AP interface — but if that interface is the link you
are connected over, evicting it drops your connection. That is expected; reach
the Pi another way before turning that radio into an AP.

### 2. The radio is rfkill soft-blocked

Fresh Pi OS images block the radio until a country is set.

```sh
rfkill list           # look for "Soft blocked: yes" on a wlan entry
sudo rfkill unblock wifi
sudo iw reg set US    # use your own country code
```

The installer and the `apctl` pre-start step now do this automatically; run the
commands by hand if you are on an older build.

### 3. Wrong or empty interface in the generated config

```sh
grep interface= /etc/travelrouter/generated/hostapd/ap1.conf
```

If `interface=` is empty or names a radio that isn't present, the AP is bound to
a stale interface UUID. Re-run discovery (restart `travelrouter.service`) or
re-create the AP against a present radio in the web UI.

## I can reach the UI on the Pi itself but not from another device

If the AP is down (see above) there is no `TravelRouter` network to join — fix
the AP first. Once a client is associated it lands on `10.42.0.0/24`, which the
firewall's input chain already allows to reach the management port.

If you are testing over the **upstream** LAN instead, the input chain allows the
management port only from RFC-1918 ranges (`10/8`, `172.16/12`, `192.168/16`).
Confirm the ruleset actually loaded:

```sh
sudo nft list table inet trouter | head
```

If the table is missing, a generation error aborted the (atomic) load; check
`journalctl -u travelrouter` for the nftables error.
