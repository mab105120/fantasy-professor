---
name: waiver-wire
description: Weekly waiver-wire report for The Man Wolf — ranks free agents by rest-of-season value (with a short this-week fill-in section), covering RB/WR/TE adds, a D/ST stream, a QB note, and stashes/handcuffs. Each add says whether to claim on waivers (priority resets weekly to inverse standings) or wait for free agency, and is paired with a drop from a ranked bench cut order. Includes the league angle (competing claims, opponent blocking, recent adds/drops). Use when the user asks for a waiver report, waiver targets, who to pick up/claim/add, who to drop, or a D/ST stream. Not for setting the lineup (weekly-lineup), deep one-player evaluation (player-eval), or trades (trade-analyzer).
---

# Waiver Wire

The question this skill answers: **which unrostered players should The Man
Wolf add this week, what does each one cost (waiver priority and a roster
spot), and who goes to make room?**

**Lens: rest of season first.** Rank candidates on whether they can become a
starter, or protect one, between now and the fantasy playoffs (Weeks 15–17).
Only the separate "This week only" section judges one-week value. "No claim
this week" is a legitimate answer. When nothing clears the bar, say so first.

**When to run:** Tuesday, after Monday night's game is final and before
claims process on **Wednesday**. Other days work too, but adjust the waiver
clock (step 4) to match.

Follow `CLAUDE.md` throughout: use the educator voice, define each stat the
first time it appears, put evidence over hype, use `team_id` as the only join
key, and run the mandatory player-status check.

## 1. Sync and load context

1. Sync with the deep free-agent pool, plus transactions:
   ```
   python3 tools/espn_client.py sync --free-agents-size 600
   python3 tools/espn_client.py transactions
   ```
   If `data/sync_meta.json` shows the just-finished week's `week_stats` as
   missing or `complete: false`, run `week-stats --week <N>` for it.
2. Read `reports/history.md` and `strategy.md`.
   - **Reconcile the last waiver entry.** If a `waiver-wire` entry is
     `OUTCOME: pending`, check `transactions.json` for Man Wolf adds and
     drops since that entry's date. Record what actually happened (claimed,
     added as a free agent, skipped) and mark it resolved. If the
     transactions don't settle it, ask Mo.
   - Pull forward the latest cut order, the players on the watch list,
     and any open roster decisions.
3. From `data/teams.json`, collect:
   - The Man Wolf's roster, `waiver_rank` (call it **#N**), open roster and
     IR spots, and any IR-slot player who is no longer OUT. That can make
     ESPN mark the roster invalid and block adds.
   - Every other team's roster, `waiver_rank`, and record. Step 6 needs
     them.
   - Upcoming byes for our starters (next 3 weeks) and this week's opponent.

## 2. Find The Man Wolf's needs

Before looking at any free agent, write down the needs. Each candidate is
judged against them.
- **Weakest starting slots ROS:** the starters or FLEX options most likely
  to be outscored, judged on usage trend in `week_stats.json` (weeks with
  `game_played == 100`), not season points alone.
- **Depth holes:** use `strategy.md`'s roster philosophy. RB depth is the
  lineup lever. WR starters should be about volume. Stream D/ST. Don't
  overpay at QB or TE.
- **Injury and bye exposure:** injured starters and their timelines, bye
  collisions coming up, and starters with no handcuff (their backup on
  their NFL team) on our roster.

## 3. Build the candidate pool

Use three sources, and **cross-check every name against `teams.json`**.
Expert waiver lists are written for generic leagues, and most of their names
will already be rostered here.
1. **`data/free_agents.json`:** filter by recent production
   (`avg_points`, `total_points`), `percent_owned` trend, `posRank`, and
   `eligibleSlots`. `percent_owned` is ESPN's league-wide ownership, not
   ownership in this league.
2. **`data/transactions.json`:** players dropped in this league over the
   last ~2 weeks. Those drops are both a signal and a source.
3. **Expert waiver columns for this week:** FantasyPros waiver advice and
   ECR, ESPN, Yahoo, CBS, The Athletic, PFF, plus beat writers for role
   news. Trusted sources only. Stop searching once the consensus is
   clear.

