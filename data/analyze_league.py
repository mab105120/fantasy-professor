#!/usr/bin/env python3
"""
D League (ESPN 394766) weekly analysis.

Reads the JSON export in this directory and prints every figure the weekly
report needs. Week-agnostic: analyses the latest week present in week_stats.json,
or pass a week number as the first argument.

Usage:  python3 analyze_league.py [week]
"""
import json, sys, os, collections

D = os.path.dirname(os.path.abspath(__file__))
def load(n): return json.load(open(os.path.join(D, n)))

TEAMS = load('teams.json')
WEEK  = load('week_stats.json')
FA    = load('free_agents.json')
TX    = load('transactions.json')
DRAFT = load('draft_results.json')
LEAGUE= load('league.json')

NAME   = {t['team_id']: t['team_name'].strip() for t in TEAMS}
WAIVER = {t['team_id']: t['waiver_rank'] for t in TEAMS}
BENCH  = {'BE', 'IR'}
# Starting slots from league.settings.position_slot_counts (non-bench, non-zero)
SLOTS  = {'QB':1, 'RB':2, 'WR':2, 'TE':1, 'D/ST':1}
FLEX_N = 2
FLEX_ELIGIBLE = ('RB', 'WR', 'TE')

weeks = sorted({w['week'] for w in WEEK})
WK = int(sys.argv[1]) if len(sys.argv) > 1 else weeks[-1]
rows = [w for w in WEEK if w['week'] == WK]
if not rows:
    sys.exit(f"No rows for week {WK}. Weeks present: {weeks}")

by_team = collections.defaultdict(list)
for w in rows: by_team[w['fantasy_team_id']].append(w)

def actual(tid):
    return sum(r['points'] for r in by_team[tid] if r['slot_position'] not in BENCH)

def optimal(tid):
    """Highest-scoring legal lineup from the non-IR roster. Returns (total, picks)."""
    pool = [r for r in by_team[tid] if r['slot_position'] != 'IR']
    byp = collections.defaultdict(list)
    for r in pool: byp[r['position']].append(r)
    for k in byp: byp[k].sort(key=lambda x: -x['points'])
    picks, taken = [], collections.defaultdict(int)
    for pos, n in SLOTS.items():
        for i in range(min(n, len(byp.get(pos, [])))):
            picks.append((pos, byp[pos][i])); taken[pos] += 1
    flex = []
    for pos in FLEX_ELIGIBLE: flex += byp.get(pos, [])[taken[pos]:]
    flex.sort(key=lambda x: -x['points'])
    for r in flex[:FLEX_N]: picks.append(('FLEX', r))
    return sum(r['points'] for _, r in picks), picks

def pending(tid):
    return [r for r in by_team[tid]
            if r['game_played'] == 0 and r['slot_position'] not in BENCH]

print(f"### D LEAGUE — WEEK {WK} — league {LEAGUE['league_id']} · {LEAGUE['year']}")
print(f"### weeks in export: {weeks} · current_week field: {LEAGUE['current_week']}\n")

# --- data-health warnings -------------------------------------------------
warn = []
if all(t['points_for'] == 0 for t in TEAMS):
    warn.append("teams.json results are ZEROED (points_for/wins all 0) — scores below are RECONSTRUCTED from week_stats.")
unplayed = [r for r in rows if r['game_played'] == 0]
if unplayed:
    games = sorted({f"{r['proTeam']}@{r['pro_opponent']}" for r in unplayed})
    warn.append(f"{len(unplayed)} rostered players UNPLAYED ({', '.join(games)}) — flag affected teams.")
if len(DRAFT) != len({(d['round'], d['round_pick'], d['player_id']) for d in DRAFT}):
    warn.append(f"draft_results.json has duplicates ({len(DRAFT)} rows) — deduped below.")
for w in warn: print("!! " + w)
print()

# --- standings ------------------------------------------------------------
act = {t['team_id']: actual(t['team_id']) for t in TEAMS}
print("== STANDINGS (reconstructed) ==")
print(f"{'TEAM':<22}{'SCORE':>9} {'OPPONENT':<20}{'OPP':>9}{'RES':>5}{'ALL-PLAY':>10}  FLAG")
for t in sorted(TEAMS, key=lambda x: -act[x['team_id']]):
    tid = t['team_id']
    m = [s for s in t['schedule'] if s['week'] == WK]
    opp = m[0]['opponent_team_id'] if m else None
    ap = sum(1 for o in act if o != tid and act[tid] > act[o])
    res = '' if opp is None else ('W' if act[tid] > act[opp] else 'L')
    flag = 'PENDING' if pending(tid) else ''
    print(f"{NAME[tid][:20]:<22}{act[tid]:9.2f} {NAME.get(opp,'-')[:18]:<20}"
          f"{act.get(opp,0):9.2f}{res:>5}{f'{ap}-{9-ap}':>10}  {flag}")

