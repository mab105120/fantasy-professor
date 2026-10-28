#!/usr/bin/env python3
"""
ESPN Fantasy Football connector for the fantasy-professor agent.

Loads league credentials from config/league_config.json and pulls
league settings, teams/rosters, standings, and free agents from ESPN,
writing normalized JSON snapshots into data/.

Usage:
    python3 tools/espn_client.py sync              # pull everything
    python3 tools/espn_client.py sync --free-agents-size 200
    python3 tools/espn_client.py whoami             # sanity check connection
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from espn_api.football import League

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "league_config.json"
DATA_DIR = ROOT / "data"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing config file: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text())


def connect(cfg: dict) -> League:
    return League(
        league_id=cfg["league_id"],
        year=cfg["year"],
        espn_s2=cfg["espn_s2"],
        swid=cfg["swid"],
    )


def team_name(t) -> str | None:
    """Canonical display name for an espn_api Team: whitespace-stripped, since
    ESPN preserves whatever the owner typed (one team here has a trailing
    space). team_id is the join key everywhere; team_name is display-only."""
    return t.team_name.strip() if t is not None and t.team_name else None


def is_my_team(t, cfg: dict) -> bool:
    return (team_name(t) or "").lower() == cfg["team_name"].strip().lower()


def injury_status(p) -> str:
    """espn_api returns [] for players with no injury record (all D/STs);
    normalise to a string so every consumer can do string comparisons."""
    st = getattr(p, "injuryStatus", None)
    if isinstance(st, str) and st:
        return st
    return "ACTIVE" if not getattr(p, "injured", False) else "UNKNOWN"


def refresh_team_names(rows: list, league: League, id_key: str, name_key: str) -> None:
    """Rewrite the team-name column on every row of an accumulating file from
    the live team list, so a mid-season rename propagates through history
    instead of freezing the old name into rows written before it."""
    names = {t.team_id: team_name(t) for t in league.teams}
    for r in rows:
        if r.get(id_key) in names:
            r[name_key] = names[r[id_key]]


def record_sync(league: League, filename: str, weeks: list | None = None, **extra) -> None:
    """Stamp data/sync_meta.json with when `filename` was last written and
    what ESPN's current_week was at the time. The data files themselves are
    plain arrays (consumers depend on that), so freshness lives here.

    For per-week history files, also record each refreshed week and whether
    it was complete at sync time (`complete` = the week was already behind
    current_week, i.e. its Monday game had finished). A week with
    complete=false is an in-progress snapshot and must be re-pulled.

    `extra` adds file-specific fields (e.g. the free-agent pool `size`).
    Keys this function doesn't know (like the sync job's `_job` entry) are
    preserved.
    """
    meta_path = DATA_DIR / "sync_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    now = datetime.now().isoformat(timespec="seconds")
    entry = meta.get(filename, {})
    entry.update({"synced_at": now, "current_week": league.current_week, **extra})
    if weeks is not None:
        wk_meta = entry.setdefault("weeks", {})
        for wk in weeks:
            wk_meta[str(wk)] = {"synced_at": now, "complete": wk < league.current_week}
    meta[filename] = entry
    meta_path.write_text(json.dumps(meta, indent=2))


def owner_to_dict(o) -> dict:
    """Keep only the human-readable bits of an ESPN owner record — the raw
    object also carries the owner's SWID GUID and ~15 notification-settings
    objects, which are PII/noise and were 40% of teams.json."""
    return {k: o.get(k) for k in ("displayName", "firstName", "lastName")}


def player_to_dict(p) -> dict:
    return {
        "playerId": p.playerId,
        "name": p.name,
        "position": p.position,
        "proTeam": p.proTeam,
        "eligibleSlots": p.eligibleSlots,
        "lineupSlot": getattr(p, "lineupSlot", None),
        "injured": p.injured,
        "injuryStatus": injury_status(p),
        "percent_owned": p.percent_owned,
        "percent_started": p.percent_started,
        "total_points": p.total_points,
        "avg_points": p.avg_points,
        "projected_total_points": p.projected_total_points,
        "projected_avg_points": p.projected_avg_points,
        "posRank": getattr(p, "posRank", None),
    }


def team_to_dict(t) -> dict:
    return {
        "team_id": t.team_id,
        "team_name": team_name(t),
        "team_abbrev": t.team_abbrev,
        "owners": [owner_to_dict(o) for o in (t.owners or []) if isinstance(o, dict)],
        "division_name": getattr(t, "division_name", None),
        "wins": t.wins,
        "losses": t.losses,
        "ties": t.ties,
        "points_for": t.points_for,
        "points_against": t.points_against,
        "standing": t.standing,
        "final_standing": t.final_standing,
        "streak_type": t.streak_type,
        "streak_length": t.streak_length,
        "acquisition_budget_spent": t.acquisition_budget_spent,
        "waiver_rank": t.waiver_rank,
        "schedule": [
            {
                "week": i + 1,
                "opponent_team_id": opp.team_id,
                "opponent_team_name": team_name(opp),
                "score": t.scores[i] if i < len(t.scores) else None,
                "outcome": t.outcomes[i] if i < len(t.outcomes) else None,
            }
            for i, opp in enumerate(t.schedule)
        ],
        "roster": [player_to_dict(p) for p in t.roster],
    }


def settings_to_dict(s) -> dict:
    return {
        "name": s.name,
        "team_count": s.team_count,
        "scoring_type": s.scoring_type,
        "scoring_format": [
            {
                "abbr": item.get("abbr"),
                "label": item.get("label"),
                "points": item.get("points"),
            }
            for item in s.scoring_format
        ],
        # Only slots this league actually uses; ESPN returns ~25 with 0s.
        "position_slot_counts": {k: v for k, v in s.position_slot_counts.items() if v},
        "keeper_count": s.keeper_count,
        "playoff_team_count": s.playoff_team_count,
        "playoff_matchup_period_length": s.playoff_matchup_period_length,
        "reg_season_count": s.reg_season_count,
        "trade_deadline": s.trade_deadline,
        "faab": s.faab,
        "acquisition_budget": s.acquisition_budget,
        "median_scoring": s.median_scoring,
        "division_map": s.division_map,
    }


def draft_settings_to_dict(league: League, teams_by_id: dict) -> dict:
    raw = league.espn_request.league_get(params={"view": "mSettings"})
    d = raw.get("settings", {}).get("draftSettings", {})
    pick_order = d.get("pickOrder", [])
    return {
        "type": d.get("type"),
        "order_type": d.get("orderType"),
        "date_ms": d.get("date"),
        "time_per_selection_sec": d.get("timePerSelection"),
        "is_trading_enabled": d.get("isTradingEnabled"),
        "pick_order_team_ids": pick_order,
        "pick_order_team_names": [
            teams_by_id.get(tid, f"team_{tid}") for tid in pick_order
        ],
    }


def sync(cfg: dict, free_agents_size: int) -> None:
    league = connect(cfg)
    DATA_DIR.mkdir(exist_ok=True)

    teams_by_id = {t.team_id: team_name(t) for t in league.teams}

    league_out = {
        "league_id": cfg["league_id"],
        "year": cfg["year"],
        "current_week": league.current_week,
        "settings": settings_to_dict(league.settings),
        "draft": draft_settings_to_dict(league, teams_by_id),
    }
    (DATA_DIR / "league.json").write_text(json.dumps(league_out, indent=2))

    teams_out = [team_to_dict(t) for t in league.teams]
    (DATA_DIR / "teams.json").write_text(json.dumps(teams_out, indent=2))

    free_agents = league.free_agents(size=free_agents_size)
    fa_out = [player_to_dict(p) for p in free_agents]
    (DATA_DIR / "free_agents.json").write_text(json.dumps(fa_out, indent=2))
    for name in ("league.json", "teams.json"):
        record_sync(league, name)
    # pool size matters to the freshness guard: waivers needs the deep pool
    record_sync(league, "free_agents.json", size=free_agents_size)

    my_team = next(
        (t for t in league.teams if is_my_team(t, cfg)),
        None,
    )
    print(f"Synced league {cfg['league_id']} ({cfg['year']}), week {league.current_week}")
    print(f"  {len(teams_out)} teams, {len(fa_out)} free agents written to {DATA_DIR}")
    if my_team:
        print(f"  Your team: {team_name(my_team)} (id {my_team.team_id}), "
              f"{len(my_team.roster)} players on roster")
    else:
        print(f"  WARNING: could not find a team named '{cfg['team_name']}' — "
              f"check config/league_config.json")


def transaction_entries(activities) -> list:
    """Flatten espn_api Activity objects into JSON-serializable rows.

    Each Activity can carry multiple actions (a trade emits one row per side:
    TRADE_SENT from the sending team, TRADE_RECEIVED on the receiving team).
    """
    entries = []
    for act in activities:
        for team, action, player, bid in act.actions:
            team_id = getattr(team, "team_id", None)
            tname = team_name(team) if team else None
            if hasattr(player, "playerId"):
                player_id = player.playerId
                player_name = player.name
            elif isinstance(player, int):
                player_id = player
                player_name = None
            else:
                player_id = None
                player_name = str(player)
            entries.append({
                "date_ms": act.date,
                "team_id": team_id,
                "team_name": tname,
                "action": action,
                "player_id": player_id,
                "player_name": player_name,
                "bid_amount": bid,
            })
    return entries


def transactions(cfg: dict, page_size: int, max_pages: int) -> None:
    """Pull league activity (adds/drops/trades) and merge into
    data/transactions.json, picking up from where the last sync left off.

    ESPN's activity feed has no date filter, only size/offset paging, so this
    pages backwards in `page_size` chunks until it reaches an event at or
    before `last_synced_ms` (the newest event date seen on the previous
    sync) — i.e. it fetches exactly the gap since last time, rather than
    requiring a manually-guessed --size big enough to not miss anything.
    `max_pages` is a safety cap (matters most on the very first sync, when
    there is no prior boundary to stop at).
    """
    league = connect(cfg)
    DATA_DIR.mkdir(exist_ok=True)

    out_path = DATA_DIR / "transactions.json"
    if out_path.exists():
        raw = json.loads(out_path.read_text())
        if isinstance(raw, list):  # migrate from the old plain-array format
            existing_entries, last_synced_ms = raw, 0
        else:
            existing_entries = raw.get("entries", [])
            last_synced_ms = raw.get("last_synced_ms", 0)
    else:
        existing_entries, last_synced_ms = [], 0

    activities = []
    offset = 0
    reached_boundary = False
    for _ in range(max_pages):
        batch = league.recent_activity(size=page_size, offset=offset)
        if not batch:
            reached_boundary = True
            break
        activities.extend(batch)
        if batch[-1].date <= last_synced_ms or len(batch) < page_size:
            reached_boundary = True
            break
        offset += page_size

    new_entries = transaction_entries(activities)

    def key(e):
        return (e["date_ms"], e["team_id"], e["action"], e["player_id"])

    merged = {key(e): e for e in existing_entries}
    added = 0
    for e in new_entries:
        k = key(e)
        if k not in merged:
            added += 1
        merged[k] = e

    # Oldest first, like every other history file in data/.
    all_entries = sorted(merged.values(), key=lambda e: e["date_ms"])
    refresh_team_names(all_entries, league, "team_id", "team_name")
    new_last_synced_ms = max([e["date_ms"] for e in new_entries] + [last_synced_ms], default=last_synced_ms)

    out_path.write_text(json.dumps(
        {"last_synced_ms": new_last_synced_ms, "entries": all_entries}, indent=2
    ))
    record_sync(league, "transactions.json")

    trades = sum(1 for e in new_entries if e["action"] == "TRADE_RECEIVED")
    print(f"Fetched {len(new_entries)} activity rows ({trades} trade sides) across "
          f"{offset // page_size + 1} page(s), {added} new since last sync")
    print(f"  data/transactions.json now has {len(all_entries)} total rows, "
          f"last synced through {datetime.fromtimestamp(new_last_synced_ms / 1000)}")
    if not reached_boundary:
        print(f"  WARNING: hit the {max_pages}-page cap before reaching the prior sync "
              f"point — some activity between syncs may be missing. Re-run with a "
              f"higher --max-pages.")


def draft_results(cfg: dict) -> None:
    """Pull the actual draft board (every pick, in order) and write
    data/draft_results.json.

    This is what actually happened — which player each team took at each
    pick, and whether it was a keeper slot rather than a live pick. It never
    changes after the draft, so one pull per season is enough.
    """
    league = connect(cfg)
    DATA_DIR.mkdir(exist_ok=True)

    # connect() already fetched the draft, and espn_api's refresh_draft()
    # appends to league.draft rather than replacing it — clear first or
    # every pick is written twice.
    league.draft = []
    league.refresh_draft()
    picks = [
        {
            "overall_pick": i + 1,
            "round": p.round_num,
            "round_pick": p.round_pick,
            "team_id": p.team.team_id if p.team else None,
            "team_name": team_name(p.team) if p.team else None,
            "player_id": p.playerId,
            "player_name": p.playerName,
            "keeper": p.keeper_status,
        }
        for i, p in enumerate(league.draft)
    ]
    (DATA_DIR / "draft_results.json").write_text(json.dumps(picks, indent=2))
    record_sync(league, "draft_results.json")

    keepers = sum(1 for p in picks if p["keeper"])
    print(f"Wrote data/draft_results.json: {len(picks)} picks ({keepers} keepers)")


def power_rankings(cfg: dict, week: int) -> None:
    """Pull power rankings for a week and merge into data/power_rankings.json,
    an accumulating history of {week, team_id, team_name, score} rows.

    Power ranking is ESPN's two-game-rolling-average strength score, distinct
    from won-loss record — useful for spotting a team that's stronger/weaker
    than its record suggests.
    """
    league = connect(cfg)
    DATA_DIR.mkdir(exist_ok=True)

    out_path = DATA_DIR / "power_rankings.json"
    existing = json.loads(out_path.read_text()) if out_path.exists() else []

    def key(r):
        return (r["week"], r["team_id"])

    merged = {key(r): r for r in existing}
    weeks = weeks_to_refresh(league, week)
    for wk in weeks:
        # A re-pull replaces the week outright rather than upserting into
        # it, so rows ESPN no longer returns don't linger from an earlier
        # snapshot.
        merged = {k: r for k, r in merged.items() if r["week"] != wk}
        new_rows = [
            {
                "week": wk,
                "team_id": team.team_id,
                "team_name": team_name(team),
                "score": float(score),
            }
            for score, team in league.power_rankings(week=wk)
        ]
        for r in new_rows:
            merged[key(r)] = r
        print(f"Fetched week {wk} power rankings ({len(new_rows)} teams)")

    all_rows = sorted(merged.values(), key=lambda r: (r["week"], -r["score"]))
    refresh_team_names(all_rows, league, "team_id", "team_name")
    out_path.write_text(json.dumps(all_rows, indent=2))
    record_sync(league, "power_rankings.json", weeks)
    print(f"Wrote data/power_rankings.json ({len(all_rows)} total rows across all weeks)")


def weeks_to_refresh(league, week):
    """Weeks a history-accumulating command should (re)pull.

    An explicit --week is used as-is. Otherwise refresh the previous week as
    well as the current one: ESPN rolls current_week forward on Tuesday, so
    a sync run mid-week would otherwise only ever write the in-progress week
    and the just-finished week would be frozen at whatever partial (or
    all-zero, pre-kickoff) snapshot the last sync happened to capture.
    """
    if week is not None:
        return [week]
    cur = league.current_week
    return [w for w in (cur - 1, cur) if w >= 1]


def named_stats(breakdown: dict) -> dict:
    """Drop ESPN's unnamed internal statId keys (e.g. "5", "175") that
    espn_api's PLAYER_STATS_MAP has no name for — they never appear in
    points_breakdown, so they don't affect fantasy scoring and are just
    noise for a stat line."""
    return {k: v for k, v in breakdown.items() if not k.isdigit()}


_DERIVED_STAT = re.compile(r"(PlusYardTD|YardGame|PerAttempt|PerReception|Percentage|Incompletions|TimesSacked)$")


def projected_stats(breakdown: dict) -> dict:
    """Trim ESPN's projection line to the raw counting stats (yards, TDs,
    receptions, targets, attempts, D/ST buckets...) rounded to 2dp. The
    ~30 derived categories it also carries (40+ yard TD odds, 100-yard-game
    odds, yards-per-attempt, completion %) never feed this league's scoring
    and were most of week_stats.json's bulk, as 9-decimal floats."""
    return {
        k: round(v, 2)
        for k, v in named_stats(breakdown).items()
        if not _DERIVED_STAT.search(k) and round(v, 2) != 0
    }


