---
name: espn-sync
description: Refresh league data from ESPN (league settings, all teams' rosters, standings, free-agent/player pool, recent transactions, draft results, power rankings, per-player weekly stat lines) into data/*.json. Use whenever the user asks to sync, refresh, or update league/ESPN data, or as a first step before weekly-lineup, trade-analyzer, team-review, or league-outlook if the cached data looks stale or absent.
---

# ESPN Sync

Refreshes the local data cache from the live ESPN league.

## Steps

1. From the project root, run:
   ```
   python3 tools/espn_client.py sync
   ```
   Any time you need a fuller free-agent pool (e.g. a deep waiver search
   or streaming-defense scan), use a larger pool size:
   ```
   python3 tools/espn_client.py sync --free-agents-size 600
   ```
2. Also pull transaction history (adds/drops/trades):
   ```
   python3 tools/espn_client.py transactions
   ```
   This tracks the datetime of the newest event seen last time
   (`last_synced_ms` in `data/transactions.json`) and pages ESPN's activity
   feed backwards until it reaches that point, so it only needs to cover the
   gap since the last sync rather than guessing a size big enough to not
   miss anything. It merges into the existing file rather than overwriting
   it. If it warns that it hit the page cap before reaching the prior sync
   point (e.g. after a very long gap), re-run with a higher `--max-pages`.
3. Make sure the season's draft board is on disk (needed for draft-ROI and
   "what did they pay for X" questions). It never changes after the draft,
   so once `data/draft_results.json` exists this can be skipped; it's cheap
   and idempotent if run anyway:
   ```
   python3 tools/espn_client.py draft-results
   ```
4. During the season, refresh power rankings:
   ```
   python3 tools/espn_client.py power-rankings
   ```
   With no `--week`, this re-pulls **both the previous week and the current
   week** and merges them into `data/power_rankings.json`. The previous-week
   refresh is essential: ESPN rolls `current_week` forward on Tuesday, so a
   week's rows written mid-week are a partial (or pre-kickoff, all-zero)
   snapshot and only become final once re-pulled after that week's Monday
   game. Never assume the current week's scores are final.
5. During the season, refresh per-player weekly stat lines the same way:
   ```
   python3 tools/espn_client.py week-stats
   ```
   Same previous-week + current-week behaviour and same caveat: the current
   week's rows carry `game_played: 0` and `points: 0` for any player whose
   game hasn't happened yet, and are only final once re-pulled after Monday
   night. This is the only file that records past-week lineups (including
   players since dropped), so it must be kept up to date every sync. To
   backfill or force-refresh one specific week: `week-stats --week N`
   (likewise `power-rankings --week N`).
6. Report what changed vs. before if this isn't the first sync of the
   session (e.g. new week number, roster moves, injury status changes, new
   trades/adds/drops). Say explicitly which week's stats/rankings are final
   and which are still in progress — read that from
   `data/sync_meta.json` (`weeks.<N>.complete`) rather than guessing.
7. If the script errors with an auth failure, the ESPN cookies in
   `config/league_config.json` have likely expired — tell the user they need
   to grab fresh `espn_s2` and `SWID` values from their browser.
8. If it can't find a team matching `team_name` in the config, list the
   teams it did find and ask the user to confirm/correct the name.

Do not edit `data/*.json` by hand — always regenerate via the sync script so
the schema stays consistent with what the other skills expect.
