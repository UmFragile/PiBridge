"""SQLite persistence layer and schema.

A single connection-per-call model keeps this simple and safe under the low
concurrency of an embedded appliance. Foreign keys are enforced. The schema
is created idempotently on first run.
"""
import sqlite3
import json
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Stable identity for every NIC the appliance has ever seen. The UUID is
-- keyed on MAC so a USB adapter keeps its config across replug/reboot.
CREATE TABLE IF NOT EXISTS interfaces (
    uuid        TEXT PRIMARY KEY,
    mac         TEXT UNIQUE NOT NULL,
    kind        TEXT NOT NULL,          -- wifi_builtin|wifi_usb|eth_usb|eth|modem|tether|generic
    last_name   TEXT,                   -- last kernel name (wlan0...) — informational only
    driver      TEXT,
    phy         TEXT,
    capabilities TEXT,                  -- JSON blob from HAL capability probe
    role        TEXT DEFAULT 'unused',  -- ap|client|wan|vpn_only|unused
    first_seen  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL,
    present     INTEGER NOT NULL DEFAULT 0
);

-- Access Point profiles. Each maps to one interface UUID.
CREATE TABLE IF NOT EXISTS access_points (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    iface_uuid    TEXT NOT NULL REFERENCES interfaces(uuid),
    ssid          TEXT NOT NULL,
    psk           TEXT,                 -- NULL/empty => open (discouraged)
    band          TEXT DEFAULT '2.4',   -- 2.4|5
    channel       INTEGER DEFAULT 6,
    hidden        INTEGER DEFAULT 0,
    client_isolation INTEGER DEFAULT 0,
    max_clients   INTEGER DEFAULT 32,
    subnet        TEXT DEFAULT '10.42.0.0/24',
    dhcp_start    TEXT DEFAULT '10.42.0.50',
    dhcp_end      TEXT DEFAULT '10.42.0.200',
    dns_servers   TEXT DEFAULT '1.1.1.1,9.9.9.9',
    routing_policy TEXT DEFAULT 'direct', -- direct|wireguard|openvpn|isolated|killswitch
    vpn_id        INTEGER REFERENCES vpn_profiles(id),
    enabled       INTEGER DEFAULT 1,
    schedule      TEXT,                 -- JSON {days:[],start:"HH:MM",end:"HH:MM"} or NULL
    created       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vpn_profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,          -- wireguard|openvpn
    config_blob TEXT NOT NULL,          -- raw tunnel config (stored; encrypt-at-rest TODO)
    kill_switch INTEGER DEFAULT 1,
    auto_reconnect INTEGER DEFAULT 1,
    created     INTEGER NOT NULL
);

-- Per-AP MAC access control.
CREATE TABLE IF NOT EXISTS mac_acl (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ap_id     INTEGER NOT NULL REFERENCES access_points(id) ON DELETE CASCADE,
    mac       TEXT NOT NULL,
    mode      TEXT NOT NULL             -- allow|deny
);

-- Client identity/state (rename, reservations, block flags persist here).
CREATE TABLE IF NOT EXISTS clients (
    mac         TEXT PRIMARY KEY,
    label       TEXT,
    reserved_ip TEXT,
    blocked     INTEGER DEFAULT 0,
    first_seen  INTEGER,
    last_seen   INTEGER
);

CREATE TABLE IF NOT EXISTS scripts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT UNIQUE NOT NULL,
    enabled   INTEGER DEFAULT 0,
    last_run  INTEGER,
    last_rc   INTEGER
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    actor     TEXT,
    action    TEXT NOT NULL,
    detail    TEXT
);

-- Transaction journal: every staged/applied/committed/rolled-back change.
CREATE TABLE IF NOT EXISTS transactions (
    id          TEXT PRIMARY KEY,       -- uuid4
    ts          INTEGER NOT NULL,
    state       TEXT NOT NULL,          -- staged|applied|committed|rolledback|failed
    summary     TEXT,
    snapshot    TEXT,                   -- path to snapshot dir
    deadline    INTEGER                 -- epoch by which confirmation is required
);

CREATE TABLE IF NOT EXISTS users (
    username    TEXT PRIMARY KEY,
    pw_hash     TEXT NOT NULL,
    created     INTEGER NOT NULL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    config.ensure_dirs()
    with connect() as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version','1')"
        )


def audit(actor, action, detail=None):
    with connect() as c:
        c.execute(
            "INSERT INTO audit_log(ts, actor, action, detail) VALUES(?,?,?,?)",
            (int(time.time()), actor, action,
             json.dumps(detail) if detail is not None else None),
        )
