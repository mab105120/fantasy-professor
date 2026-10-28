import json

import pytest

from fplib import reports
from fplib.reports import ReportError


def test_paths_and_default_weeks(proj):
    assert reports.default_week(proj, "waivers") == 6
    assert reports.default_week(proj, "review") == 5   # reviews the week just played
    assert reports.report_path(proj, "waivers", 6).relative_to(proj.root).as_posix() == "reports/w06/waivers.json"
    assert reports.report_path(proj, "trade", 6).relative_to(proj.root).as_posix() == "reports/lab/trade.json"


def test_write_builds_envelope(proj):
    path = reports.write(proj, "waivers", 6, {"headline": "Hold: no claim", "sections": {"call": "hold"}})
    doc = json.loads(path.read_text())
    assert doc["status"] == "final" and doc["week"] == 6
    assert doc["man_wolf"] == {"record": "4-1", "standing": 3, "opponent_id": 9}
    assert doc["data_freshness"] == {"teams.json": "2026-10-17T21:27:29"}


def test_body_cannot_set_envelope_fields(proj):
    with pytest.raises(ReportError, match="Unexpected"):
        reports.write(proj, "waivers", 6, {"headline": "x", "week": 3})


def test_validation_error_names_the_path(proj):
    with pytest.raises(ReportError, match=r"glossary\.0\.definition"):
        reports.write(proj, "waivers", 6, {"headline": "x", "glossary": [{"term": "aDOT", "definition": ""}]})


def test_rerun_replaces_weekly_and_lab_overwrites(proj):
    reports.write(proj, "lineup", 6, {"headline": "first"})
    reports.write(proj, "lineup", 6, {"headline": "second"})
    assert json.loads(reports.report_path(proj, "lineup", 6).read_text())["headline"] == "second"
    reports.write(proj, "trade", 6, {"headline": "Gordon to Imad"})
    reports.write(proj, "trade", 7, {"headline": "Kamara to ALI"})
    lab = sorted(p.name for p in (proj.reports / "lab").iterdir())
    assert lab == ["trade.json"]
    assert json.loads((proj.reports / "lab" / "trade.json").read_text())["week"] == 7


def test_sections_then_finalize(proj):
    reports.write_section(proj, "preview", 6, "games.401", {"teams": ["SF", "SEA"]})
    reports.write_section(proj, "preview", 6, "games.402", {"teams": ["TB", "DAL"]})
    path = reports.report_path(proj, "preview", 6)
    doc = json.loads(path.read_text())
    assert doc["status"] == "draft" and set(doc["sections"]["games"]) == {"401", "402"}
    with pytest.raises(ReportError, match="headline"):
        reports.finalize(proj, "preview", 6)
    reports.finalize(proj, "preview", 6, {"headline": "Week 6: what to watch", "sections": {"what_to_watch": "x"}})
    doc = json.loads(path.read_text())
    assert doc["status"] == "final" and set(doc["sections"]) == {"games", "what_to_watch"}


def test_section_into_non_object_fails(proj):
    reports.write_section(proj, "preview", 6, "games", [1, 2])
    with pytest.raises(ReportError, match="not an object"):
        reports.write_section(proj, "preview", 6, "games.401", {})


def test_no_partial_files_left_behind(proj):
    reports.write(proj, "waivers", 6, {"headline": "x"})
    assert [p.name for p in (proj.reports / "w06").iterdir()] == ["waivers.json"]
