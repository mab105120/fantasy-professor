---
name: sunday-recap
description: Live/in-progress game-day recap of Sunday's (or any live slate's) NFL games and their fantasy impact on the D League, written as sports-journalist commentary — not lineup advice. Use when the user wants a "what's happening right now" or "how'd the slate go" read on games in progress or just finished, contrasted against pre-game expectations. Distinct from weekly-lineup (which is a pre-kickoff start/sit decision skill) — by the time this runs, lineups are locked, so the output is color commentary and league-wide storyline tracking, not a decision.
---

# Sunday Recap

A live-slate recap in the voice of a sports journalist/commentator: what's
actually happening across the league's games right now (or just finished),
measured against what was expected going in. This is **not** a
decision-support skill — lineups are already set by the time this runs, so
don't frame anything as start/sit advice (that's `weekly-lineup`'s job,
pre-kickoff). The point is narrative and context: helping Mo follow the
league's story as it unfolds.

## Steps

1. Sync fresh data:
   ```
   python3 tools/espn_client.py sync
   python3 tools/espn_client.py week-stats --week N   # N = current week
   ```
   Mid-slate, `week_stats.json` is a snapshot, not a final result. For every
   player referenced, check `game_played` (100 = game over, 0 = not yet
   played — a game in progress may report partial live stats or may still
   read as 0 depending on what ESPN had synced at that moment; don't assume
   a 0 means "hasn't played" without cross-checking live score context) and
   `on_bye_week` separately, per the project's data-flow caveats. If the
   sync itself lags (ESPN not yet reflecting an in-progress game), say so
   rather than presenting a stale number as current.

2. For live scores, game clock/quarter, and play-by-play color, use web
   search (e.g. ESPN scoreboard) — `data/*.json` is fantasy-league data, not
   NFL live play-by-play, so it won't have this. Search per game as needed
   rather than once for the whole slate, so scores are current at write
   time.

3. The spine of every section is **pre-game expectation vs. what's actually
   happening**: pull `projected_avg_points`/`projected_breakdown` from
   `data/week_stats.json` (captured pre-kickoff) and compare against the
   actual/live line for the same player. A player at 2x their projection by
   halftime is a story; a player at their normal average isn't.

4. Structure the report in this fixed order:

   **Section 1 — The Man Wolf (always first, mandatory).** Opponent, current
   score (live or final), and a player-by-player table for started players:
   actual vs. projected points so far. Close with a projection of how the
   matchup likely finishes — factor in which players on both sides haven't
   played yet and their pre-game projections, not just the current score.

   **Section 2 — Every other league matchup**, one subsection each. For
   each: current/final score, the standout performances (over/under
   pre-game projection), and a closing **"Fantasy impact"** line — what this
   means for the league (standings implications, a player relevant to a
   trade target or waiver watch heating up or busting, a team's playoff
   push helped/hurt). This callout is mandatory per matchup — it's what
   makes the recap useful beyond a scoreboard screenshot.

   **Section 3 — Notable NFL color (optional).** Brief mentions of
   non-league games only if they carry fantasy relevance to players
   rostered somewhere in this league (e.g. a rostered player's team in a
   shootout, a bad weather game affecting a rostered kicker-less-relevant
   skill player). Skip entirely if nothing rostered is affected — this
   section is not a general NFL recap.

5. If a player **leaves a game with an injury** or a new questionable/out
   designation surfaces live, flag it clearly even though this is otherwise
   an observational report — that's live status information Mo needs, not a
   recommendation. This doesn't require the full player-status research
   this project mandates for recommendations (no ranking/starting/trading
   is happening here); just report what's known and flag it as unconfirmed
   if the severity isn't yet clear.

6. Voice: present tense, narrative, alive — write like the game is
   happening as the reader reads it ("X just broke off a 40-yard house
   call"). Every stat claim must still trace back to real data pulled in
   steps 1-3, never invented or estimated to fit the narrative.

7. Output as a single self-contained HTML file under
   `reports/sunday-recap/` (create the directory if it doesn't exist),
   named `YYYY-MM-DD-wNN-sunday-recap.html`. This subfolder — not the
   top-level `reports/` — is where every recap goes. Reuse the modern CSS design system
   already established in `reports/2026-09-19-w02-all-matchups.html` —
   pull its `<style>` block as the base (CSS custom properties with
   light/dark via `prefers-color-scheme`, card/pill/grade components,
   sticky nav) rather than inventing new visual language. Extend it with a
   live-game indicator for anything not yet final — a pulsing "LIVE" pill
   plus quarter/clock — so in-progress and final games are visually
   distinct at a glance. Load the `dataviz` skill before adding any new
   chart/visualization component (e.g. a live win-probability bar) beyond
   what that CSS file already provides.

8. **Do not update `reports/history.md`.** Unlike every other report in
   this project, a Sunday recap is disposable: it's read once and the file
   is expected to be deleted afterwards, so it must not leave a ledger
   entry behind (an entry would just be pruned on the next run anyway).
   Don't append, edit, or "pin" anything in `history.md` from this skill.
   The one exception is information, not the report: if a live injury
   surfaced on a Man Wolf player (step 5), say so plainly in the chat
   reply so Mo can decide whether to log it — but still don't write it to
   the ledger yourself.

Keep it fun and readable — this is the one report in the project that's
meant to feel like a broadcast, not a memo. But "fun" never means
loosening the project's accuracy bar: a bad stat in a punchy sentence is
still a bad stat.
