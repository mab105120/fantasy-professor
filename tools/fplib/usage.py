"""Box-score usage shares for one player (plan §4 `fp usage`): targets and
carries as a share of the team's, per completed game. Replaces the
per-skill scratchpad code. Completed games never change, so their summaries
are cached under .run/cache/espn/."""
import json
from pathlib import Path

import requests

from .paths import Paths

SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
TEAM_FIX = {"JAC": "JAX", "WAS": "WSH"}  # fantasy API vs site API abbreviations


def norm(abbr: str | None) -> str | None:
    return TEAM_FIX.get(abbr, abbr) if abbr else abbr


def _stat(group: dict | None, athlete_id: str | None, key: str) -> float:
    """A stat from a box-score group, for one athlete or (None) the team total."""
    if not group or key not in group.get("keys", []):
        return 0.0
    i = group["keys"].index(key)
    if athlete_id is None:
        vals = group.get("totals") or []
    else:
        row = next((a for a in group.get("athletes", []) if str(a["athlete"]["id"]) == athlete_id), None)
        vals = row["stats"] if row else []
    try:
        return float(vals[i])
    except (IndexError, ValueError, TypeError):
        return 0.0


def _attempts(group: dict | None) -> float:
    if not group or "completions/passingAttempts" not in group.get("keys", []):
        return 0.0
    i = group["keys"].index("completions/passingAttempts")
    try:
        return float(group["totals"][i].split("/")[1])
    except (IndexError, ValueError, AttributeError):
        return 0.0


def game_usage(summary: dict, player_id: int) -> dict | None:
    """Usage for `player_id` in one game summary, or None if he has no line.
    Pure function (tested against a recorded fixture)."""
    pid = str(player_id)
    header = summary.get("header", {})
    comps = header.get("competitions", [{}])[0].get("competitors", [])
    for team in summary.get("boxscore", {}).get("players", []):
        groups = {g["name"]: g for g in team.get("statistics", [])}
        if not any(str(a["athlete"]["id"]) == pid for g in groups.values() for a in g.get("athletes", [])):
            continue
        ab = team["team"]["abbreviation"]
        opp = next((c["team"]["abbreviation"] for c in comps if c["team"]["abbreviation"] != ab), None)
        rec, rush = groups.get("receiving"), groups.get("rushing")
        tgt, team_tgt = _stat(rec, pid, "receivingTargets"), _stat(rec, None, "receivingTargets")
        car, team_car = _stat(rush, pid, "rushingAttempts"), _stat(rush, None, "rushingAttempts")
        return {
            "week": header.get("week"),
            "team": ab,
            "opponent": opp,
            "targets": tgt, "team_targets": team_tgt,
            "target_share": round(tgt / team_tgt, 3) if team_tgt else None,
            "carries": car, "team_carries": team_car,
            "carry_share": round(car / team_car, 3) if team_car else None,
            "team_pass_attempts": _attempts(groups.get("passing")),
            "receptions": _stat(rec, pid, "receptions"),
            "receiving_yards": _stat(rec, pid, "receivingYards"),
            "rushing_yards": _stat(rush, pid, "rushingYards"),
            "touchdowns": _stat(rec, pid, "receivingTouchdowns") + _stat(rush, pid, "rushingTouchdowns"),
        }
    return None


class Client:
    def __init__(self, paths: Paths, session=None):
        self.paths = paths
        self.http = session or requests.Session()
        self.cache = paths.run / "cache" / "espn"

    def get(self, url: str, params: dict | None = None) -> dict:
        r = self.http.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def summary(self, event_id: str, completed: bool) -> dict:
        path: Path = self.cache / f"summary-{event_id}.json"
        if completed and path.exists():
            return json.loads(path.read_text())
        data = self.get(f"{SITE}/summary", {"event": event_id})
        if completed:
            self.cache.mkdir(parents=True, exist_ok=True)
            # keep only what usage needs; full summaries are ~600 KB
            path.write_text(json.dumps({"header": data.get("header"), "boxscore": data.get("boxscore")}))
        return data

    def team_id(self, abbr: str) -> str:
        data = self.get(f"{SITE}/teams")
        for t in data["sports"][0]["leagues"][0]["teams"]:
            if t["team"]["abbreviation"] == abbr:
                return t["team"]["id"]
        raise SystemExit(f"unknown NFL team {abbr!r}")

    def completed_events(self, team_id: str, season: int) -> list[str]:
        data = self.get(f"{SITE}/teams/{team_id}/schedule", {"season": season, "seasontype": 2})
        return [e["id"] for e in data.get("events", [])
                if e["competitions"][0]["status"]["type"].get("completed")]


def find_player(paths: Paths, player_id: int) -> dict:
    """Name and NFL team from the league cache (rosters, free agents, week stats)."""
    for t in paths.read_json(paths.data / "teams.json", []) or []:
        for p in t["roster"]:
            if p["playerId"] == player_id:
                return {"name": p["name"], "pro_team": p["proTeam"], "position": p["position"]}
    for p in paths.read_json(paths.data / "free_agents.json", []) or []:
        if p["playerId"] == player_id:
            return {"name": p["name"], "pro_team": p["proTeam"], "position": p["position"]}
    raise SystemExit(f"player {player_id} not found in teams.json or free_agents.json "
                     f"(re-sync with a deeper pool: fp fresh player-eval)")


def player_usage(paths: Paths, player_id: int, weeks: int = 3, client: Client | None = None) -> dict:
    client = client or Client(paths)
    info = find_player(paths, player_id)
    season = (paths.read_json(paths.data / "league.json") or {}).get("year")
    events = client.completed_events(client.team_id(norm(info["pro_team"])), season)
    games = []
    for eid in reversed(events):
        summ = client.summary(eid, completed=True)
        g = game_usage(summ, player_id)
        if g is None:
            comps = summ.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
            opp = next((c["team"]["abbreviation"] for c in comps
                        if norm(c["team"]["abbreviation"]) != norm(info["pro_team"])), None)
            g = {"event_id": eid, "week": summ.get("header", {}).get("week"), "opponent": opp,
                 "note": "no box-score line (inactive or did not record a stat)"}
        games.append(g)
        if len(games) == weeks:
            break
    return {"player_id": player_id, **info, "games": list(reversed(games))}
