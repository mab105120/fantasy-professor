"""Report storage, envelope building, validation and section merging (plan §3–4)."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from schemas.report import BODY_FIELDS, LAB_TYPES, REPORT_TYPES, WEEKLY_TYPES, Report

from .paths import Paths, write_json_atomic

MAN_WOLF_ID = 14


class ReportError(Exception):
    pass


def default_week(paths: Paths, rtype: str) -> int:
    """Week a report is filed under when none is given: the current week, except
    Week in Review, which reviews the week just played."""
    week = paths.current_week()
    return max(1, week - 1) if rtype == "review" else week


def report_path(paths: Paths, rtype: str, week: int) -> Path:
    if rtype in WEEKLY_TYPES:
        return paths.reports / f"w{week:02d}" / f"{rtype}.json"
    if rtype in LAB_TYPES:
        return paths.reports / "lab" / f"{rtype}.json"
    raise ReportError(f"unknown report type {rtype!r}; expected one of {list(REPORT_TYPES)}")


def format_errors(err: ValidationError) -> str:
    """One line per failure with the exact path, so a skill can fix and retry."""
    lines = []
    for e in err.errors():
        loc = ".".join(str(p) for p in e["loc"]) or "<root>"
        lines.append(f"  {loc}: {e['msg']}")
    return "\n".join(lines)


def validate(doc: dict) -> Report:
    try:
        return Report.model_validate(doc)
    except ValidationError as e:
        raise ReportError("report failed validation:\n" + format_errors(e)) from None


def freshness(paths: Paths) -> dict[str, str | None]:
    meta = paths.read_json(paths.sync_meta, {}) or {}
    return {name: entry.get("synced_at") for name, entry in meta.items()
            if not name.startswith("_") and isinstance(entry, dict)}


def man_wolf(paths: Paths, week: int) -> dict | None:
    teams = paths.read_json(paths.data / "teams.json")
    if not teams:
        return None
    me = next((t for t in teams if t["team_id"] == MAN_WOLF_ID), None)
    if me is None:
        return None
    rec = f"{me['wins']}-{me['losses']}" + (f"-{me['ties']}" if me.get("ties") else "")
    opp = next((s["opponent_team_id"] for s in me.get("schedule", []) if s["week"] == week), None)
    return {"record": rec, "standing": me["standing"], "opponent_id": opp}


def envelope(paths: Paths, rtype: str, week: int, status: str) -> dict:
    return {
        "type": rtype,
        "schema_version": 1,
        "status": status,
        "week": week,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_freshness": freshness(paths),
        "man_wolf": man_wolf(paths, week),
    }


def check_body(body: Any) -> dict:
    if not isinstance(body, dict):
        raise ReportError("report body must be a JSON object")
    extra = sorted(set(body) - set(BODY_FIELDS))
    if extra:
        raise ReportError(f"body may only contain {list(BODY_FIELDS)}; fp sets the envelope. Unexpected: {extra}")
    return body


def write(paths: Paths, rtype: str, week: int, body: dict, draft: bool = False) -> Path:
    """Validate and place a complete report. Replaces any existing report in
    the same slot (weekly: same type+week; lab: the single slot)."""
    doc = envelope(paths, rtype, week, "draft" if draft else "final") | check_body(body)
    validate(doc)
    path = report_path(paths, rtype, week)
    write_json_atomic(path, doc)
    return path


def set_path(obj: dict, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    if not all(keys):
        raise ReportError(f"bad section key {dotted!r}")
    cur = obj
    for k in keys[:-1]:
        nxt = cur.setdefault(k, {})
        if not isinstance(nxt, dict):
            raise ReportError(f"section key {dotted!r}: {k!r} is not an object")
        cur = nxt
    cur[keys[-1]] = value


def write_section(paths: Paths, rtype: str, week: int, key: str, value: Any) -> Path:
    """Merge one piece into `sections` at a dotted key (e.g. `games.401772810`).
    Creates a draft report if none exists yet; the report stays a draft until
    `finalize`. An existing final report is reopened as a draft."""
    path = report_path(paths, rtype, week)
    doc = paths.read_json(path)
    if doc is None or doc.get("week") != week:
        doc = envelope(paths, rtype, week, "draft") | {"sections": {}}
    doc["status"] = "draft"
    doc.setdefault("sections", {})
    set_path(doc["sections"], key, value)
    validate(doc)
    write_json_atomic(path, doc)
    return path


def finalize(paths: Paths, rtype: str, week: int, body: dict | None = None) -> Path:
    """Mark a draft final, optionally merging top-level body fields (e.g. the
    headline once all sections are in). Refreshes created_at/freshness."""
    path = report_path(paths, rtype, week)
    doc = paths.read_json(path)
    if doc is None:
        raise ReportError(f"no report at {path} to finalize")
    body = check_body(body or {})
    sections = {**doc.get("sections", {}), **body.pop("sections", {})}
    doc = {**doc, **envelope(paths, rtype, week, "final"), **body, "sections": sections}
    validate(doc)
    write_json_atomic(path, doc)
    return path


def load_json_arg(arg: str) -> Any:
    """Read JSON from a file path, or stdin when the path is '-'."""
    import sys
    text = sys.stdin.read() if arg == "-" else Path(arg).read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ReportError(f"{arg}: invalid JSON at line {e.lineno} col {e.colno}: {e.msg}") from None
