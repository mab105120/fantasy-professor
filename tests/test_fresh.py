import json
from datetime import datetime

from fplib import fresh

NOW = datetime(2026, 10, 17, 22, 0, 0)


def meta(proj, **entries):
    (proj.data / "sync_meta.json").write_text(json.dumps(entries))


def test_fresh_when_everything_recent(proj):
    meta(proj,
         **{"teams.json": {"synced_at": "2026-10-17T21:00:00"},
            "transactions.json": {"synced_at": "2026-10-17T20:00:00"},
            "week_stats.json": {"weeks": {"5": {"synced_at": "2026-10-13T20:00:00", "complete": True}}},
            "power_rankings.json": {"weeks": {"5": {"synced_at": "2026-10-13T20:00:00", "complete": True}}}})
    assert fresh.evaluate(proj, "review", now=NOW) == []


def test_stale_age_size_and_incomplete_week(proj):
    meta(proj,
         **{"teams.json": {"synced_at": "2026-10-17T10:00:00"},                   # 12h > 6h
            "free_agents.json": {"synced_at": "2026-10-17T21:00:00", "size": 150},  # too small
            "transactions.json": {"synced_at": "2026-10-17T21:00:00"},
            "week_stats.json": {"weeks": {"5": {"synced_at": "2026-10-11T20:00:00", "complete": False}}}})
    problems = dict(fresh.evaluate(proj, "waivers", now=NOW))
    assert any("teams.json: 12.0h old" in p for p in problems)
    assert any("pool of 150" in p for p in problems)
    assert problems["week_stats.json: week 5 not final yet"] == ["week-stats", "--week", "5"]


def test_missing_files_are_stale(proj):
    meta(proj)
    problems = [p for p, _ in fresh.evaluate(proj, "trade", now=NOW)]
    assert "teams.json: never synced (needs < 6h)" in problems


def test_check_only_does_not_sync(proj, monkeypatch):
    meta(proj)
    called = []
    monkeypatch.setattr(fresh.sync, "run", lambda *a, **k: called.append(a))
    assert fresh.ensure(proj, "trade", check_only=True, log=lambda m: None) is False
    assert called == []
