---
name: player-eval
description: Deep player evaluation report for one or two specific players — health/status, role and volume, efficiency, value in this league's scoring, value over replacement, matchup calendar, teammate/depth-chart risk, expert consensus, and fit with The Man Wolf. Also handles head-to-head comparisons ("X vs Y", "keep X or Y", "who's better rest of season") and names a winner. Use when the user asks to evaluate, break down, or compare specific players. Not for setting a lineup (weekly-lineup) or judging a whole trade (trade-analyzer).
---

# Player Eval

A rest-of-season (ROS) player report, grounded in *this* league, with a
short "this week" note. Model: `reports/2026-09-25-w03-juwan-johnson.html`.

## 0. Pick the mode (from the user's wording)

| Mode | Wording | Output |
|---|---|---|
| **Single** | "evaluate X", "report on X" | Standalone report on one player |
| **Multi** | "reports on X and Y", "look at X, also Y" (no comparison asked) | One combined report: a short summary on top, then a full standalone section per player. No winner. |
| **Compare** | "X vs Y", "X or Y", "keep/start/add/trade for X or Y", "who's better" | One side-by-side report where each dimension has a winner, ending in a **named winner** for the decision |

- **Limit: 2 players per run.** If more are named, ask the user to pick
  two, or offer to run it again for the rest.
- If it's unclear whether the user wants a comparison, ask. Don't guess.
- **Compare mode always names a winner** for a concrete decision: keep vs
  cut, start, trade target, or waiver add. Infer the decision from the
  request and the rosters (e.g. both on our roster with a roster crunch →
  keep/cut). If you can't infer it, ask.
- If the two players play different positions, compare them through the
  lineup slot they'd actually fill (FLEX, bench) and value over replacement.
  Don't compare raw points.

## 1. Load context

1. Sync: `python3 tools/espn_client.py sync` and
   `python3 tools/espn_client.py transactions`. If `data/sync_meta.json`
   shows the last completed week's `week_stats` missing or
   `complete: false`, run `week-stats --week <N>` for it.
2. Read `reports/history.md`. Earlier reports, trade entries, and
   `OUTCOME: pending` items may already cover this player or the decision
   behind the request. Also read `strategy.md`.
3. Locate each player:
   - `data/teams.json` gives the owner (the owner sets the framing: ours →
     hold/sell/start; another team's → trade target, with that team's record,
     depth and needs; free agent → add, using **weekly inverse-standings waiver priority
     #N, never FAAB**).
   - `data/free_agents.json`. If the player isn't there, re-sync with
     `--free-agents-size 600`.
   - `data/week_stats.json` for weekly lines (only exists for rostered
     players). Check `game_played` / `on_bye_week` before reading a 0.
   - `data/draft_results.json` for what the owner paid to get him.
4. Pull NFL data from ESPN's public API **into the scratchpad only**
   (never into `data/`):
   - Team list/ids: `https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams`
   - Schedule and bye: `.../nfl/teams/<id>/schedule?season=<year>`
   - Box scores for each completed game:
     `.../nfl/summary?event=<id>`. Use them to compute **team-level
     shares** yourself (targets ÷ team targets, carries ÷ team carries,
     team pass attempts). Box scores also expose committee partners and
     teammates the headline numbers hide.

## 2. Mandatory live status check (CLAUDE.md)

For every player, confirm the current injury designation, the practice
participation line (Wed/Thu/Fri), game status, any legal or suspension
issue, and contract/job security. Use the team's official injury report
or established beat writers. Don't rely on `injuryStatus` in the cache
alone. If a status can't be confirmed, label it `UNCONFIRMED`.

Flag any **roster-mechanics** consequences, e.g. a player sitting in an IR
slot who is no longer OUT (ESPN can mark the roster invalid and block
moves), or a 2-for-1 that needs a drop.

## 3. Usage, efficiency, and the depth chart

Track these metrics by position, and define each one in plain language the
first time it appears:

| Pos | Role / volume | Efficiency |
|---|---|---|
| WR / TE | snap %, route share, target share, first-read share, aDOT, red-zone targets, slot/inline split | YPRR, TPRR, catch rate, YAC share, yards/target |
| RB | snap %, carry share, target share, route share, red-zone and goal-line carries, 2-min/3rd-down role | yards/carry, yards after contact, missed tackles forced, explosive-run rate |
| QB | dropbacks, pass attempts/game, designed runs + scrambles, red-zone attempts | EPA/play, CPOE, sack rate, TD/INT rate, aDOT |
| D/ST | pressure rate, sacks, takeaways, points allowed | opponent offenses' ranks (the unit's value is mostly its schedule) |