Cut the pool down to the most plausible ~8–15 names across positions, then
research only those.

## 4. Vet each finalist

For every player who might appear in the shortlist, the stashes, or the
fill-ins:

- **Status (mandatory, live):** injury designation, practice participation,
  and any legal or suspension issue, checked against the team's official
  injury report or beat writers. If you can't confirm it, label it
  `UNCONFIRMED`.
- **Usage, from box scores:** pull ESPN public-API box scores for the
  player's recent games into the **scratchpad only**, never into `data/`.
  The scoreboard and summary endpoints are listed in `player-eval`
  (`site.api.espn.com/.../nfl/summary?event=<id>`), and `teams/{id}/depthcharts`
  gives the depth chart. Compute shares and a 2–3 week trend: target share,
  carry share, snap and route share where available, and red-zone work.
  Separate healthy games from impaired ones. Volume trend counts for more
  than one big game. Flag any score that rests on touchdowns or a single
  long play as likely to regress.
- **Path to starting:** what has to happen for this player to start for
  us, and how likely it is. That could be a depth-chart change, an injury
  return or absence (with timeline), or a rookie taking over the job.
- **Value in our scoring:** PPR, 0.1 points per rushing or receiving yard,
  6-point rushing/receiving TDs, 4-point passing TDs, −2 per INT or lost
  fumble, no kicker. Give an expected ppg range, labeled as a judgment
  call, and compare it with the player he'd replace.
- **Schedule:** the next 3 weeks plus the playoff weeks (15–17), with
  defense-vs-position ranks. Use the prior season's ranks before about
  Week 5, with a caveat. Note the player's bye.
- **Expert consensus:** ROS rank and waiver priority across at least 2
  sources. Tag our read `AGREE`, `DIVERGE ↑`, or `DIVERGE ↓`, with the
  reason.
- **Keeper tiebreak:** youth only breaks ties when the immediate value is
  a wash (`strategy.md`). It never outranks a clearly better player.
- **Acquisition status (inferred):** ESPN data doesn't say whether a player
  is a free agent or on waivers. Infer it and label it:
  - Players whose NFL game this week has been played are on waivers until
    Wednesday's processing. On a Tuesday run, assume that's almost
    everyone.
  - Players dropped in this league within the waiver period are on
    waivers (check `transactions.json` dates).
  - Otherwise they're `FA`.
  Tag each one `FA` or `WAIVERS (inferred)`, and tell Mo to confirm in the
  ESPN app before acting.

## 5. Apply the priority rule and pair the drops

**Waiver priority spend rule.** Priority resets every week to inverse
standings (confirmed by Mo 2026-10-07): 1st place picks last, and a
successful claim does **not** push us down next week. Claiming costs only
the drop, so the questions are whether he beats our worst bench player and
whether we can realistically win him. **Claim (`USE #N`) when:**
1. He beats the first player on the cut order on ROS value, **and**
2. Waiting is risky: per Step 6, a team **ahead of us in priority**, or a
   free-agent adder, is likely to take him. When nobody else is likely to
   want him, waiting for FA is just as good and keeps the option open.

Put claims in this order: projected **Man Wolf starters ROS** first,
**handcuffs to an injured or fragile Man Wolf starter** next, and stashes
last. When we're high in the standings our priority is late, so expect
to lose contested names and list a fallback for each. Use a conditional
claim (same drop) when only one of two should process.

Everyone else gets **"wait for FA after Wednesday's run"**. If the player
is still there after processing, he costs only the drop. Every candidate
carries one label, `USE #N` or `WAIT FOR FA`, and a one-line reason. When
two claims compete for one priority, rank them.

