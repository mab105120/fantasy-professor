---
name: trade-analyzer
description: Trade evaluator and proposal builder. Use when the user wants to evaluate a specific proposed trade, or wants help finding trade targets to fix a roster weakness or pivot to a new strategy.
---

# Trade Analyzer

## Steps

1. Sync fresh data: `python3 tools/espn_client.py sync`.
2. Read `data/teams.json` for every team's full roster (not just the
   user's) — trades need both sides' context.
3. Read `strategy.md` for the roster-construction philosophy, keeper math,
   and the current contend-or-rebuild posture (see its checkpoints). If the
   user's goal for *this* trade isn't obvious from that (e.g. "win now" vs.
   "fix a specific positional hole"), ask before recommending anything.
4. Read `reports/history.md` for trades already proposed/answered so you
   don't re-pitch a dead offer, and `data/draft_results.json` when the
   question is what a team paid to acquire a player (draft capital is a
   real anchor in how owners value their own players).

### Evaluating a specific proposed trade

- Form a rest-of-season evaluation of **every player in the trade** (both
  sides) by consulting current expert opinion — rest-of-season rankings,
  trade-value charts, and analyst notes from reputable sources (FantasyPros
  consensus, ESPN/Yahoo/CBS/The Athletic/PFF analysts, established beat
  writers). Points scored and ESPN projections alone can miss what drives
  future value: role/usage changes, depth-chart moves, remaining schedule,
  injury outlook, and regression signals (e.g. unsustainable TD rate).
  For each player, state the consensus view briefly and whether your
  evaluation agrees or diverges, and why.
- Compare value given up vs. received using that expert-informed
  evaluation alongside `total_points`, `avg_points`, and
  `projected_total_points`/`projected_avg_points` — the numbers are
  inputs, not the verdict.
- Check roster fit on both sides: does this fill a real need (open/weak
  slot) or create a surplus at an already-strong position?
- Check bye-week and injury exposure changes.
- Give a clear verdict: accept / decline / counter, with the reasoning,
  not just a numeric edge.

### Proposing trade targets

- Identify the user's weakest starting slot(s) and thin bench spots.
- Cross-reference other teams' rosters for players who are surplus at a
  position where that team is deep and the user is thin (or vice versa for
  what to offer).
- Propose 2-3 concrete trade packages (specific players both directions),
  ranked by how realistic the other team is to accept (are they actually
  deep enough there to give up value) and how much it helps the user.

Flag anything that looks like a clear win for the other side — don't just
optimize for what helps the user if it's an unrealistic ask.

If the verdict hinges on one or two players whose outlook is genuinely
uncertain or close (e.g. a key player's role after a teammate returns, or
which of two players to cut to make room), *suggest* `/player-eval` for a
deep dive on them. Don't run it automatically; the user decides.

## Write the report (HTML, dark mode)

Every trade evaluation or proposal run ends in a single self-contained HTML
report. The analysis belongs in the report, not the chat.

1. **Design: use `report-template.html`** (in this skill's folder). Copy its
   `<head>`/`<style>` block verbatim, so every trade report shares one
   dark-mode look, and build the body from its components. Use only the
   sections that apply:
   - **Header**: eyebrow ("Trade evaluation · Week N" or "Trade targets ·
     Week N"), a title naming the deal, and meta pills (build time, ESPN
     sync time, our record/standing, partner's record/standing).
   - **Verdict banner** (evaluation mode): `accept` / `decline` / `counter`
     class, the call in one sentence, and a confidence level. Follow it
     with a KPI row: value delta, starting-lineup projection delta, roster
     spots.
   - **The deal**: "You give" / "You get" columns with a player row for
     each player (position badge, status tag, team/bye/consensus rank, avg
     pts), plus the value-balance meter. Name the value source under the
     meter.
   - **Player by player**: a table with status, avg, ROS projection,
     expert consensus, and our read, tagged `AGREE` or `DIVERGE ↑/↓`.
   - **Roster fit**: a before/after lineup table (`class="chg"` on rows that
     change), plus pros/cons lists.
   - **Partner context**: why *this* owner would say yes, using league data
     (standing, positional holes, transaction habits).
   - **Risks** (injury, bye collisions, keeper value), **Counter-offer**
     (when relevant), **Packages** (proposal mode, ranked cards with
     acceptance / helps-us dots), and **Next steps**.
   - A collapsed **Glossary** for every stat term used, and a **Sources**
     footer.

   Keep it scannable. Lead with the call, use short sentences in cards and
   tables, and don't write long paragraphs. Every player shown must carry
   a status tag from the mandatory live status check (`ACTIVE`, `Q`, `D`,
   `O`, `IR`, `SUSP`). If a status couldn't be confirmed, tag it
   `UNCONFIRMED` (`tag q`). Keep the page readable at phone width (the
   template's grids and scrollable tables already handle this).

2. **Where to save: `reports/trade-eval/`** (create it if missing). Name the
   file `YYYY-MM-DD-wNN-<slug>.html`, where `NN` is `current_week` from
   `data/league.json` and `<slug>` is a short kebab-case label for the deal
   (e.g. `kittle-for-evans-johnson`, `wr-targets`). Never overwrite: if the
   name already exists, add `-v2`, `-v3`, … (one more than the highest
   existing version). Resolve the path with:

   ```
   W=$(python3 -c "import json;print('%02d'%json.load(open('data/league.json'))['current_week'])")
   SLUG="kittle-for-evans-johnson"   # set per trade
   DIR="reports/trade-eval"; mkdir -p "$DIR"
   BASE="$DIR/$(date +%F)-w$W-$SLUG"
   if [ ! -e "$BASE.html" ]; then echo "$BASE.html"; else
     V=$(ls "$DIR" | sed -n "s/^$(basename "$BASE")-v\([0-9][0-9]*\)\.html$/\1/p" | sort -n | tail -1)
     echo "$BASE-v$(( ${V:-1} + 1 )).html"; fi
   ```

3. **Ledger:** append an entry to `reports/history.md` as usual, with
   `File: trade-eval/<filename>.html`, the verdict or packages, and
   `OUTCOME: pending` until Mo says whether the offer was sent, accepted,
   or declined.

4. **Chat reply:** give the call in one or two lines (verdict + the main
   reason), then the report path. Don't repeat the full analysis in chat.
