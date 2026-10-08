---
name: league-outlook
description: League-wide team-by-team outlook report for the current week and rest of season — short-term strengths/weaknesses/objectives plus long-term risks/opportunities for every team, framed to spot week-over-week shifts useful for trade negotiation. Use when the user wants a read on the whole league (not just The Man Wolf), wants help figuring out who might accept a trade, or wants to track how teams are trending week to week.
---

# League Outlook

Produces one report covering **every team in the league**, not just The Man
Wolf. Distinct from `team-review` (which is Man-Wolf-only and record/roster
focused) — this skill's purpose is reading the *rest of the league* so trade
proposals can be aimed at teams likely to say yes.

## Steps

1. Sync fresh data:
   ```
   python3 tools/espn_client.py sync
   python3 tools/espn_client.py transactions
   python3 tools/espn_client.py power-rankings
   python3 tools/espn_client.py week-stats --week N   # for each week played so far, if missing from data/week_stats.json
   ```
   Re-sync is mandatory here even if data looks recent — this report is
   explicitly about what's *changed*, so stale injury/score data undermines
   the whole point.

2. Determine the current week (scoring period) from `data/league.json` and
   confirm it against the most recent non-zero week in
   `data/power_rankings.json`.

3. For **each team** in `data/teams.json`, gather before writing anything:
   - Record, `standing`, streak, `points_for`/`points_against` vs. league
     average.
   - This week's opponent and matchup, if available from the league data.
   - Full roster with `injuryStatus`/`injured`, `avg_points` vs.
     `projected_avg_points` (recent form vs. expectation) per player, and any
     bye-week players this week. Where a player's role in the report matters
     (a named strength/weakness, not just a roster listing), check their
     recent per-week rows in `data/week_stats.json` (weeks with
     `game_played == 100` only) rather than relying on the season average
     alone — it shows whether they're trending up/down, not just where they
     land on average.
   - Power-ranking history for this team from `data/power_rankings.json`:
     current score vs. prior 1-2 weeks, to characterize direction (rising,
     falling, flat) and whether it agrees or diverges from their W-L record
     (a team winning on a falling power score is fragile; losing on a rising
     score is a buy-low/scary-out target).
   - Recent activity for this team from `data/transactions.json` (adds,
     drops, trades) — read this as a signal of intent (rebuilding/selling
     vs. pushing all-in vs. plugging a bye-week hole) per the project's
     "ground everything in actual league state" principle.

4. Write one section per team, **always in this fixed sub-structure** so
   reports are diffable week over week:

   ```
   ### <Team Name> (<record>, standing #<n>, power rank trend: <↑/↓/→>)

   **This week**
   - Strengths: ...
   - Weaknesses: ...
   - What they'll be looking for this week: (e.g. protecting a lead, needs
     a win to stay playoff-relevant, chasing points for a tiebreak, trying
     to survive a bye-week gap at a position)

   **Rest of season**
   - Risks: ...
   - Opportunities: ...
   ```

   Order teams by current standing (1st to last) so the report reads the
   same way every time.

5. Player-status and consensus rules from the project's global instructions
   still apply here: if a section names a **specific player** as a
   buy-low/sell-high candidate, an injury replacement, or a trade
   angle — not just describing them in passing — verify their current
   health/legal status live (don't trust a stale sync) and note current
   expert consensus on them before asserting the take. Skip this for
   players only mentioned incidentally (e.g. listing a bye-week starter).

6. Close with a short **"Where the trade opportunities are"** roll-up: 2-4
   bullets cross-referencing the sections above — e.g. a team weak at RB
   this week paired with a team whose transaction history shows they're
   deep enough there to move a piece, or a fading team likely open to
   selling a strength for a need elsewhere. This is the payoff section for
   trade targeting — keep it grounded in what was actually observed above,
   not generic advice.

7. If this isn't the first time the report has been run this season, briefly
   flag notable shifts vs. what would reasonably have been true last week
   (e.g. a team's power rank direction reversing, a new injury, a trade that
   changed their needs) rather than re-deriving everything from scratch in
   prose — the user is tracking trends over time.

Keep the tone analytical and direct, matching `team-review`'s standard: call
out real weaknesses and fragility plainly rather than softening bad outlooks,
since the whole point is spotting exploitable trade leverage across the
league.