# --- lineup efficiency ----------------------------------------------------
print("\n== LINEUP EFFICIENCY ==")
print(f"{'TEAM':<22}{'ACTUAL':>9}{'OPTIMAL':>9}{'EFF':>8}{'LEFT':>8}")
effs = []
for t in TEAMS:
    tid = t['team_id']; o, _ = optimal(tid)
    effs.append((tid, act[tid], o, 100*act[tid]/o if o else 0, o-act[tid]))
for tid, a, o, e, l in sorted(effs, key=lambda x: -x[3]):
    print(f"{NAME[tid][:20]:<22}{a:9.2f}{o:9.2f}{e:7.1f}%{l:8.2f}")
print(f"\nChart scale (max optimal): {max(o for _,_,o,_,_ in effs):.2f}")

# --- start/sit errors -----------------------------------------------------
print("\n== START/SIT ERRORS ==")
for tid, a, o, e, l in sorted(effs, key=lambda x: -x[4]):
    if l < 0.01: continue
    _, picks = optimal(tid)
    started = {r['player_id'] for r in by_team[tid] if r['slot_position'] not in BENCH}
    miss = [(s, r) for s, r in picks if r['player_id'] not in started]
    if not miss: continue
    print(f"\n{NAME[tid]}  (left {l:.2f})")
    for s, r in sorted(miss, key=lambda x: -x[1]['points']):
        print(f"    IN  {s:<9}{r['player_name'][:22]:<24}{r['points']:6.1f}")
    should = {r['player_id'] for _, r in picks}
    for r in sorted([r for r in by_team[tid]
                     if r['slot_position'] not in BENCH and r['player_id'] not in should],
                    key=lambda x: x['points']):
        p = ' [UNPLAYED]' if r['game_played'] == 0 else ''
        print(f"    OUT {r['slot_position']:<9}{r['player_name'][:22]:<24}{r['points']:6.1f}{p}")

# --- positional grid ------------------------------------------------------
print("\n== STARTER POINTS BY SLOT ==")
grid = collections.defaultdict(lambda: collections.defaultdict(float))
for w in rows:
    if w['slot_position'] in BENCH: continue
    p = 'FLEX' if w['slot_position'] == 'RB/WR/TE' else w['slot_position']
    grid[w['fantasy_team_id']][p] += w['points']
cols = ['QB','RB','WR','TE','FLEX','D/ST']
print(f"{'TEAM':<22}" + ''.join(f"{c:>9}" for c in cols) + f"{'TOTAL':>9}")
for tid in sorted(grid, key=lambda x: -act[x]):
    print(f"{NAME[tid][:20]:<22}" + ''.join(f"{grid[tid][c]:9.1f}" for c in cols)
          + f"{act[tid]:9.1f}")
avg = {c: sum(grid[t][c] for t in grid)/len(grid) for c in cols}
print(f"{'LEAGUE AVG':<22}" + ''.join(f"{avg[c]:9.1f}" for c in cols)
      + f"{sum(avg.values()):9.1f}")

print("\n== POSITIONAL NEED (vs league avg) ==")
for tid in sorted(grid, key=lambda x: NAME[x]):
    d = sorted(((c, grid[tid][c]-avg[c]) for c in cols), key=lambda x: x[1])
    print(f"  {NAME[tid][:20]:<22}weak: {d[0][0]} {d[0][1]:+.1f}, {d[1][0]} {d[1][1]:+.1f}"
          f"   strong: {d[-1][0]} {d[-1][1]:+.1f}")

# --- rosters --------------------------------------------------------------
print("\n== ROSTER DEPTH & INJURIES ==")
for t in TEAMS:
    c = collections.Counter(p['position'] for p in t['roster'])
    inj = [p['name'] for p in t['roster']
           if p['injured'] or p['injuryStatus'] not in ('ACTIVE','NORMAL')]
    print(f"  {NAME[t['team_id']][:20]:<22}QB{c['QB']} RB{c['RB']} WR{c['WR']} "
          f"TE{c['TE']} DST{c['D/ST']} ({len(t['roster'])})  inj: {', '.join(inj) or '-'}")

