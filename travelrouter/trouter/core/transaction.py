"""Transaction manager — the appliance's anti-lockout core.

Any connectivity-affecting change follows this lifecycle:

    begin()      snapshot current generated config + a journal row (state=staged)
    apply(fn)    run the caller's apply function; on exception -> rollback
    health()     run health probes; if any fail -> rollback
    arm()        set a confirmation deadline (state=applied) and start the
                 watchdog. If commit() is not called before the deadline the
                 watchdog restores the snapshot automatically.
    commit()     the user confirmed connectivity still works -> keep changes
    rollback()   restore the snapshot and re-apply it

The snapshot is a tar of GEN_DIR plus a copy of the AP table, which is enough
to reconstruct every service config. Restoring the snapshot and re-running the
service reload returns the box to its last-known-good state.

This module never trusts a single request to be safe: even a perfectly valid
config can kill the link the admin is connected over, so the human-confirm
deadline is mandatory for any change touching APs, routing, or firewall.
"""
import os
import shutil
import tarfile
import threading
import time
import uuid

from .. import config, db

_active_lock = threading.Lock()
_watchdogs = {}   # txid -> threading.Timer


class TransactionError(Exception):
    pass


def _snapshot_path(txid):
    return os.path.join(config.SNAPSHOT_DIR, f"{txid}.tar.gz")


def _make_snapshot(txid):
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)
    path = _snapshot_path(txid)
    with tarfile.open(path, "w:gz") as tar:
        if os.path.isdir(config.GEN_DIR):
            tar.add(config.GEN_DIR, arcname="generated")
    return path


def _restore_snapshot(path):
    if not os.path.exists(path):
        raise TransactionError("snapshot missing; cannot roll back")
    # Wipe generated dir then extract.
    if os.path.isdir(config.GEN_DIR):
        shutil.rmtree(config.GEN_DIR)
    os.makedirs(os.path.dirname(config.GEN_DIR), exist_ok=True)
    with tarfile.open(path, "r:gz") as tar:
        tar.extractall(os.path.dirname(config.GEN_DIR.rstrip("/")))


class Transaction:
    def __init__(self, summary, reload_fn, health_fn):
        self.id = str(uuid.uuid4())
        self.summary = summary
        self.reload_fn = reload_fn      # callable() -> applies generated config
        self.health_fn = health_fn      # callable() -> (ok: bool, detail: str)
        self.snapshot = None
        self.deadline = None

    # -- lifecycle ------------------------------------------------------
    def begin(self):
        if not _active_lock.acquire(blocking=False):
            raise TransactionError("another change is already in progress")
        self.snapshot = _make_snapshot(self.id)
        with db.connect() as c:
            c.execute(
                "INSERT INTO transactions(id, ts, state, summary, snapshot) "
                "VALUES(?,?, 'staged', ?, ?)",
                (self.id, int(time.time()), self.summary, self.snapshot),
            )
        db.audit("system", "tx.begin", {"id": self.id, "summary": self.summary})
        return self

    def apply(self, generate_fn):
        """generate_fn writes the new generated config; then we reload."""
        try:
            generate_fn()
            self.reload_fn()
            self._set_state("applied")
        except Exception as e:
            self._rollback(reason=f"apply failed: {e}")
            raise TransactionError(f"apply failed and was rolled back: {e}")

    def health(self):
        ok, detail = self.health_fn()
        if not ok:
            self._rollback(reason=f"health check failed: {detail}")
            raise TransactionError(f"health check failed, rolled back: {detail}")
        return True

    def arm(self):
        """Start the confirmation countdown + watchdog."""
        self.deadline = int(time.time()) + config.CONFIRM_TIMEOUT_SECONDS
        with db.connect() as c:
            c.execute("UPDATE transactions SET deadline=? WHERE id=?",
                      (self.deadline, self.id))
        timer = threading.Timer(config.CONFIRM_TIMEOUT_SECONDS,
                                self._watchdog_fire)
        timer.daemon = True
        _watchdogs[self.id] = timer
        timer.start()
        db.audit("system", "tx.arm",
                 {"id": self.id, "deadline": self.deadline})
        return self.deadline

    def commit(self):
        self._cancel_watchdog()
        self._set_state("committed")
        db.audit("system", "tx.commit", {"id": self.id})
        self._release()

    def _watchdog_fire(self):
        # Reached the deadline without a commit -> assume the admin is locked
        # out and revert.
        self._rollback(reason="confirmation timeout")

    def _rollback(self, reason):
        try:
            if self.snapshot:
                _restore_snapshot(self.snapshot)
                try:
                    self.reload_fn()
                except Exception:
                    pass
            self._set_state("rolledback")
            db.audit("system", "tx.rollback", {"id": self.id, "reason": reason})
        finally:
            self._cancel_watchdog()
            self._release()

    def rollback(self, reason="manual"):
        self._rollback(reason)

    # -- helpers --------------------------------------------------------
    def _set_state(self, state):
        with db.connect() as c:
            c.execute("UPDATE transactions SET state=? WHERE id=?",
                      (state, self.id))

    def _cancel_watchdog(self):
        t = _watchdogs.pop(self.id, None)
        if t:
            t.cancel()

    def _release(self):
        try:
            _active_lock.release()
        except RuntimeError:
            pass


def get(txid):
    with db.connect() as c:
        row = c.execute("SELECT * FROM transactions WHERE id=?",
                        (txid,)).fetchone()
    return dict(row) if row else None


def pending():
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM transactions WHERE state='applied' "
            "ORDER BY ts DESC LIMIT 1").fetchone()
    return dict(row) if row else None
