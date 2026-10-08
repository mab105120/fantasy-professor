---
name: team-review
description: Periodic team performance review. Use when the user wants an evaluation of how The Man Wolf is performing over the season so far, wants trends surfaced, or wants to know if anything is concerning enough to act on (via trade, waiver, or lineup changes).
---

# Team Review

## Steps

1. Sync fresh data:
   ```
   python3 tools/espn_client.py sync
   python3 tools/espn_client.py week-stats --week N   # for each week played so far this season
   ```
   `week-stats` only covers one week per call — run it once per completed
   week if `data/week_stats.json` doesn't already have that week's rows.
2. Pull "The Man Wolf" from `data/teams.json`: record (wins/losses/ties),
   `points_for` vs `points_against`, `standing`, streak.
3. Compare `points_for` against the league average (computed across all
   teams in `data/teams.json`) to judge whether results reflect
   underlying scoring strength or luck (e.g. good record but below-average
   points_for suggests a soft schedule and fragility ahead).
4. Per-player: compare `total_points`/`avg_points` against
   `projected_total_points`/`projected_avg_points` for each rostered
   player to flag significant underperformers (drafted/traded-for
   expectations not being met) and overperformers (possible sell-high
   trade candidates). These are season aggregates, so pair them with
   step 5's week-by-week view before concluding anything — a bad
   season average can hide a player who was rostered but not yet
   playing meaningful snaps early, or one who's trending up/down.
5. Pull each rostered player's per-week rows from `data/week_stats.json`
   (filter to weeks where `game_played == 100`, i.e. actually finished —
   see the caveat in the project's data-flow docs) to see the actual
   game-by-game trend behind the season average: is a player's production
   improving, declining, or wildly inconsistent week to week? Use
   `points_breakdown` and `breakdown` to explain *why* (e.g. touchdown-
   dependent scoring vs. a real usage/target-share decline) rather than
   just citing the point totals. This is what distinguishes "bad
   average because of one blowup week" from "actually declining."
6. Check `injuryStatus` across the roster for any lingering issues eating
   into production.
7. Synthesize into:
   - **Where things stand**: record, scoring rank, playoff position
     relative to the top-6 cutoff.
   - **What's working**: players/positions outperforming.
   - **Concerns**: underperforming players, thin positions, bad
     point differential trends, injury risk concentration — be direct
     about anything that should worry the user, don't just deliver good
     news.
   - **Suggested next steps**: point at `trade-analyzer` or waiver
     targets (from `data/free_agents.json`) if a specific weakness
     warrants it.

This is meant to be run periodically (e.g. weekly or after a bad week) —
keep a consistent structure each time so trends are easy to compare across
reviews.
