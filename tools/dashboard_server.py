#!/usr/bin/env python3
"""
Live dashboard server for the weekly-matchup report.

Serves the latest weekly-matchup report with a live layer on top, plus a
small JSON API that the page (or the agent, via curl) polls for fresh data.
Data is split into three groups, each cached for its own interval so ESPN is
hit at most once per interval no matter how many tabs or clients poll:

    live     NFL scoreboard (state, score, clock, line) + every rostered
             player's fantasy points/slot/projection from ESPN box scores,
             and the Man Wolf matchup tally computed from both.
    rosters  fantasy standings/records and NFL injury reports for games not
             yet final (one ESPN game-summary call per game).
    static   the report file itself; the page reloads when it changes
             (e.g. after a new /weekly-matchup run).

Usage:
    python3 tools/dashboard_server.py                    # http://127.0.0.1:8765
    python3 tools/dashboard_server.py --live 5 --rosters 120 --static 30
    python3 tools/dashboard_server.py --report reports/weekly-matchup/<file>.html --week 5

API (all GET return JSON; intervals are seconds):
    GET  /api/live      GET /api/rosters      GET /api/static
    GET  /api/all       everything above in one payload (handy for the agent)
    GET  /api/config    current intervals and their allowed ranges
    POST /api/config    {"live": 7, "rosters": 300, "static": 60} - any subset
    GET  /api/<group>?force=1   bypass the cache once
"""
import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import espn_client as ec  # noqa: E402

ROOT = ec.ROOT
ASSETS = Path(__file__).resolve().parent / "dashboard"
REPORTS = ROOT / "reports" / "weekly-matchup"
SITE_API = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# allowed interval range per group (seconds) and defaults
LIMITS = {"live": (5, 60), "rosters": (60, 3600), "static": (10, 3600)}
DEFAULTS = {"live": 7, "rosters": 300, "static": 60}

# ESPN fantasy and site APIs disagree on a few team abbreviations
TEAM_FIX = {"JAC": "JAX", "WAS": "WSH"}
SKILL_POS = {"QB", "RB", "WR", "TE"}


def team_abbr(t: str) -> str:
    return TEAM_FIX.get(t, t)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Group:
    """A cached data group: refetched when older than its interval, one fetch
    at a time; on failure the last good data is kept and the error reported."""

    def __init__(self, name: str, fetch, interval: int):
        self.name, self.fetch, self.interval = name, fetch, interval
        self.data, self.fetched_at, self.error = None, 0.0, None
        self.lock = threading.Lock()

    def get(self, force: bool = False) -> dict:
        with self.lock:
            if force or self.data is None or time.time() - self.fetched_at >= self.interval:
                try:
                    self.data = self.fetch()
                    self.fetched_at, self.error = time.time(), None
                except Exception as e:  # keep serving stale data
                    self.error = f"{type(e).__name__}: {e}"
                    if self.data is None:
                        self.fetched_at = time.time()  # don't hammer ESPN while it's failing
            age = time.time() - self.fetched_at
            return {
                "group": self.name,
                "fetched_at": datetime.fromtimestamp(self.fetched_at, timezone.utc).isoformat(timespec="seconds"),
                "age_s": round(age, 1),
                "interval_s": self.interval,
                "stale": self.error is not None,
                "error": self.error,
                "data": self.data,
            }