def box_player_to_row(bp, week: int, fantasy_team_id, fantasy_team_name) -> dict:
    return {
        "week": week,
        "player_id": bp.playerId,
        "player_name": bp.name,
        "position": bp.position,
        "proTeam": bp.proTeam,
        "fantasy_team_id": fantasy_team_id,
        "fantasy_team_name": fantasy_team_name,
        "slot_position": bp.slot_position,
        "points": bp.points,
        "breakdown": named_stats(bp.breakdown),
        "points_breakdown": bp.points_breakdown,
        "projected_points": bp.projected_points,
        "projected_breakdown": projected_stats(bp.projected_breakdown),
        "pro_opponent": bp.pro_opponent,
        "on_bye_week": bp.on_bye_week,
        "game_played": bp.game_played,
        "injured": bp.injured,
        "injuryStatus": injury_status(bp),
    }


def week_stats(cfg: dict, week) -> None:
    """Pull every rostered player's fantasy + real stat line for a week and
    merge into data/week_stats.json, an accumulating history of rows (one
    per player per week): fantasy points scored, the underlying real-stat
    breakdown (yards, TDs, receptions, etc.), and the pre-game projection
    for comparison. Free agents aren't included (only players in a lineup
    that week) since box_scores only carries rostered players.
    """
    league = connect(cfg)
    DATA_DIR.mkdir(exist_ok=True)

    out_path = DATA_DIR / "week_stats.json"
    existing = json.loads(out_path.read_text()) if out_path.exists() else []

    def key(r):
        return (r["week"], r["player_id"], r["fantasy_team_id"])

    merged = {key(r): r for r in existing}
    weeks = weeks_to_refresh(league, week)
    for wk in weeks:
        # Replace the week outright: an in-progress week's lineups change as
        # players are added/dropped, and an upsert would leave ghost rows
        # (a dropped player still listed on his old team, or the same
        # player on two teams) from the earlier snapshot.
        merged = {k: r for k, r in merged.items() if r["week"] != wk}
        new_rows = []
        for m in league.box_scores(week=wk):
            home_id = m.home_team.team_id if m.home_team else None
            home_name = team_name(m.home_team) if m.home_team else None
            for bp in m.home_lineup:
                new_rows.append(box_player_to_row(bp, wk, home_id, home_name))
            # Bye-week matchups have no away team/lineup.
            if m.away_team:
                away_id = m.away_team.team_id
                away_name = team_name(m.away_team)
                for bp in m.away_lineup:
                    new_rows.append(box_player_to_row(bp, wk, away_id, away_name))
        for r in new_rows:
            merged[key(r)] = r
        print(f"Fetched week {wk} stat lines ({len(new_rows)} players)")

    all_rows = sorted(merged.values(), key=lambda r: (r["week"], -r["points"]))
    refresh_team_names(all_rows, league, "fantasy_team_id", "fantasy_team_name")
    out_path.write_text(json.dumps(all_rows, indent=2))
    record_sync(league, "week_stats.json", weeks)
    print(f"Wrote data/week_stats.json ({len(all_rows)} total rows across all weeks)")


