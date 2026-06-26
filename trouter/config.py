"""Central configuration: filesystem layout and runtime constants.

All absolute paths live here so the rest of the codebase never hard-codes a
location. Override any of these with environment variables (TROUTER_*) for
development on a non-Pi machine.
"""
import os

def _p(env, default):
    return os.environ.get(env, default)

# Where the appliance stores mutable state.
STATE_DIR        = _p("TROUTER_STATE_DIR", "/var/lib/travelrouter")
DB_PATH          = os.path.join(STATE_DIR, "trouter.sqlite3")
SNAPSHOT_DIR     = os.path.join(STATE_DIR, "snapshots")
BACKUP_DIR       = os.path.join(STATE_DIR, "backups")
RUN_DIR          = _p("TROUTER_RUN_DIR", "/run/travelrouter")

# Generated system config that real services consume.
GEN_DIR          = _p("TROUTER_GEN_DIR", "/etc/travelrouter/generated")
HOSTAPD_DIR      = os.path.join(GEN_DIR, "hostapd")      # one .conf per AP
DNSMASQ_DIR      = os.path.join(GEN_DIR, "dnsmasq")      # one .conf per AP
NFTABLES_FILE    = os.path.join(GEN_DIR, "nftables.conf")
SYSCTL_FILE      = "/etc/sysctl.d/99-travelrouter.conf"

# User-facing sandboxes.
FILES_ROOT       = _p("TROUTER_FILES_ROOT", "/srv/files")
SCRIPTS_ROOT     = _p("TROUTER_SCRIPTS_ROOT", "/home/pi/scripts")

# Logs.
LOG_DIR          = _p("TROUTER_LOG_DIR", "/var/log/travelrouter")

# Bundled assets (templates that generate system config).
PKG_DIR          = os.path.dirname(os.path.abspath(__file__))
REPO_DIR         = os.path.dirname(PKG_DIR)
SYSTEM_TEMPLATES = os.path.join(REPO_DIR, "templates_system")
DEFAULT_CONFIG   = os.path.join(REPO_DIR, "config", "default.yaml")
REGULATORY_DB    = os.path.join(REPO_DIR, "config", "regulatory.yaml")

# Safety: how long the user has to confirm a connectivity-affecting change
# before it auto-reverts. Spec asks for 60-120s.
CONFIRM_TIMEOUT_SECONDS = int(_p("TROUTER_CONFIRM_TIMEOUT", "90"))

# Management UI port (must match what the firewall opens) and the regulatory
# domain the radio + hostapd use. Without a country the Pi's radio stays
# rfkill-blocked and hostapd refuses to start an AP.
MGMT_PORT    = int(_p("TROUTER_PORT", "8080"))
COUNTRY_CODE = _p("TROUTER_COUNTRY", "US")

# Web/security.
SECRET_KEY_FILE  = os.path.join(STATE_DIR, "secret.key")
SESSION_LIFETIME_MIN = 60
LOGIN_MAX_ATTEMPTS   = 5
LOGIN_LOCKOUT_SEC    = 300

ALL_DIRS = [STATE_DIR, SNAPSHOT_DIR, BACKUP_DIR, RUN_DIR, GEN_DIR,
            HOSTAPD_DIR, DNSMASQ_DIR, FILES_ROOT, SCRIPTS_ROOT, LOG_DIR]

def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)