# --- free agents ----------------------------------------------------------
rostered = {p['playerId'] for t in TEAMS for p in t['roster']}
overlap = rostered & {f['playerId'] for f in FA}
print(f"\n== FREE AGENTS ({len(FA)} in pool; roster overlap: {len(overlap)}) ==")
print("WAIVER PRIORITY: " + ' > '.join(
    f"#{WAIVER[t]} {NAME[t]}" for t in sorted(WAIVER, key=lambda x: WAIVER[x])))
for pos in ('RB','WR','TE','QB','D/ST'):
    pool = [f for f in FA if f['position'] == pos]
    print(f"\n-- {pos} — by week points --")
    for f in sorted(pool, key=lambda x: -x['total_points'])[:6]:
        print(f"   {f['name'][:22]:<24}{f['proTeam']:<5}pts={f['total_points']:6.1f} "
              f"own={f['percent_owned']:5.1f}% proj={f['projected_total_points']:6.1f}")
    print(f"-- {pos} — by season projection --")
    for f in sorted(pool, key=lambda x: -x['projected_total_points'])[:4]:
        print(f"   {f['name'][:22]:<24}{f['proTeam']:<5}pts={f['total_points']:6.1f} "
              f"own={f['percent_owned']:5.1f}% proj={f['projected_total_points']:6.1f}")

# --- vs projection --------------------------------------------------------
print("\n== VS PROJECTION (started, played) ==")
played = sorted([w for w in rows
                 if w['slot_position'] not in BENCH and w['game_played'] == 100],
                key=lambda x: -(x['points'] - x['projected_points']))
for label, sl in (('OVER', played[:10]), ('UNDER', played[-10:])):
    print(f" {label}:")
    for w in sl:
        print(f"   {w['player_name'][:22]:<24}{w['position']:<5}"
              f"{NAME[w['fantasy_team_id']][:16]:<18}"
              f"{w['points']:6.1f} vs {w['projected_points']:5.1f}"
              f"{w['points']-w['projected_points']:+7.1f}")

print("\n== BENCHED 15+ ==")
for w in sorted([w for w in rows if w['slot_position'] == 'BE' and w['points'] >= 15],
                key=lambda x: -x['points']):
    print(f"   {w['player_name'][:22]:<24}{w['position']:<5}"
          f"{NAME[w['fantasy_team_id']][:18]:<20}{w['points']:6.1f}")

# --- draft ----------------------------------------------------------------
seen, picks = set(), []
for d in DRAFT:
    k = (d['round'], d['round_pick'], d['player_id'])
    if k in seen: continue
    seen.add(k); picks.append(d)
picks.sort(key=lambda x: x['overall_pick'])
pts  = {w['player_id']: w['points'] for w in rows}
proj = {w['player_id']: w['projected_points'] for w in rows}
print(f"\n== DRAFT ROI — first 24 picks ({len(picks)} deduped) ==")
for d in picks[:24]:
    pid = d['player_id']
    if pid not in pts:
        print(f"{d['overall_pick']:>4} {d['player_name'][:22]:<24}"
              f"{d['team_name'][:18]:<20}  DROPPED"); continue
    print(f"{d['overall_pick']:>4} {d['player_name'][:22]:<24}{d['team_name'][:18]:<20}"
          f"{pts[pid]:7.1f}{proj[pid]:7.1f}{pts[pid]-proj[pid]:+8.1f}"
          f"  {'K' if d['keeper'] else ''}")

# --- transactions ---------------------------------------------------------
print(f"\n== TRANSACTIONS ({len(TX['entries'])}) ==")
for e in sorted(TX['entries'], key=lambda x: x['date_ms']):
    print(f"   {NAME.get(e['team_id'], e['team_name'])[:18]:<20}"
          f"{e['action']:<16}{e['player_name']}")

# --- bench surplus (trade targets) ----------------------------------------
print("\n== BENCH SURPLUS (proj > 120, for trade matching) ==")
for t in TEAMS:
    s = [p for p in sorted(t['roster'], key=lambda x: -x['projected_total_points'])
         if p['lineupSlot'] == 'BE' and p['projected_total_points'] > 120]
    if s:
        print(f"  {NAME[t['team_id']][:20]:<22}" + ', '.join(
            f"{p['name']}({p['position']},{p['projected_total_points']:.0f})" for p in s[:5]))
