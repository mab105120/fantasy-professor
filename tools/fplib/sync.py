"""Running ESPN syncs safely (plan §6): one writer at a time, every run's
result recorded in data/sync_meta.json under `_job` so the app can show a
sync-health banner (e.g. expired ESPN cookies)."""
import fcntl
import json
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime

from .paths import Paths, write_json_atomic

# What each scheduled mode runs (espn_client.py subcommands, in order).
MODES: dict[str, list[list[str]]] = {
    "light": [["sync", "--free-agents-size", "600"]],
    "nightly": [["transactions"], ["week-stats"]],
    # Tuesday after MNF: re-pull last week (now complete) and this week.
    "finalize": [["sync", "--free-agents-size", "600"], ["week-stats"], ["power-rankings"], ["transactions"]],
}


class SyncError(Exception):
    pass


@contextmanager
def sync_lock(paths: Paths, timeout: float = 900, poll: float = 1.0):
    """Exclusive lock on data/.sync.lock. A second writer waits rather than
    colliding; gives up after `timeout` seconds."""
    paths.data.mkdir(parents=True, exist_ok=True)
    with open(paths.data / ".sync.lock", "w") as fh:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SyncError(f"another sync held the lock for over {timeout:.0f}s")
                time.sleep(poll)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run_step(paths: Paths, args: list[str]) -> str:
    proc = subprocess.run([sys.executable, str(paths.espn_client), *args], cwd=paths.root,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        raise SyncError(f"`espn_client.py {' '.join(args)}` failed: {tail[0]}")
    return proc.stdout


def explain(error: str) -> str:
    low = error.lower()
    if any(s in low for s in ("401", "unauthorized", "espn_s2", "swid", "private league")):
        return error + " — ESPN cookies have likely expired: refresh espn_s2/SWID in config/league_config.json"
    return error


def record_job(paths: Paths, label: str, ok: bool, error: str | None) -> None:
    meta = paths.read_json(paths.sync_meta, {}) or {}
    now = datetime.now().isoformat(timespec="seconds")
    job = meta.get("_job", {})
    job.update({"last_run": now, "label": label, "ok": ok, "error": error})
    if ok:
        job["last_success"] = now
        job["failing_since"] = None
    elif not job.get("failing_since"):
        job["failing_since"] = now
    meta["_job"] = job
    write_json_atomic(paths.sync_meta, meta)


def run(paths: Paths, steps: list[list[str]], label: str, log=print) -> None:
    """Run steps under the lock; record success/failure; re-raise on failure."""
    with sync_lock(paths):
        try:
            for args in steps:
                log(f"[{datetime.now():%H:%M:%S}] espn_client.py {' '.join(args)}")
                out = run_step(paths, args)
                for ln in out.strip().splitlines()[:3]:
                    log(f"    {ln}")
        except SyncError as e:
            msg = explain(str(e))
            record_job(paths, label, False, msg)
            raise SyncError(msg) from None
        record_job(paths, label, True, None)


def job_status(paths: Paths) -> dict:
    return (paths.read_json(paths.sync_meta, {}) or {}).get("_job", {})


def dumps(obj) -> str:
    return json.dumps(obj, indent=2)