Rules:
- **Separate healthy weeks from impaired ones** (illness, in-game injury,
  snap count). Don't average a limited game into the player's role.
- **Flag regression** where a number can't hold: YAC-driven yardage, TD
  rate far above or below the player's baseline, tiny samples. Give the
  baseline to regress toward (last season, or the career rate in the same
  scheme).
- **Depth chart and teammates:** list committee partners, injured
  teammates due back (with return timelines from beat reporting), and
  incoming competition. **Verify any premise in the user's question**:
  if they assume a teammate's return will hurt the player, check where
  that teammate actually sits on the depth chart before agreeing.

## 4. Expert consensus and quantitative evaluations (required, weighed throughout)

Expert opinion is an input to *every* section, not a closing appendix.
Collect it before writing any verdict.

**Collect, for each player:**
1. **ROS rankings (at least 2 independent sources):** FantasyPros ROS ECR
   (expert consensus ranking, the primary anchor), ESPN, Yahoo, CBS ROS
   ranks.
2. **Trade-value charts:** Yahoo (Justin Boone), CBS (Dave Richard),
   FantasyPros, Roto Street Journal. Record the number *and* where it sits
   among positional peers.
3. **Quantitative / advanced-stat evaluations (at least 1 source):** PFF
   grades and usage data, NFL Next Gen Stats, FantasyPros advanced stats,
   Fantasy Points Data, 4for4, numberFire/FanDuel Research projections,
   ESPN projections (already in `data/*.json`).
4. **Analyst notes:** ESPN (Cockcroft, Bowen, Clay), Yahoo, CBS, The
   Athletic, PFF, FantasyPros writers, and established team beat writers
   for role and injury news.
5. **This week:** consensus weekly positional rank and start/sit lean.

**Only trusted sources.** No random blogs, content farms, aggregator spam,
or unsourced social media. Search until the consensus is clear, then stop.

**How to use it:**
- Every section that makes a claim (role, efficiency, value, matchups)
  says whether experts agree and cites them.
- The report includes a consensus table per player: source → rank/value/
  grade → note. Below it, state the **strength of agreement** (tight vs
  wide spread between sources).
- Our read is tagged `AGREE`, `DIVERGE ↑` or `DIVERGE ↓`, **with the
  reason**. Diverging is allowed, but it must rest on evidence the experts
  don't have or are underweighting: league-specific context, a usage
  signal, a teammate's return. Label it as a judgment call.
- In Compare mode, the verdict states whether the winner is also the
  consensus pick. If not, it explains why we're going against the
  consensus.

## 5. League-specific grounding

- **Scoring:** convert to this league's scoring (PPR, 0.1/yd rush and rec,
  6-pt rush/rec TD, 4-pt pass TD, 0.04/pass yd, −2 INT/fumble lost, no
  kicker, no TE premium). Give **floor / median / ceiling** weekly ranges
  and each one's rough frequency, labeled as judgment calls. Show how much
  of the player's scoring comes from TDs.
- **Value over replacement:** compare with the best free agent at the
  position (`free_agents.json`: avg, ESPN ROS proj, % rostered) and rank
  the player among every rostered player at his position in this league.
  In a 10-team league the waiver floor is high, so say so when the edge is
  small.
- **Matchup calendar:** every remaining NFL opponent with a
  defense-vs-position rank, mapped to The Man Wolf's D League opponent that
  week (`teams.json` schedule). Highlight the bye and the **fantasy
  playoffs (Weeks 15–17: 6 teams, one week per round)**. Before about
  Week 5, use the **prior season's** final defense-vs-position ranks with a
  caveat. From about Week 5 on, blend in or switch to the current season.
  Note the source and whether it's PPR or half-PPR.
