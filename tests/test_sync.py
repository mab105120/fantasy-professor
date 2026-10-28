import json
import threading
import time

import pytest

from fplib import sync
from fplib.sync import SyncError


def fake_client(proj, body: str):
    tools = proj.root / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "espn_client.py").write_text(body)


def test_run_records_success(proj):
    fake_client(proj, "print('Synced league 394766 (2026), week 6')")
    sync.run(proj, [["sync"]], "job:light", log=lambda m: None)
    job = sync.job_status(proj)
    assert job["ok"] is True and job["label"] == "job:light" and job["failing_since"] is None
    assert "teams.json" in json.loads(proj.sync_meta.read_text())   # other keys preserved


def test_run_records_failure_and_explains_auth(proj):
    fake_client(proj, "import sys; sys.exit('espn_api: 401 Unauthorized for private league')")
    with pytest.raises(SyncError, match="cookies have likely expired"):
        sync.run(proj, [["sync"]], "job:light", log=lambda m: None)
    first = sync.job_status(proj)
    assert first["ok"] is False and first["failing_since"]
    with pytest.raises(SyncError):
        sync.run(proj, [["sync"]], "job:light", log=lambda m: None)
    assert sync.job_status(proj)["failing_since"] == first["failing_since"]   # keeps the first failure time


def test_lock_blocks_second_writer(proj):
    held = threading.Event()
    release = threading.Event()

    def holder():
        with sync.sync_lock(proj):
            held.set()
            release.wait(5)

    t = threading.Thread(target=holder)
    t.start()
    held.wait(5)
    start = time.monotonic()
    with pytest.raises(SyncError, match="held the lock"):
        with sync.sync_lock(proj, timeout=0.3, poll=0.05):
            pass
    assert time.monotonic() - start >= 0.3
    release.set()
    t.join()
    with sync.sync_lock(proj, timeout=1):
        pass
