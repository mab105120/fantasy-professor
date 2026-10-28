"""Freshness guard (spec §5.2): each capability declares how fresh its data
must be; if sync_meta says otherwise, the capability syncs before analysing."""
from dataclasses import dataclass
from datetime import datetime

from . import sync
from .paths import Paths


@dataclass(frozen=True)
class MaxAge:
    """`file` must have been synced within `hours` (and with a pool of at
    least `min_size` free agents, for free_agents.json)."""
    file: str
    hours: float
    min_size: int | None = None


@dataclass(frozen=True)
class WeekDone:
    """The given week ("previous" or "current") of a per-week history file must
    be synced; `final=True` also requires it to be complete (week over)."""
    file: str
    which: str = "previous"
    final: bool = True


REQUIREMENTS: dict[str, list] = {
    "review": [MaxAge("teams.json", 12), MaxAge("transactions.json", 24),
               WeekDone("week_stats.json"), WeekDone("power_rankings.json")],
    "waivers": [MaxAge("free_agents.json", 6, min_size=600), MaxAge("teams.json", 6),
                MaxAge("transactions.json", 12), WeekDone("week_stats.json")],
    "lineup": [MaxAge("teams.json", 2), MaxAge("free_agents.json", 6),
               WeekDone("week_stats.json", "current", final=False), WeekDone("week_stats.json")],
    "preview": [MaxAge("teams.json", 12), MaxAge("transactions.json", 24),
                WeekDone("week_stats.json", "current", final=False)],
    "trade": [MaxAge("teams.json", 6), MaxAge("transactions.json", 24), MaxAge("draft_results.json", 24 * 365)],
    "player-eval": [MaxAge("teams.json", 6), MaxAge("free_agents.json", 12, min_size=600),
                    MaxAge("transactions.json", 24)],
}

FIX = {  # espn_client.py args that refresh each file
    "league.json": ["sync", "--free-agents-size", "600"],
    "teams.json": ["sync", "--free-agents-size", "600"],
    "free_agents.json": ["sync", "--free-agents-size", "600"],
    "transactions.json": ["transactions"],
    "draft_results.json": ["draft-results"],
}


def _age_hours(stamp: str | None, now: datetime) -> float | None:
    if not stamp:
        return None
    return (now - datetime.fromisoformat(stamp)).total_seconds() / 3600


def evaluate(paths: Paths, capability: str, now: datetime | None = None) -> list[tuple[str, list[str]]]:
    """Return [(problem, fix_args)] for every unmet requirement (empty = fresh)."""
    if capability not in REQUIREMENTS:
        raise SystemExit(f"unknown capability {capability!r}; expected one of {list(REQUIREMENTS)}")
    now = now or datetime.now()
    meta = paths.read_json(paths.sync_meta, {}) or {}
    league = paths.read_json(paths.data / "league.json") or {}
    cur = league.get("current_week")
    problems = []
    for req in REQUIREMENTS[capability]:
        entry = meta.get(req.file, {})
        if isinstance(req, MaxAge):
            age = _age_hours(entry.get("synced_at"), now)
            if age is None or age > req.hours:
                got = "never synced" if age is None else f"{age:.1f}h old"
                problems.append((f"{req.file}: {got} (needs < {req.hours:g}h)", FIX[req.file]))
            elif req.min_size and (entry.get("size") or 0) < req.min_size:
                problems.append((f"{req.file}: pool of {entry.get('size', 'unknown')} (needs {req.min_size})",
                                 FIX[req.file]))
            continue
        if cur is None:
            problems.append(("league.json missing (current week unknown)", FIX["league.json"]))
            continue
        week = cur - 1 if req.which == "previous" else cur
        if week < 1:
            continue
        cmd = "week-stats" if req.file == "week_stats.json" else "power-rankings"
        wk = entry.get("weeks", {}).get(str(week))
        if wk is None:
            problems.append((f"{req.file}: week {week} not synced", [cmd, "--week", str(week)]))
        elif req.final and not wk.get("complete"):
            problems.append((f"{req.file}: week {week} not final yet", [cmd, "--week", str(week)]))
        elif not req.final and req.which == "current":
            age = _age_hours(wk.get("synced_at"), now)
            if age is None or age > 12:
                got = "undated" if age is None else f"{age:.1f}h old"
                problems.append((f"{req.file}: week {week} snapshot {got} (needs < 12h)",
                                 [cmd, "--week", str(week)]))
    return problems


def ensure(paths: Paths, capability: str, check_only: bool = False, log=print) -> bool:
    """Sync whatever is stale for `capability`. League-level syncs run first and
    the week checks are re-evaluated after, since a sync can move current_week."""
    problems = evaluate(paths, capability)
    if not problems:
        log(f"{capability}: data is fresh enough")
        return True
    for p, _ in problems:
        log(f"stale  {p}")
    if check_only:
        return False
    league_level = [fix for _, fix in problems if fix[0] in ("sync", "transactions", "draft-results")]
    if league_level:
        sync.run(paths, _unique(league_level), f"fresh:{capability}", log=log)
    weekly = [fix for _, fix in evaluate(paths, capability)]
    if weekly:
        sync.run(paths, _unique(weekly), f"fresh:{capability}", log=log)
    left = evaluate(paths, capability)
    for p, _ in left:
        log(f"still stale after sync: {p}")
    return not left


def _unique(cmds: list[list[str]]) -> list[list[str]]:
    seen, out = set(), []
    for c in cmds:
        if tuple(c) not in seen:
            seen.add(tuple(c))
            out.append(c)
    return out
