#!/usr/bin/env python3
"""Scheduled ESPN sync (plan §6). Run by launchd (tools/launchd/), or by hand:

    .venv/bin/python tools/sync_job.py light      # every 4h: league, rosters, injuries, 600-player FA pool
    .venv/bin/python tools/sync_job.py nightly    # 03:00: transactions + this/last week's stat lines
    .venv/bin/python tools/sync_job.py finalize   # Tue 06:00: everything, marking last week complete

Takes the shared sync lock, records the outcome in data/sync_meta.json
(`_job`), and exits non-zero on failure so `launchctl print` shows it.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fplib import sync  # noqa: E402
from fplib.paths import Paths  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=sorted(sync.MODES))
    a = p.parse_args(argv)
    print(f"=== sync_job {a.mode} @ {datetime.now().isoformat(timespec='seconds')}", flush=True)
    try:
        sync.run(Paths(), sync.MODES[a.mode], f"job:{a.mode}", log=lambda m: print(m, flush=True))
    except sync.SyncError as e:
        print(f"FAILED: {e}", flush=True)
        return 1
    print("ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
