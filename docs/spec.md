# Fantasy Professor — Product Spec

Status: **draft v0.2** · 2026-10-14 · built from the review + interview of 2026-10-14; §12 open questions resolved same day
Owner: Mo · Scope: the app + agent as a whole, not one feature

This document defines **what** the Fantasy Professor agent and app do. It is
the reference every change is checked against: a new skill, report type, data
file, or UI area that isn't described here gets added to this spec first (or
rejected), so the project doesn't drift back into ad-hoc accumulation.
Implementation choices (framework, file formats in detail, migration steps)
belong in the implementation plan, not here, except where they are product
constraints.

---

## 1. Purpose

A personal in-season assistant for one fantasy team — **The Man Wolf**, ESPN
league 394766 ("D LEAGUE") — made of three parts:

1. **The agent** — a small, fixed set of skills that produce analysis
   (waivers, lineup, matchup preview, week review, trades, player evals).
2. **Season memory** — the agent's continuity: what was done, what was
   decided, what we're watching.
3. **The app** — a local web app that is (a) a **reading room** where every
   skill's output is presented in one consistent design, and (b) a **live
   game-day hub** grounded in this league and specifically in The Man Wolf's
   weekly matchup.

Draft-day work stays out of scope (separate draft agent), as in `CLAUDE.md`.

## 2. Users and environment

- **One user (Mo), one league, one team.** League/team ids can live in
  config, but multi-user, multi-league, auth and hosting are non-goals.
- **Local only.** The app runs on Mo's Mac and is used from the laptop
  browser; it binds to `127.0.0.1`. ESPN cookies never leave the server side.
- **Control surface (v1): Claude Code CLI.** Skills are triggered from the
  CLI; the app displays. **End-state vision: skills can also be triggered
  from the app** (see §10) — v1 must not make that harder.

## 3. Why this redesign (findings from the review)

