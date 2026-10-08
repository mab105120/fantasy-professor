# Season Strategy — The Man Wolf

Status: **active**, set 2026-08-30 after a 2025 postmortem (5-9 regular season,
9th of 10 by record). Kept **zero** players this season deliberately — full
reset. This doc is the guide for every week's lineup/waiver/trade decisions.
Re-check actual performance against it at the checkpoints below and revise
here (don't just drift) if the plan stops fitting reality.

The 2026 draft is complete (board in `data/draft_results.json`). Draft-day
guidance has moved to the separate draft agent; what remains here is the
roster philosophy the draft was built on, kept because it still steers
waiver and trade decisions.

## Posture: win-now, opportunistic on youth

Goal is the championship **this season**. We are not punting the year for a
rebuild. But "win-now" doesn't mean ignore keeper value — see the keeper math
below, which makes some youth bets nearly free.

Why win-now was viable despite keeping 0 players while 7 of 10 teams kept
1-3: keeper cost in this league is a **flat round-skip by count, not tied to
the round a player was originally drafted** (keep 3 → skip rounds 1-3, keep 2
→ skip rounds 1-2, keep 1 → skip round 1, regardless of who the players are).
Every other team's early draft capital was partially spent before the draft
started, while we drafted with a full, unrestricted set of picks from round 1
on.

## Keeper math (why youth has hidden value all season)

Because the cost of keeping N players next year is always "skip your first N
rounds" — never the specific round a player was drafted in — a **breakout
player acquired cheaply this year (late-round pick, waiver add, trade
throw-in) is nearly free to keep** (costs the same as keeping a round-1 pick
would: next draft's round-1 slot, if kept as the #1 keeper). A veteran costs
proportionally more to keep relative to his output. Implication for waivers
and trades: when two options are a wash for *this* week, prefer the
high-ceiling young player (rookie, 2nd/3rd-year breakout candidate) over the
similarly-projected aging veteran, purely for keeper optionality — it is
close to a free option on next year's team.

Don't let this override the starting lineup: starters are the best players
for this year, full stop. Youth is a tiebreaker for bench spots, not the
deciding factor for who plays.

## Roster construction philosophy (this league's format)

10-team H2H PPR, 1 QB / 2 RB / 2 WR / 1 TE / 2 FLEX(RB-WR-TE) / 1 D-ST, no
kicker, 7 bench, 2 IR. 7 skill-position starters per week, up to 4 of them RB
if we build that way — this format rewards RB depth more than standard
leagues. These were the 2026 draft priorities; they still describe the roster
shape to maintain through waivers and trades.

1. **RB depth is the lineup lever.** Up to 4 RB starting slots (2 RB + 2
   FLEX) means RB depth is a real weekly edge, not just handcuff insurance.
   Buy RB when it's available; don't let the position thin out.
2. **WR: volume over ceiling** for the starting spots — target-share and
   opportunity security over boom-bust upside. 2025's problem wasn't lineup
   management (a perfectly optimal lineup would have only flipped 1 game
   all season, W11), it was that rostered talent (A.J. Brown, Cooper Kupp)
   underperformed/got hurt and there wasn't a strong enough bench floor.
   Boom-bust dart throws belong on the bench, not in the WR1/WR2 slots.
3. **QB: don't overpay.** Single QB slot, no superflex, 4-pt passing TDs —
   a top-10/12 QB is enough; elite RB/WR talent is scarcer than elite QB
   production here. Don't trade real RB/WR value for a QB upgrade.
4. **TE: mid-tier is fine** unless a true elite (top-3) TE can be had
   cheaply — TE1 scarcity is real but not worth premium assets outside the
   top handful.
5. **D/ST: stream, don't invest.** 2025 drafted a D/ST in round 9 that never
   produced — stream defenses off waivers by matchup instead.
6. **Bench construction:** RB/WR handcuffs and high-ceiling young players
   for keeper value (see keeper math above) over a backup QB or a second
   TE.

## In-season management rules

- **Run `/weekly-lineup` every week before games lock, no exceptions.**
  2025's only real, if minor, leak was lineup management (~15 pts/week left
  on the bench on average, one game's worth of margin over the season) —
  cheap to fix by just doing it consistently.
- **Waiver priority favors dual value**: this week's need AND keeper
  upside. A rostered rookie who might be a future keeper beats a
  vet-of-convenience add if the immediate lineup need is a wash.
- **Trade deadline pivot rule**: reassess contention status at the week 9-10
  checkpoint (below). If in contention, use bench/keeper-optional depth to
  buy. If mathematically out, sell expiring/aging veteran value for future
  draft picks or younger keeper-caliber players — don't ride a lost season
  out of inertia.

## Performance checkpoints — measure against this plan, not just the record

- **Week 4**: early read. Are we rostering the RB depth we set out to
  get? Is points-for tracking top-4 in the league? Too early to change
  strategy, but flag drift.
- **Week 8 (midseason)**: the real decision point. If below .500 **and**
  more than 2 games out of the 6th-seed playoff line, pivot from win-now to
  selling veterans for future keeper value for the remaining weeks — update
  this doc when that pivot happens, don't just act on it silently.
- **Week 11 (waiver/trade deadline window)**: last real chance to buy or
  sell. Lock in the contend-or-rebuild call made at week 8 unless something
  material changed (injuries, standings swing).
- **End of season**: full postmortem via `/team-review` — same rigor as the
  2025 review (regular-season standing, not `final_standing`; lineup
  efficiency vs. optimal; draft picks vs. actual production) — to decide
  what carries into next year's keepers and next year's strategy revision.

## Notes for other skills

- `weekly-lineup`: the roster philosophy above is *not* a lineup input —
  start the best players for this week regardless of age or keeper value.
- `trade-analyzer`: weigh proposals against both this year's contention
  status (see checkpoints) and keeper math — a rebuild-mode return should
  price in future draft-round-skip value, not just next week's points.
- `team-review`: check actual weekly points-for rank and lineup efficiency
  against the Week 4 / Week 8 / Week 11 checkpoints above, not just
  win-loss record.