**Cut order.** Rank the whole bench from first cut to last. For each
player, give ROS value in one line, status, keeper relevance, and why he's
at that spot. Never put a starter on the cut list. Carry forward the
previous cut order from `history.md` and explain any change. Pair each
recommended add with the top of the cut order, unless position needs say
otherwise (keep the bye cover, keep the starter's handcuff), and say so.

## 6. League angle

- **Competing claims:** list the teams ahead of us in waiver priority, and
  for each one, whether it has a need at the position of each `USE #N`
  target (its roster, injuries, and byes). A competitor ahead of us with
  the same need is a reason to claim now rather than wait.
- **Opponent blocking:** flag any free agent who would mainly help this
  week's opponent or one of the next two, such as the replacement for
  their injured starter. Blocking is a tiebreaker only. Never spend #N
  just to block.
- **Recent league activity:** notable adds and drops by other teams since
  the last report, and what each signals (rebuilding, scrambling at a
  position, a role change other teams noticed).

## 7. Report sections, in this fixed order

1. **The call (banner):** either the claims to make in priority order, or
   "Hold: no claim this week, save #N", with the main reason.
2. **Where the roster stands:** needs from step 2, open spots, priority
   #N, and the waiver clock.
3. **Shortlist, ROS-ranked (3–5 cards):** rank, player, status,
   acquisition tag, priority label, usage trend, path to starting,
   expected ppg range, schedule note, consensus tag, risks, paired drop.
4. **This week only:** bye or injury fill-ins for the coming week's
   lineup, plus their cost. Leave start/sit decisions to `/weekly-lineup`.
5. **D/ST stream:** the top 2–3 streaming defenses for this week, ranked
   on opponent sacks and turnovers allowed, the opponent's implied team
   total, and consensus. **Never rank D/ST on ESPN projections.** Name the
   next week's stream too, if it's clear.
6. **QB note:** a short note. Is there a backup or bye answer, a breakout,
   or "no action"? Remember that QBs are worth less with 4-point passing
   TDs.
7. **Stashes and handcuffs (3–5):** players with little value now, held
   for upside or keeper value. Note what would unlock each one.
8. **League angle:** step 6.
9. **Cut order:** step 5.
10. **Watch list:** names that aren't there yet, each with the trigger that
    would make him an add (for example, "≥ 6 targets again in W6").
11. **Glossary** (collapsed) and **Sources**.

If a decision hinges on a close call between two players, *suggest*
`/player-eval A vs B` for the add-or-keep decision. Don't run it
automatically.

## 8. Write and save the report (HTML)

- **Design:** use `report-template.html` in this skill's folder. Copy its
  `<head>`/`<style>` block verbatim and build the body from its
  components. Drop any component that doesn't apply. Every player shown
  carries a status tag. Keep the page readable at phone width.
- Every number must trace back to `data/*.json`, an ESPN API pull, or a
  cited source. Label judgment calls as judgment calls.
- **Where to save: `reports/waiver-wire/`.** Never overwrite. Resolve the
  path with:
  ```
  W=$(python3 -c "import json;print('%02d'%json.load(open('data/league.json'))['current_week'])")
  DIR="reports/waiver-wire"; mkdir -p "$DIR"
  BASE="$DIR/$(date +%F)-w$W-waivers"
  if [ ! -e "$BASE.html" ]; then echo "$BASE.html"; else
    V=$(ls "$DIR" | sed -n "s/^$(basename "$BASE")-v\([0-9][0-9]*\)\.html$/\1/p" | sort -n | tail -1)
    echo "$BASE-v$(( ${V:-1} + 1 )).html"; fi
  ```
  `current_week` is the upcoming week the claims are for. On a Tuesday
  run, ESPN has already rolled it forward.

## 9. Ledger and reply

- Append to `reports/history.md` with `File: waiver-wire/<filename>.html`.
  Include priority #N, the call (claims in order with their drops, or
  hold), the D/ST stream, stashes, the updated cut order, the watch list
  with triggers, and any sources that worked or failed. End with
  `OUTCOME: pending` whenever a claim or add is recommended, and
  `OUTCOME: informational` for a hold. The next run resolves pending
  entries (step 1).
- **Chat reply:** the call in one or two lines (claims and drops, or hold,
  and whether to spend #N), then the report path. Don't repeat the report
  in chat.
