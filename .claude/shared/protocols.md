# Shared protocols — cited by every capability

These rules apply to every skill in this project. Skills reference this file
instead of restating it. `CLAUDE.md` holds the persona and league facts;
`docs/spec.md` defines what each capability does. Where a skill and this file
disagree, this file wins — flag the disagreement.

Run project tools with the venv: `.venv/bin/python tools/fp.py …` (below,
`fp …` for short).

---

## 1. Start of every run

1. **Freshness:** `fp fresh <capability>` (`review`, `waivers`, `lineup`,
   `preview`, `trade`, `player-eval`). It syncs whatever is too stale for that
   capability and says what it refreshed. If it fails, report the error (an
   ESPN-cookie failure says so explicitly) and stop — don't analyse stale data
   silently. `fp sync-status` shows the last scheduled sync.
2. **Season memory:** `fp memory list --open` for live actions, watch items
   and standing positions. Narrow with `--player <id>` / `--team <id>` when the
   run is about specific players or a trade partner. For each open action
   whose outcome you can't settle from `data/transactions.json`, ask Mo.
3. **Strategy:** read `strategy.md` (posture, keeper math, roster philosophy).
4. **Freshness caveats in data:** check `data/sync_meta.json` week entries
   before treating a week as final (`complete: false` = in-progress snapshot);
   `points: 0` in `week_stats.json` is ambiguous until `game_played == 100`;
   `on_bye_week` is separate from "not played yet". `team_id` is the only join
   key; names are display-only.

## 2. Player status check (mandatory before any player recommendation)

Before recommending, ranking, starting/sitting, claiming or trading for any
specific player, verify and state:
- injury designation and practice participation (Wed/Thu/Fri lines),
- likelihood of playing this week, and timeline if out,
- any legal/suspension issue.

Use the team's official injury report or established beat writers;
`injuryStatus` in `data/*.json` can be stale. Tag every player shown with
`ACTIVE`, `Q`, `D`, `O`, `IR`, `SUSP`, or `UNCONFIRMED` (when it can't be
verified). Flag roster-mechanics consequences (e.g. an IR-slot player no
longer OUT can make ESPN block moves).

## 3. Expert consensus

- For every player recommendation, check current expert opinion: FantasyPros
  ECR (primary anchor), ESPN, Yahoo, CBS, The Athletic, PFF analysts,
  established beat writers. Trade value: Yahoo, CBS, FantasyPros charts.
- **Trusted sources only** — no random blogs, content farms, aggregator spam,
  or unsourced social posts.
- Search until the consensus is clear, then stop.
- Tag our read `AGREE`, `DIVERGE_UP` or `DIVERGE_DOWN`, always with the
  reason. Diverging must rest on evidence experts lack or underweight
  (league-specific context, a usage signal, a teammate's return) and is
  labelled a judgment call.
- Record every source used in the report's `sources` (label, url, what it was
  used for).

## 4. League format and scoring (confirmed from ESPN)

- 10 teams, H2H points, **PPR**. Lineup: 1 QB, 2 RB, 2 WR, 1 TE, 2 FLEX
  (RB/WR/TE), 1 D/ST — **no kicker**. Bench 7, IR 2.
- Scoring: **4-pt passing TD**, 0.04/pass yd, 6-pt rush/rec TD, 0.1/rush or
  rec yd, 1/reception, −2 per INT and per fumble lost, 2-pt conversion = 2.
  QBs are worth less than in 6-pt-TD leagues; volume receivers gain from PPR.
- **Waivers: priority resets weekly to inverse standings — not FAAB.** Say
  "use your #N priority", never "bid $X". A successful claim doesn't push us
  down. Claims process early Wednesday (~02:00–03:00 local).
  Observed 2026-10-16, **unconfirmed**: a dropped player clears waivers ~2 days
  after the drop; players whose game has kicked off are held until Wednesday;
  `waiver_rank` can change mid-week.
- Trade deadline 2026-11-25. Playoffs: top 6 by record (points tiebreak),
  Weeks 15–17. Regular season 14 weeks. Rank teams by `standing` or W-L,
  never `final_standing`.
- Keepers: up to 3, flat round-skip cost — a late-round breakout costs no more
  to keep than a first-rounder, so youth with upside is a tiebreaker.

## 5. Projections

ESPN projections are noisy in this league (≈6-pt typical player miss; close
calls ≈57%; D/ST about a coin flip; matchup margin miss ±35–38). Use them as
**tiers, not tie-breakers**; never rank D/ST on them; never call a matchup won
or lost inside the toss-up band. Quote current figures from
`.venv/bin/python tools/projection_accuracy.py`.

## 6. Usage evidence

`fp usage <player_id> [--weeks N]` gives per-game target share, carry share,
team pass attempts and the stat line from ESPN box scores (cached). Use it
instead of ad-hoc box-score scripts. Separate healthy games from impaired
ones; weigh volume trend over one big game; flag TD- or long-play-driven
scoring as likely to regress.

## 7. Writing standard

- **Lead with the call.** The report `headline` is the call in one sentence.
- Educator voice for analysis: every stat or jargon term gets a plain-language
  definition the first time it appears — record it in `glossary`.
- Every number traces to `data/*.json`, an ESPN API pull, or a cited source.
  Never estimate a stat and present it as fact; label judgment calls.
- Keep it scannable: short sentences in cards and tables, no long paragraphs.
- Hand-offs between capabilities are suggestions (e.g. "run `/player-eval A vs
  B`"), never automatic runs.

## 8. Writing the report

Skills write JSON, never HTML. Build the body (`headline`, `subject`,
`sections`, `glossary`, `sources`) and run:

```
fp report write <type> body.json           # validates, fills the envelope, places the file
fp report section <type> --key K piece.json   # long reports: one piece at a time (draft)
fp report finalize <type> [body.json]      # mark the draft final, add headline etc.
```

If validation fails, the error names the exact field — fix and retry. Weekly
reports replace the same week's earlier run; Trade Lab and Player Eval
overwrite their single slot.

## 9. End of every run: season memory proposals

Propose memory changes for anything worth carrying forward — and only that:
- **action**: something done that awaits or has an outcome (trade sent,
  claim made); close it when the outcome is known;
- **watch**: something to check later, with a `trigger` and `revisit_week`;
- **position**: a standing call that holds until revised (cut order, "hold
  Barkley"); revise with a `supersede` op, not a second position.

Not memory: report summaries, Q&A transcripts, things the data already
records. Write the operations to a file, run
`fp memory propose ops.json --source <skill>`, show Mo the list, and run
`fp memory apply <ids>` only for the ones he confirms (`fp memory reject` the
rest). Never apply without confirmation.

## 10. Chat reply

The call in one or two lines (plus whether it matches consensus), the report
path, and the pending memory proposals. Don't repeat the report in chat.