class Dashboard:
    def __init__(self, cfg: dict, week: int | None, report: Path | None, intervals: dict):
        self.cfg = cfg
        self.league = ec.connect(cfg)
        self.league_lock = threading.Lock()
        self.week = week or self.league.current_week
        self.report = report or latest_report()
        self.my_id = next(t.team_id for t in self.league.teams if ec.is_my_team(t, cfg))
        self.http = requests.Session()
        self.groups = {
            "live": Group("live", self.fetch_live, intervals["live"]),
            "rosters": Group("rosters", self.fetch_rosters, intervals["rosters"]),
            "static": Group("static", self.fetch_static, intervals["static"]),
        }

    # ---------- live
    def scoreboard(self) -> list:
        r = self.http.get(f"{SITE_API}/scoreboard",
                          params={"week": self.week, "seasontype": 2, "dates": self.cfg["year"]}, timeout=10)
        r.raise_for_status()
        games = []
        for e in r.json().get("events", []):
            c = e["competitions"][0]
            side = {x["homeAway"]: x for x in c["competitors"]}
            odds = (c.get("odds") or [{}])[0]
            st = e["status"]["type"]
            games.append({
                "id": e["id"],
                "away": side["away"]["team"]["abbreviation"],
                "home": side["home"]["team"]["abbreviation"],
                "away_score": int(side["away"].get("score") or 0),
                "home_score": int(side["home"].get("score") or 0),
                "state": st["state"],            # pre | in | post
                "detail": st["shortDetail"],     # "Final", "1:56 - 4th", "10/11 - 8:20 PM EDT"
                "kickoff": e["date"],
                "line": odds.get("details"),
                "over_under": odds.get("overUnder"),
            })
        return games

    def fetch_live(self) -> dict:
        games = self.scoreboard()
        state = {}
        for g in games:
            state[g["away"]] = state[g["home"]] = g["state"]
        with self.league_lock:
            boxes = self.league.box_scores(week=self.week)
        players, matchup = [], None
        for m in boxes:
            sides = [(m.home_team, m.home_lineup)] + ([(m.away_team, m.away_lineup)] if m.away_team else [])
            for team, lineup in sides:
                for bp in lineup:
                    pro = team_abbr(bp.proTeam)
                    players.append({
                        "player_id": bp.playerId,
                        "name": bp.name,
                        "position": bp.position,
                        "pro_team": pro,
                        "fantasy_team_id": team.team_id,
                        "slot": bp.slot_position,
                        "starter": bp.slot_position not in ("BE", "IR"),
                        "points": round(bp.points or 0, 2),
                        "projected": round(bp.projected_points or 0, 2),
                        "injury_status": ec.injury_status(bp),
                        "on_bye": bool(bp.on_bye_week),
                        "game_state": state.get(pro, "bye"),
                    })
            if m.away_team and self.my_id in (m.home_team.team_id, m.away_team.team_id):
                opp = m.away_team if m.home_team.team_id == self.my_id else m.home_team
                matchup = {"my_team_id": self.my_id, "opponent_id": opp.team_id}
        if matchup:
            for key, tid in (("me", matchup["my_team_id"]), ("opponent", matchup["opponent_id"])):
                matchup[key] = tally([p for p in players if p["fantasy_team_id"] == tid])
        return {"week": self.week, "games": games, "players": players, "matchup": matchup}

    # ---------- rosters
    def fetch_rosters(self) -> dict:
        with self.league_lock:
            self.league.refresh()
            teams = [{
                "team_id": t.team_id,
                "name": ec.team_name(t),
                "abbrev": t.team_abbrev,
                "wins": t.wins, "losses": t.losses, "ties": t.ties,
                "standing": t.standing,
                "points_for": round(t.points_for, 2),
            } for t in self.league.teams]
        injuries = {}
        for g in self.groups["live"].get()["data"]["games"]:
            if g["state"] == "post":
                continue
            r = self.http.get(f"{SITE_API}/summary", params={"event": g["id"]}, timeout=10)
            r.raise_for_status()
            for t in r.json().get("injuries", []):
                ab = team_abbr(t["team"]["abbreviation"])
                injuries[ab] = [{
                    "name": i["athlete"]["displayName"],
                    "position": i["athlete"].get("position", {}).get("abbreviation"),
                    "status": i.get("status"),
                } for i in t.get("injuries", []) if i["athlete"].get("position", {}).get("abbreviation") in SKILL_POS]
        return {"teams": teams, "nfl_injuries": injuries}

    # ---------- static
    def fetch_static(self) -> dict:
        st = self.report.stat()
        return {"report": str(self.report.relative_to(ROOT)), "mtime": st.st_mtime, "size": st.st_size}

    def set_intervals(self, new: dict) -> dict:
        for k, v in new.items():
            if k in self.groups:
                lo, hi = LIMITS[k]
                self.groups[k].interval = int(min(hi, max(lo, float(v))))
        return self.config()

    def config(self) -> dict:
        return {"intervals": {k: g.interval for k, g in self.groups.items()},
                "limits": LIMITS, "week": self.week, "my_team_id": self.my_id,
                "report": str(self.report.relative_to(ROOT))}


