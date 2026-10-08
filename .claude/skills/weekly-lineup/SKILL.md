---
name: weekly-lineup
description: Weekly start/sit lineup optimizer. Use when the user wants help setting their starting lineup for an upcoming week — choosing between bench players, checking whether a free-agent pickup would beat a current starter, and weighing this week's opponent, matchups, standings implications, and players' current-season performance/injury status.
---

# Weekly Lineup

The question this skill answers: **which nine starters — from the roster or
the free-agent pool — give The Man Wolf the best chance to beat this week's
opponent?**

## How much to trust ESPN projections

ESPN's point projections are a coarse input, not the answer. Through Weeks
1–3 of 2026 a player's projection missed his actual score by ~6 pts on
average; the higher-projected of two RB/WR/TE within 3 pts of each other
outscored the other only ~59% of the time; for D/ST the projection did worse
than a coin flip; and the projected matchup margin missed the real one by
~30 pts. So:

- Use projections to sort players into **tiers**, not to break ties. When
  two options are within the close-call gap, the projection is not a reason
  to prefer either — decide on the evidence in step 4.
- Never rank D/ST by ESPN projection (see step 4).
- Never call a matchup "won" or "lost" from projected totals inside the
  toss-up band.

These figures are re-measured every run (step 2); quote the current ones,
not the ones above, once later weeks are in.

## Steps

1. **Sync.** `python3 tools/espn_client.py sync`, then
   `python3 tools/espn_client.py week-stats --week <W>` where `<W>` is
   `current_week` from `data/league.json`. The current-week rows give ESPN's
   projection for *this* week (`projected_points`), `slot_position`,
   `pro_opponent`, and `on_bye_week` for both fantasy lineups. Also make
   sure every completed earlier week is in `week_stats.json` (check
   `data/sync_meta.json`; backfill with `--week N` if not).
2. **Calibrate.** Run `python3 tools/projection_accuracy.py`. Note the
   per-position hit rates, the close-call hit rate, and the matchup-margin
   std dev — the last sets this week's **toss-up band** (a projected margin
   smaller than it is a toss-up). Use these numbers in the report.
3. **Load the matchup.** From `data/teams.json`: The Man Wolf's roster and
   `waiver_rank`, and this week's opponent (the `schedule` entry with
   `week == W` → `opponent_team_id`). Pull the opponent's current-week rows
   from `week_stats.json`.
4. **Roster, slot by slot.** For each starting slot (1 QB, 2 RB, 2 WR, 1 TE,
   2 FLEX(RB/WR/TE), 1 D/ST — no kicker), compare eligible roster players:
   - **Status**: live injury/designation check per CLAUDE.md; flag
     questionable/out/bye (`on_bye_week`) and name the next-best option.
   - **Tier** from this week's `projected_points` (fall back to
     `projected_avg_points` only if the week's row is missing).
   - **Within the close-call gap**, decide on, in rough order of weight:
     expert consensus weekly rank (e.g. FantasyPros ECR — the averaged
     ranking of many analysts), usage trend from `week_stats.json` breakdowns
     (targets, carries, receptions over recent weeks — volume is steadier
     than points), matchup (`pro_opponent` strength against the position),
     and teammate injuries that shift opportunity. Say which of these
     decided it.
   - **D/ST**: rank on matchup — the opposing offense's sacks and turnovers
     allowed, its implied team total from the betting line if available —
     and expert consensus, not ESPN projection.
5. **Free-agent scan.** For each starting slot, check eligible players in
   `data/free_agents.json` (`eligibleSlots`). Their projections are
   season averages (`projected_avg_points`), so they only nominate
   candidates; a free agent is worth recommending only if expert weekly
   rankings put him clearly above the projected starter (a full tier, not a
   close call), or he fills a bye/injury hole the roster can't. If a
   position looks thin, re-sync with `--free-agents-size 600`. For each
   recommendation state:
   - whether he's a free agent (instant add) or on waivers — this isn't in
     the data, so check ESPN or ask Mo;
   - the cost: a free agent costs only the player dropped; a waiver claim
     "uses your #N priority" (N = `waiver_rank`). Priority resets every
     week to inverse standings, so a claim costs only the drop. Claims
     process early Wednesday, so a player dropped after that run sits on
     waivers until the following Wednesday and can't help this week. Say
     whether the player helps this week or only later;
   - who to drop from the bench, and what that player is worth rest of
     season.
6. **Opponent.** Sum the opponent's projected starters (`slot_position`
   not `BE`/`IR`) against the recommended lineup. Flag opponent starters who
   are injured, on bye, or questionable — their total may be inflated or
   about to change. Then frame the margin against the toss-up band:
   - outside the band, favored → lean toward steady, high-floor options;
   - outside the band, underdog → lean toward high-ceiling, boom-or-bust
     options;
   - inside the band (the usual case) → simply take the best expected
     lineup.
   Combine with standings context: a must-win week for a playoff spot
   tolerates more variance than a comfortable one.
7. **Present.** Slot-by-slot starters with the reason for each; bench
   players who were close calls; each change vs. the current ESPN lineup
   with its projected gain (labelled as a tier-level estimate); free-agent
   moves listed separately with their cost; projected margin vs. the
   opponent before and after, stated against the toss-up band; and the
   step-2 accuracy figures in one line so Mo can see how much weight the
   projections carry this week.
8. **FLEX.** Call out FLEX decisions explicitly since those are usually the
   closest calls. If a start/sit call is genuinely close (a coin flip on
   projection and consensus), *suggest* running `/player-eval <A> vs <B>`
   for a deeper comparison. Don't run it automatically; the user decides.
9. **Save** the report as HTML under `reports/weekly-lineup/week<W>/`, where
   `<W>` is `current_week` from `data/league.json` (refreshed by the sync in
   step 1). Never overwrite an earlier run: each run gets the next number,
   `lineup-report-<n>.html`, where `<n>` is one more than the highest
   existing number in that folder (or 1 if the folder is empty/missing).
   Use the highest number, not a file count, so a deleted report never
   causes an overwrite. Resolve the path with:

   ```
   W=$(python3 -c "import json;print(json.load(open('data/league.json'))['current_week'])")
   DIR="reports/weekly-lineup/week$W"
   mkdir -p "$DIR"
   N=$(ls "$DIR" 2>/dev/null | sed -n 's/^lineup-report-\([0-9][0-9]*\)\.html$/\1/p' | sort -n | tail -1)
   echo "$DIR/lineup-report-$(( ${N:-0} + 1 )).html"
   ```

   Write the report to the printed path and tell the user where it is.

Keep long-term roster strategy out of this skill — it's about the best
lineup for this week. A free-agent pickup is recommended here only for this
week's lineup gain, but the cost of the drop (and of any waiver priority
spent) must still be stated, since that cost outlasts the week.