- **Roster fit and strategy:** check against `strategy.md` (win-now;
  RB depth is the lever; WR volume over ceiling; don't overpay QB/TE;
  stream D/ST; youth as a bench tiebreaker under the flat round-skip
  keeper cost). Name concrete consequences: who he starts over, who gets
  cut, bye-week clustering with our other players, concentration in one
  NFL offense.
- **League angle:** how the move changes our head-to-head matchups (e.g.
  it takes a player from a future opponent) or a trade partner's
  leverage.

## 6. This-week note (short)

One box: opponent, Vegas spread/total, status, consensus weekly rank, and
a start/sit lean. For our own player, add "confirm in `/weekly-lineup`".

## 7. Write the report (HTML)

**Design:** use `report-template.html` in this skill's folder. Copy its
`<head>`/`<style>` block verbatim and build the body from its components.
Drop any component that doesn't apply.

**Single mode, section order:**
1. Header (name, position, team, owner in the league, date/sync/week)
2. KPI row (league pts/gm + positional rank in league, the key role
   metric, share metric, consensus ROS rank)
3. The short version (ROS tier label, e.g. "low-end TE1", the one-paragraph
   case, what it means for The Man Wolf) + status box
4. Role and volume → 5. Efficiency → 6. Value in our scoring (ranges +
   replacement table) → 7. Matchup calendar → 8. Upside / risk cards →
   9. Fit with The Man Wolf and strategy → 10. Expert consensus vs our
   read → 11. This week → 12. Sources

**Multi mode:** a summary strip up top (one line per player: tier, status,
consensus rank), then the Single sections for each player, one after the
other, each under its own player header.

**Compare mode:**
1. Header ("X vs Y · <decision>")
2. **Verdict banner:** winner, the decision, confidence, and whether it
   matches the consensus
3. Two player cards side by side (status, owner, tier, consensus rank)
4. **Scorecard:** one row per dimension (status/durability, role,
   volume, efficiency, TD equity, league-scoring value, value over
   replacement, schedule ROS, playoff-week schedule, teammate/depth risk,
   expert consensus, strategy/keeper fit, this week) → value A | value B |
   winner. The winner column uses `.win-a` / `.win-b` / `.push`.
5. Side-by-side sections for role, efficiency and value (paired tables,
   not two standalone essays)
6. **Combined matchup calendar:** week | D League opponent | A's NFL opp
   + rank | B's NFL opp + rank, with byes and playoff weeks highlighted
7. Upside/risk per player → consensus table (both players) → why the
   winner wins and what would flip the call → this week → sources

**Writing:** use the educator voice for the analysis, but keep it
scannable, and lead each section with its conclusion. Define every stat
the first time it's used (`.def` box). **Every number must trace back to
`data/*.json`, an ESPN API pull, or a cited source**, so never estimate a
stat and present it as a fact. Label judgment calls as judgment calls.
Every player shown carries a status tag from step 2.

**Where to save: `reports/player-eval/`.** Name the file
`YYYY-MM-DD-wNN-<slug>.html`. The slug is the player
(`juwan-johnson`) or the pairing (`worthy-vs-pittman`,
`evans-and-pittman`). Never overwrite. Resolve the path with:

```
W=$(python3 -c "import json;print('%02d'%json.load(open('data/league.json'))['current_week'])")
SLUG="worthy-vs-pittman"   # set per run
DIR="reports/player-eval"; mkdir -p "$DIR"
BASE="$DIR/$(date +%F)-w$W-$SLUG"
if [ ! -e "$BASE.html" ]; then echo "$BASE.html"; else
  V=$(ls "$DIR" | sed -n "s/^$(basename "$BASE")-v\([0-9][0-9]*\)\.html$/\1/p" | sort -n | tail -1)
  echo "$BASE-v$(( ${V:-1} + 1 )).html"; fi
```

## 8. Ledger and reply

- Append an entry to `reports/history.md`:
  `File: player-eval/<filename>.html`. Include the mode, status, key
  usage numbers, consensus, our read (AGREE/DIVERGE), the verdict or
  winner, and what to watch next. End with `OUTCOME: informational`, or
  `OUTCOME: pending` if it feeds an open decision (a cut, claim, or trade).
- **Chat reply:** the call in one or two lines (tier or winner + the main
  reason, and whether it matches the consensus), then the report path.
  Don't repeat the report in chat.