def tally(rows: list) -> dict:
    """Fantasy score for one lineup: banked (games final), live (in progress),
    and the ESPN projection for starters who haven't played."""
    starters = [p for p in rows if p["starter"]]
    by = lambda s: [p for p in starters if p["game_state"] == s]
    banked, live, left = by("post"), by("in"), by("pre")
    return {
        "banked": round(sum(p["points"] for p in banked), 2),
        "live": round(sum(p["points"] for p in live), 2),
        "score": round(sum(p["points"] for p in banked + live), 2),
        "remaining_projection": round(sum(p["projected"] for p in left), 2),
        "projected_final": round(sum(p["points"] for p in banked + live) + sum(p["projected"] for p in left), 2),
        "to_play": [{"name": p["name"], "pro_team": p["pro_team"], "projected": p["projected"]} for p in left],
        "playing": [{"name": p["name"], "pro_team": p["pro_team"], "points": p["points"]} for p in live],
    }


def latest_report() -> Path:
    files = sorted(REPORTS.glob("*-visual.html")) or sorted(REPORTS.glob("*.html"))
    if not files:
        sys.exit(f"No weekly-matchup report found in {REPORTS}")
    return files[-1]


def make_handler(dash: Dashboard):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet: one line per API error only
            pass

        def send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def json(self, obj, code: int = 200):
            self.send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            force = q.get("force", ["0"])[0] == "1"
            path = url.path.rstrip("/") or "/"
            if path == "/":
                return self.page()
            if path.startswith("/dashboard/"):
                return self.asset(path[len("/dashboard/"):])
            if path == "/api/config":
                return self.json(dash.config())
            if path == "/api/all":
                return self.json({k: g.get(force) for k, g in dash.groups.items()} | {"config": dash.config()})
            group = path[len("/api/"):] if path.startswith("/api/") else None
            if group in dash.groups:
                return self.json(dash.groups[group].get(force))
            self.json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path.rstrip("/") != "/api/config":
                return self.json({"error": "not found"}, 404)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                self.json(dash.set_intervals(body))
            except (ValueError, TypeError) as e:
                self.json({"error": str(e)}, 400)

        def page(self):
            html = dash.report.read_text()
            boot = json.dumps(dash.config())
            html = html.replace("</head>", '<link rel="stylesheet" href="/dashboard/live.css"></head>', 1)
            html = html.replace("</body>", f'<script>window.DASH_BOOT={boot};</script>'
                                           '<script src="/dashboard/live.js"></script></body>', 1)
            self.send(200, html.encode(), "text/html; charset=utf-8")

        def asset(self, name: str):
            f = (ASSETS / name).resolve()
            if f.parent != ASSETS.resolve() or not f.is_file():
                return self.json({"error": "not found"}, 404)
            ctype = {".js": "text/javascript", ".css": "text/css"}.get(f.suffix, "application/octet-stream")
            self.send(200, f.read_bytes(), f"{ctype}; charset=utf-8")

    return Handler


def main():
    p = argparse.ArgumentParser(description="Live weekly-matchup dashboard")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--week", type=int, help="NFL/fantasy week (default: ESPN current week)")
    p.add_argument("--report", type=Path, help="report HTML to serve (default: newest weekly-matchup report)")
    for k, (lo, hi) in LIMITS.items():
        p.add_argument(f"--{k}", type=int, default=DEFAULTS[k], help=f"{k} refresh interval, s ({lo}-{hi})")
    a = p.parse_args()
    intervals = {k: min(LIMITS[k][1], max(LIMITS[k][0], getattr(a, k))) for k in LIMITS}
    report = (ROOT / a.report).resolve() if a.report and not a.report.is_absolute() else a.report
    dash = Dashboard(ec.load_config(), a.week, report, intervals)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(dash))
    print(f"Week {dash.week} dashboard on http://127.0.0.1:{a.port}  "
          f"(report: {dash.report.relative_to(ROOT)}; intervals {intervals})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
