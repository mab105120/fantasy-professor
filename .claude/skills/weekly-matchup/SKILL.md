---
name: weekly-matchup
description: Full-slate NFL weekly matchup report viewed through the D League lens — for every NFL game in a week, each team's offensive scheme (run/pass tendencies, offensive line), run and pass defense, and player cards for the skill players who matter, prioritising The Man Wolf's players, this week's fantasy opponent, and waiver-wire names, with expectations stated in this league's scoring and a closing "what to watch" section. Use whenever the user asks for an NFL weekly report, a full-slate preview, a breakdown of "this week's" or "week N" NFL games, or "who should I watch for in the Sunday slate". Not for setting the lineup (weekly-lineup) or deep single-player evaluation (player-eval).
---

# NFL Weekly Matchup Report

## What this produces

One self-contained HTML report covering an NFL week — every game, both teams,
and the skill players who'll touch the ball — read through the lens of the
D League (id 394766) and The Man Wolf. The NFL matchups are the subject; the
league is why they matter. A full slate is 13-16 games, each needing several
rounds of research, so budget tool calls and work systematically — a thin
report defeats the purpose.

This is a **preview, not a decision**. It surfaces matchup signals ("Tuten
faces the league's worst run defense"); actual start/sit calls belong to
`/weekly-lineup`, and deep player comparisons to `/player-eval`. Suggest those
where a signal points at a real decision — don't run them automatically.
Never frame anything as betting advice.

Follow `CLAUDE.md` throughout: educator voice (define each stat or jargon term
— snap share, target share, aDOT, pressure rate, stuff rate, EPA, etc. — in a
plain-language line the first time it appears), evidence over hype, and
`team_id` as the only join key across `data/*.json`.

## Step 1: Refresh and load league context

1. Read `reports/history.md` (open decisions, injury notes, players Mo is
   watching) and `strategy.md` (current roster philosophy). Ask about any
   `OUTCOME: pending` entry that bears on this week before relying on it.
2. Sync fresh data (rosters and injuries change daily):
   ```
   python3 tools/espn_client.py sync
   python3 tools/espn_client.py transactions
   ```
   Check `data/sync_meta.json` for freshness and `complete` flags before
   treating any week's stats as final.
3. Build the league map from `data/teams.json` (+ `data/free_agents.json`):
   - **Week:** `current_week` from `data/league.json`, unless the user names
     another week.
   - **The Man Wolf's roster**, with each player's `proTeam`, `lineupSlot`,
     `injuryStatus`.
   - **This week's fantasy opponent:** The Man Wolf's `schedule` entry for
     the week → `opponent_team_id` → that team's roster.
   - **Every other rostered player**, keyed by `proTeam`, tagged with their
     fantasy team (for league-wide notes).
   - **Waiver-relevant free agents:** the higher-`percent_owned` /
     `projected_avg_points` names in `free_agents.json` at positions where
     The Man Wolf is thin (per `history.md` / `strategy.md`).

   This map drives player selection (Step 3) and matchup ordering (Step 4).

## Step 2: Pin down scope

1. **Schedule.** Get the week's NFL games with a web search for the official
   schedule (e.g. "NFL week 4 2026 schedule" on NFL.com or ESPN). Cross-check
   against `pro_opponent` in `data/week_stats.json` if that week has been
   synced. Note bye teams — and which league-rostered players (especially
   Man Wolf starters) are on bye.
2. **Full slate or a subset.** Default is every game. If the user narrows it
   ("only games with my players", "just SNF"), honour that. If a request is
   ambiguous in a way that changes the whole job, ask one quick question;
   otherwise proceed.

## Step 3: Research each matchup

**Trusted sources only** (per `CLAUDE.md`): team stats and splits from
Pro-Football-Reference, ESPN, NFL.com / Next Gen Stats, TeamRankings; line
and advanced data from PFF, FTN, Sharp Football Analysis; depth charts from
ESPN / Ourlads / team sites; injury reports from the official team/NFL
reports and established beat writers; expert rankings and previews from
FantasyPros consensus and ESPN / Yahoo / CBS / The Athletic / PFF analysts.
No content farms, aggregator spam, or unsourced social posts. Track which
sources work and note them in the ledger entry (Step 6) so future runs
waste fewer searches.

**Per team, quantitative:**
- Record, points scored/allowed per game.
- Offensive scheme: pass rate vs. run rate (and pass rate over expected if
  available), notable game-script shifts.
- Offensive line: sack rate / pressure rate allowed; a run-blocking
  indicator (stuff rate, yards before contact) if available.
- Run defense: yards per carry and rush yards/game allowed, rank.
- Pass defense: yards per attempt and pass yards/game allowed, rank.
- **Fantasy points allowed by position** (QB/RB/WR/TE) — the most direct
  bridge from NFL matchup to league points.

If a metric isn't published free, use the closest substitute, name it as a
substitute, and move on. Early in the season (Weeks 1-4), say plainly that
the sample is small and lean on prior-season context where relevant.

**Per team, qualitative:** a few sentences synthesised from several expert
previews and the stats above — consensus, not one writer's take. Paraphrase
throughout; any direct quote stays under 15 words with attribution.

**Player cards — who gets one:**
- **Always:** every Man Wolf player (starters and bench) whose team plays.
- **Always:** the fantasy opponent's likely starters.
- **Waiver names** from the Step 1 map whose matchup or role this week makes
  them worth watching.
- Other skill players (QB/RB/WR/TE) likely to see meaningful snaps — scaled
  to the team, not the full depth chart. Mark each with the fantasy team
  that rosters them, or "FA".
- D/STs: a one-line note on each defense's fantasy outlook (pressure rate,
  turnovers, opponent's sack/INT tendency). No kickers — the league has none.

**Each card covers:**
- **Status (mandatory, live):** injury designation, practice participation,
  likelihood of missing games, and any legal/suspension issue — from a live
  news/injury-report lookup, not only the cached `injuryStatus`. If status
  can't be confirmed, say so on the card. A player with a real question mark
  is never shown as a confident play.
- Role: what to watch for in this specific game.
- Usage: snap share, target or carry share, recent stat lines (use
  `data/week_stats.json` for league players' recent weeks).
- Expectation in **this league's scoring** — 4-pt passing TDs (QBs worth
  less than in 6-pt leagues), full PPR (volume receivers gain), 6-pt
  rush/rec TDs, −2 per INT and per fumble lost — tied to the opponent's
  defensive profile. Compare against ESPN's projection
  (`projected_avg_points`) and say whether the matchup argues for beating
  it or falling short.
- **Consensus:** for Man Wolf players, opponent starters, and waiver names,
  state the current expert consensus (FantasyPros weekly rank / start-sit
  consensus) and whether this report's read agrees or diverges, and why.
  Search enough to find the consensus, then stop.

## Step 4: Keep working notes

Keep a running markdown scratch file in the session scratchpad directory,
one section per matchup as you finish it, so the final step is a formatting
pass rather than a re-write, and progress survives a long run.

## Step 5: Assemble the report

Save one self-contained HTML file to `reports/weekly-matchup/` (create the
folder if needed), named `YYYY-MM-DD-wNN-weekly-matchup.html`. Reuse the
`<style>` block from `reports/2026-09-19-w02-all-matchups.html` as the base
(CSS custom properties, light/dark via `prefers-color-scheme`,
card/pill/grade components, sticky nav) rather than inventing new visual
language. Load the `dataviz` skill before adding any chart or visual
component beyond what that CSS provides. Static page — no interactivity or
persistent state needed. No team logos or trademarked imagery; team names,
colour accents, and typography only.

**Section order:**
1. **The Man Wolf lens (first, mandatory).** A compact table of every Man
   Wolf player: NFL opponent, matchup grade (favourable / neutral / tough,
   from fantasy-points-allowed and the defensive profile), status, and a
   one-line note. Flag byes, injury questions, and any matchup that
   meaningfully favours a bench player over a starter — with a pointer to
   `/weekly-lineup` or `/player-eval` rather than a verdict. Then the same
   exposure view for this week's fantasy opponent (where their points are
   likely to come from, who's in a tough spot).
2. **Waiver watch.** Free agents whose role or matchup this week makes them
   worth attention, with status and consensus. Frame claims as "use your #N
   priority" (weekly inverse-standings waivers, never FAAB) and cross-check `history.md` so
   previously passed names aren't re-pitched without new evidence.
3. **Jump-to-matchup table of contents**, games ordered by league relevance:
   games with Man Wolf players first, then games with the opponent's
   players, then by number of league-rostered players involved.
4. **One section per game:** side-by-side team comparison table (offense,
   line, run D, pass D, fantasy points allowed by position), a short
   narrative per team, then collapsible player cards (Man Wolf players
   visually highlighted; every card labelled with its fantasy team or FA).
5. **"Week N: What to Watch"** across the whole slate: statistical
   mismatches, weather-affected games, primetime games, injury situations
   with league-wide fantasy relevance, and what they mean for the D League
   standings picture.

A short glossary box (collapsible) for terms used in the report is welcome,
in addition to first-use definitions inline.

## Step 6: Record in the ledger

Append an entry to `reports/history.md` per its format: date, week, file
name, sync time, and the league-relevant takeaways — Man Wolf matchup
flags, injury statuses found, waiver names surfaced, and any `/weekly-lineup`
or `/player-eval` follow-up suggested. Mark anything Mo needs to act on
`OUTCOME: pending`. Tell Mo where the file is.