| Problem today | Consequence |
|---|---|
| 9 skills grown one at a time, overlapping (team-review / league-outlook / old global weekly debrief; waivers' "this week" vs lineup; sunday-recap vs live dashboard) | Unclear which to run and when |
| Each skill hand-writes its own HTML; 3 templates, 2 improvised designs, 2 skills with no defined output | No consistent reading experience; app can only iframe reports |
| Live dashboard scrapes one report's DOM (`g-<away>-<home>` ids, `.pn` names, "ESPN proj" header) | Live view only works on top of the weekly-matchup report |
| Sync steps, status check, consensus rules and scoring rules restated (slightly differently) in every skill | Drift between skills; long, fragile skill files |
| `history.md` logs every report as prose (~56 KB); ~⅓ entries are ad-hoc Q&A | Agent re-reads a long file to find the few things that matter |
| Orphans: `data/analyze_league.py` (script in a cache folder), global `d-league-weekly-report` skill outside the project | Hidden, unmaintained paths |

## 4. Capabilities (the agent)

Seven capabilities replace the current nine skills. Each has one job, a
defined trigger window, a structured output (§6), and a retention rule.

| # | Capability | Question it answers | When | Replaces | Retention |
|---|---|---|---|---|---|
| 1 | **Week in Review** | How did last week's five league matchups play out, what do they mean for The Man Wolf, and where is the trade leverage? | Tue (after MNF is final) | `team-review`, `league-outlook`, global `d-league-weekly-report` | Latest per week |
| 2 | **Waivers** | Who do we claim (use #N vs wait for FA), who do we drop, D/ST stream, stashes | Tue (claims process Wed) | `waiver-wire` | Latest per week |
| 3 | **Lineup** | Which 9 starters (roster or FA) give us the best chance this week | Wed → first kickoff (re-runnable before each window) | `weekly-lineup` + waivers' "this week only" fill-ins | Latest per week |
| 4 | **Matchup Preview** | Full NFL slate through the league lens: schemes, defenses, player cards, Man Wolf + opponent exposure, what to watch | Thu–Sat | `weekly-matchup` (league-lens version) | Latest per week |
| 5 | **Trade Lab** | Evaluate a proposed trade, or build packages for a target/partner | On demand | `trade-analyzer` | **Single slot, overwritten** by next run |
| 6 | **Player Eval** | Deep ROS look at 1–2 players, or a head-to-head with a named winner | On demand | `player-eval` | **Single slot, overwritten** by next run |
| 7 | **Live Hub** | What's happening in our matchup and the league right now | Every game window | dashboard + `sunday-recap` | Not stored (live) |

Notes:
- **Live Hub is an app feature, not a skill.** `sunday-recap` is dropped;
  post-game storylines belong in Week in Review.
- **Week in Review is organised by league matchup, not by team:** five
  sections, one per matchup of the week just played, **The Man Wolf's
  matchup first**, then the other four. Each section describes how that
  matchup's games went for both teams (result, decisive performances vs
  projection, lineup decisions that mattered) and what it signals for each
  team going forward (needs, direction, injuries). It closes with a short
  trade-leverage roll-up drawn from those sections. At strategy checkpoints
  (Weeks 4/8/11) it adds a "strategy vs plan" section measured against
  `strategy.md`.
- **Lineup** absorbs bye/injury fill-ins; Waivers stays rest-of-season.
- **Trade Lab / Player Eval** are disposable working tools. Anything worth
  keeping from them (an offer sent, a rejection, a hold decision) goes into
  season memory (§7), not the report.
- **Ad-hoc Q&A** in the CLI is not recorded as a report and does not get a
  ledger entry by default — only if it produces a memory item (§7) that Mo
  confirms.
- **Sync** stops being a skill the user has to think about (§5).
- Cross-capability hand-offs are *suggestions*, never automatic runs (e.g.
  Lineup suggests Player Eval on a coin-flip FLEX call).

### 4.1 Shared protocols (defined once, referenced by every capability)

Rules currently restated in each skill move into one shared reference that
skills cite rather than copy:

- **Player status check** (mandatory before any player recommendation;
  `UNCONFIRMED` label when it can't be verified).
- **Expert consensus protocol** (trusted-source list, "search until
  consensus is clear, then stop", `AGREE` / `DIVERGE ↑/↓` tagging with a
  reason).
- **League scoring + format** (4-pt pass TD, PPR, no kicker, 10 teams,
  weekly inverse-standings waiver priority — never FAAB).
- **Projection trust** (ESPN projections as tiers, not tie-breakers; current
  figures from `projection_accuracy.py`).
- **Writing standard** (lead with the call; educator voice; define each stat
  on first use; every number traces to data or a cited source; judgment
  calls labelled).
- **Usage computation** (box-score target/carry/snap shares) as a shared
  tool rather than per-run scratch code.

## 5. Data layer and sync

### 5.1 Cache (`data/`)
Unchanged in role: JSON snapshots of league, teams, free agents,
transactions, draft results, power rankings, week stats, plus
`sync_meta.json` for freshness. `team_id` remains the only join key.
Never hand-edited.

### 5.2 Who syncs
- **A scheduled background job** (macOS `launchd`, independent of the app
  and of any skill) is the routine writer of `data/`:
  - light sync every few hours (rosters, injuries, free agents);
  - nightly transactions;
  - a Tuesday post-MNF pass that finalises the previous week's stats and
    power rankings.
  Missed runs (laptop asleep) catch up on wake.
- **Freshness guard in every capability:** each capability declares the
  freshness it needs (e.g. Waivers: deep FA pool < ~6h; Lineup: injuries
  < ~2h before kickoff; Week in Review: previous week `complete: true`). If
  `sync_meta` says the data is older, the capability runs the same sync
  command itself before analysing.
- **One writer at a time:** sync takes a lock so the job and a skill never
  write `data/` concurrently.
- **Live game-day data is not cache.** Scores, situation, play-by-play and
  live fantasy points are polled by the app server while it runs and held in
  memory; they are never written into `data/`.

## 6. Report contract

**Skills emit structured data; the app renders.** Skills stop authoring
HTML.

- Each capability has a **schema** for its output (e.g. Waivers: call
  banner, roster needs, ranked shortlist cards, D/ST stream, stashes, cut
  order, watch list, glossary terms, sources). Content blocks can include
  prose, but structure (players, verdicts, tags, tables) is data.
- A **common envelope** on every report: type, week, created-at, data
  freshness at build time (`sync_meta` snapshot), Man Wolf record/standing,
  subject (for Trade Lab / Player Eval), sources.
- **Player references are ids** (ESPN player id + NFL team), never display
  names, so the live hub and trends can join report content to live data
  without scraping.
- **Status tags** (`ACTIVE`, `Q`, `D`, `O`, `IR`, `SUSP`, `UNCONFIRMED`)
  and **consensus tags** (`AGREE`, `DIVERGE ↑/↓`) are enumerated fields.
- **Storage & retention:**
  - Weekly capabilities (1–4): one report per type per week; a re-run
    replaces it.
  - Trade Lab and Player Eval: one slot each; a new run overwrites.
  - Existing W1–W6 HTML reports are **discarded** at migration (the ledger
    keeps what matters).
- **Delivery: files on the local drive are the interface.** Skills write
  report files into the reports folder; the app's backend watches that
  folder, indexes reports by type and week, and serves them to the
  frontend. Files decouple the two sides: a CLI run produces a report
  whether or not the app is running, and a future UI trigger (§10) runs the
  same skill headlessly and gets the same file.
- **Reports are not committed to git** (gitignored, like `data/`). They are
  regenerable working output.
- The app notices new/changed reports on its own (as the dashboard does
  today) — no manual refresh step.

## 7. Season memory (replaces `history.md` as a report log)

**Purpose: continuity for the agent** — so a new session knows what already
happened and what is still open, without re-deriving it. It is *not* a log
of every report.

**What goes in** (three kinds):

| Kind | Example | Lifecycle |
|---|---|---|
| **Action + outcome** | "Sent Gordon → Imad packages (3); Imad rejected all, 10-13." "Claimed Coleman with #8; won." | Open while awaiting an answer → closed with outcome |
| **Watch item** | "Benched X in W6; watch his snap share. Start him W7 if ≥ 60% snaps." | Has a trigger condition and a revisit week; closed when acted on or dropped |
| **Standing position** | Current bench cut order; "hold Barkley, don't sell"; season posture | Holds until explicitly revised; superseded, not appended |

**Not in:** report summaries, ad-hoc Q&A transcripts, league-owner
"intel" as its own category (owner behaviour is inferred from recorded
action outcomes).

**Write protocol: the agent proposes, Mo confirms.** At the end of a skill
run or conversation, the agent lists proposed memory changes (new items,
outcomes, closures, revisions); nothing is written without Mo's OK.

**Read protocol:** every capability reads open actions, open watch items and
current standing positions before analysing, and asks about any open action
whose outcome it can't settle from `transactions.json`.

**Format: a structured file** (entries with kind, status, subject players
by id, trigger/revisit week for watch items, timestamps), kept
human-readable and diff-friendly. Schema in the implementation plan.

**Committed to git.** Unlike reports and `data/`, season memory is the
durable record of the season and is versioned.

**Relationship to `strategy.md`:** the strategy doc stays a separate,
human-written document (posture, keeper math, roster philosophy,
checkpoints). Standing positions in season memory are concrete, current
calls (cut order, "hold Barkley"), not strategy.

**Not shown in the app.** Season memory is agent-facing only.

## 8. The app

Local web app built on a modern framework (backend API + component-based
frontend; specific choice in the implementation plan). Two areas.

### 8.1 Reading room
- **Organised by week (timeline).** Each week shows the reports that exist
  for it; no expected-report checklist. Trade Lab and Player Eval each have
  their single current slot.
- Every report type renders from its schema in **one consistent design**
  (dark-mode friendly; readable at laptop width). Shared components: verdict
  banner, player row/card with status + consensus tags, ranked cards,
  before/after lineup table, glossary, sources.
- **Trends page** (computed by the app from `data/` + stored reports):
  - **Scoring & luck** — points for/against vs league average; all-play
    record.
  - **Lineup efficiency** — actual vs optimal lineup points per week
    (computable from `week_stats.json`; no extra fields recorded by skills).
  - **League standing** — standings, power-rank trend, playoff position for
    every team.
- Not in v1: player pages, team pages (considered, not selected).

### 8.2 Live game-day hub
- **Independent:** works every game window (TNF, Sunday, SNF, MNF,
  international) from live ESPN data alone; no report required.
- **Enriched:** if a Matchup Preview and/or Lineup report exists for the
  week, its analysis (player-card notes, expectations, lineup rationale) is
  layered onto the same cards via player-id joins.
- **Layout modelled on today's dashboard:**
  - Man Wolf vs opponent score panel at the top (live tally, projected
    finish, who's left to play).
  - A **league scores strip**: all five league matchups' live scores and
    projected finishes.
  - **One component per NFL game**, with live state (score, clock,
    possession, field position, drive, win probability, recent plays).
  - Under each game, the league's fantasy players in it — **Man Wolf and
    this week's opponent first, then other teams' starters only** — with
    live points, points breakdown, field state, last-play flash, and each
    player's fantasy-matchup score.
- Polling intervals configurable; ESPN hit at most once per interval
  regardless of open tabs (as today).

## 9. Non-goals (v1)

- Triggering skills from the UI (end-state goal, §10).
- Multi-user, multi-league, authentication, cloud hosting, mobile layout.
- Showing or editing season memory in the app.
- Player pages and team pages.
- Advice-accuracy tracking (how start/sit and waiver calls held up);
  lineup efficiency covers this need for now.
- A live commentary/recap report.
- Draft assistance.
- Converting old reports.

## 10. End state beyond v1 (design constraint now)

Mo will eventually trigger capabilities from the app (pick an action, fill
a few parameters, watch progress, see the report appear). To keep that
cheap, v1 capabilities must be:
- **parameterised** — explicit inputs (week, players, trade partner/
  package) rather than relying on free-form conversation;
- **headless-runnable** — completable without interactive back-and-forth
  except the season-memory confirmation, which must be representable as a
  pending proposal the user approves later;
- **observable** — emit progress/status that a UI could show.

## 11. Success criteria for v1

1. **Fewer, clearer skills** — Mo can name every capability, its purpose
   and when to run it, from one page of docs.
2. **One app for all output** — every report renders in the app in one
   consistent design; no loose HTML files.
3. **Hub works every week** — the live hub works in every game window
   without a report having been run.
4. **Season memory works** — the agent reliably knows outcomes, open watch
   items and standing positions at the start of any session without
   re-deriving them.

## 12. Resolved questions (2026-10-14)

| # | Question | Resolution |
|---|---|---|
| 1 | Season memory format | Structured file (§7) |
| 2 | `strategy.md` vs standing positions | Strategy stays a separate doc (§7) |
| 3 | Advice-accuracy inputs | Deferred; trends limited to lineup efficiency (plus scoring & luck, standings) |
| 4 | Week in Review length | Organised by the 5 league matchups, Man Wolf first (§4) |
| 5 | League scores in the hub | Yes, a league scores strip (§8.2) |
| 6 | Git policy | Season memory committed; reports gitignored; app reads report files from local disk (§6) |
| 7 | Global `d-league-weekly-report` skill | Remove entirely. It is synced from Mo's claude.ai account, so it must be deleted there (Settings → Capabilities → Skills); deleting the local copy would be re-synced |
| 8 | `CLAUDE.md` rewrite | Agreed; part of the implementation |

No open questions remain; next step is the implementation plan.

## Appendix A — Interview decisions (2026-10-14)

| Topic | Decision |
|---|---|
| Users | Just Mo, this league |
| Core job | Reading room + live game-day hub (not a decision cockpit) |
| Hosting | Local, laptop only |
| Existing skills | Consolidate & redesign |
| Outputs to keep | All four families (waivers/lineup, preview, trade/player eval, review/outlook) |
| Triggering | CLI in v1; UI triggering is the end-state vision |
| Ad-hoc Q&A | Not recorded |
| Ledger | Agent continuity: actions+outcomes, watch items, standing positions; agent proposes, Mo confirms; not in the app |
| Reading room nav | By week (timeline), no checklist |
| Cross-report views | Week-over-week trends: scoring & luck, lineup efficiency, league standing; advice accuracy deferred; no player/team pages |
| Live hub | Modelled on today's dashboard; independent of reports, enriched when they exist |
| Output form | Structured data, app renders |
| Retention | Latest per type per week; Trade Lab / Player Eval single overwritten slot; old reports discarded |
| Review skills | team-review + league-outlook merge into weekly Week in Review, organised by the 5 league matchups (Man Wolf first) |
| sunday-recap | Dropped |
| Sync | Scheduled launchd job + per-capability freshness guard; live data in app memory only |
| Stack | Modern framework (choice in implementation plan) |
| weekly-matchup edit | Accidental; restored to committed league-lens version |
| Season memory | Structured file, committed to git; `strategy.md` stays separate |
| Reports in git | Not committed; app reads them from local disk |
| Hub league strip | Yes, all five league matchup scores |
| Global weekly-report skill | Remove (delete from claude.ai skills) |
| `CLAUDE.md` | Rewrite to match the spec |
