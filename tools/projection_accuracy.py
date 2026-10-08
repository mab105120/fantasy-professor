"""How well have ESPN's pre-game projections predicted actual fantasy points
in this league this season?

Reads data/week_stats.json and data/sync_meta.json (completed weeks only) and
data/teams.json (schedules), and prints:
  - per position: typical miss (mean absolute error) and how often the
    higher-projected of two same-position players actually outscored the other
  - the same hit rate for close calls (RB/WR/TE projected within CLOSE_GAP pts)
  - matchup-margin error: how far the actual winning margin landed from the
    projected margin (starters only), which sets the "toss-up" band

Run from the project root: python3 tools/projection_accuracy.py
"""
import itertools
import json
import statistics as st
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
CLOSE_GAP = 3.0
BENCH_SLOTS = {"BE", "IR"}


def main():
    meta = json.loads((DATA / "sync_meta.json").read_text())["week_stats.json"]["weeks"]
    done = {int(w) for w, m in meta.items() if m.get("complete")}
    rows = [r for r in json.loads((DATA / "week_stats.json").read_text())
            if r["week"] in done]
    if not rows:
        print("No completed weeks in week_stats.json yet.")
        return

    played = [r for r in rows if r["game_played"] == 100
              and not r["on_bye_week"] and r["projected_points"] > 0]
    print(f"Completed weeks: {sorted(done)}  player-games: {len(played)}\n")

    def pairwise(rs, lo=0.5, hi=float("inf")):
        hit = tot = 0
        for wk in {r["week"] for r in rs}:
            ws = [r for r in rs if r["week"] == wk]
            for a, b in itertools.combinations(ws, 2):
                gap = abs(a["projected_points"] - b["projected_points"])
                if lo <= gap < hi:
                    tot += 1
                    hit += (a["points"] > b["points"]) == (a["projected_points"] > b["projected_points"])
        return hit, tot

    print(f"{'pos':5} {'n':>4} {'typical miss':>13} {'higher-proj won':>16}")
    for pos in ["QB", "RB", "WR", "TE", "D/ST"]:
        rs = [r for r in played if r["position"] == pos]
        if not rs:
            continue
        mae = st.mean(abs(r["points"] - r["projected_points"]) for r in rs)
        hit, tot = pairwise(rs)
        print(f"{pos:5} {len(rs):4} {mae:10.1f} pts {hit / tot:15.0%}" if tot else f"{pos:5} {len(rs):4} {mae:10.1f} pts {'-':>16}")

    hit = tot = 0
    for pos in ["RB", "WR", "TE"]:
        h, t = pairwise([r for r in played if r["position"] == pos], hi=CLOSE_GAP)
        hit, tot = hit + h, tot + t
    if tot:
        print(f"\nClose calls (RB/WR/TE within {CLOSE_GAP:g} pts): higher-proj won {hit / tot:.0%} of {tot}")

    # Matchup margin error, starters only (bye/unplayed starters count as 0 actual).
    starters = {}
    for r in rows:
        if r["slot_position"] in BENCH_SLOTS:
            continue
        key = (r["week"], r["fantasy_team_id"])
        p, a = starters.get(key, (0.0, 0.0))
        starters[key] = (p + r["projected_points"], a + r["points"])
    errs, seen = [], set()
    for t in json.loads((DATA / "teams.json").read_text()):
        for g in t["schedule"]:
            wk, me, opp = g["week"], t["team_id"], g["opponent_team_id"]
            pair = (wk, frozenset((me, opp)))
            if wk not in done or pair in seen or (wk, me) not in starters or (wk, opp) not in starters:
                continue
            seen.add(pair)
            (mp, ma), (op, oa) = starters[(wk, me)], starters[(wk, opp)]
            errs.append((ma - oa) - (mp - op))
    if len(errs) >= 2:
        sd = st.stdev(errs)
        print(f"\nMatchup margin: actual vs projected margin missed by ±{st.mean(map(abs, errs)):.1f} pts on average "
              f"(std dev {sd:.1f}, {len(errs)} matchups).")
        print(f"Treat a projected margin under ~{sd:.0f} pts as a toss-up.")


if __name__ == "__main__":
    main()