def whoami(cfg: dict) -> None:
    league = connect(cfg)
    print(f"Connected to: {league}")
    for t in league.teams:
        marker = " <-- you" if is_my_team(t, cfg) else ""
        print(f"  {t.team_id:>3}  {team_name(t)}{marker}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sync_p = sub.add_parser("sync", help="Pull league/teams/free-agents data into data/")
    sync_p.add_argument("--free-agents-size", type=int, default=150)

    sub.add_parser("whoami", help="Verify connection and list teams")

    tx_p = sub.add_parser(
        "transactions",
        help="Pull league activity (adds/drops/trades) since the last sync and "
             "merge into data/transactions.json",
    )
    tx_p.add_argument("--page-size", type=int, default=100,
                       help="events per ESPN API page (default 100)")
    tx_p.add_argument("--max-pages", type=int, default=20,
                       help="safety cap on pages fetched, matters most on first sync (default 20)")

    sub.add_parser(
        "draft-results",
        help="Pull the actual draft board (every pick made, in order) and "
             "write data/draft_results.json",
    )

    pr_p = sub.add_parser(
        "power-rankings",
        help="Pull a week's power rankings and merge into "
             "data/power_rankings.json",
    )
    pr_p.add_argument("--week", type=int, default=None,
                       help="defaults to the previous week and the current week")

    ws_p = sub.add_parser(
        "week-stats",
        help="Pull every rostered player's fantasy + real stat line for a "
             "week and merge into data/week_stats.json",
    )
    ws_p.add_argument("--week", type=int, default=None,
                       help="defaults to the previous week and the current week")

    args = parser.parse_args()
    cfg = load_config()

    if args.command == "sync":
        sync(cfg, args.free_agents_size)
    elif args.command == "whoami":
        whoami(cfg)
    elif args.command == "transactions":
        transactions(cfg, args.page_size, args.max_pages)
    elif args.command == "draft-results":
        draft_results(cfg)
    elif args.command == "power-rankings":
        power_rankings(cfg, args.week)
    elif args.command == "week-stats":
        week_stats(cfg, args.week)


if __name__ == "__main__":
    main()
