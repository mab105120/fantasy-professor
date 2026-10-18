# Fantasy Professor — Implementation Plan

Status: **v0.3** · 2026-10-17 · implements `docs/spec.md` v0.2 · build order, not a calendar · review comments folded in

The spec says *what*; this plan says *how* and *in what order*. Any change to
scope goes into the spec first.

---

## 0. Constraints that shape the plan

- **Fallback, not parallel running.** Before the build starts, the current
  working setup is frozen (step 0 in §7). If anything in the new build
  doesn't work on a given week, Mo uses the frozen copy. So the build does
  not keep old skills alive alongside new ones, and has no calendar gates.
- **Build in dependency order, as fast as possible.** Foundation → app →
  skills → trends, each layer used by the next. Each step ends with an
  acceptance check; the old pieces it replaces are deleted when it passes.
- **Real-world validation without waiting for real weeks:** live parsing is
  tested against ESPN responses recorded once during any game window; new
  skills are run immediately on the current week's real data.
- **Starting point:** PR #1 (`feature/live-dashboard`) merged into `main`.

## 1. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.11) | Reuses `espn_client.py` / `espn_api` and the dashboard's ESPN parsing as-is; async polling; typed models |
| Schemas | **Pydantic v2 models** as the single source of truth | Validate skill output in Python, export JSON Schema, generate TypeScript types from it — one definition, three uses |
| Frontend | **React + TypeScript + Vite** | Most widely known component framework (easiest for the agent and future contributors to maintain); Vite gives a fast dev server and a static build the backend serves |
| Data fetching | TanStack Query | Polling intervals, caching, and refetch-on-focus for the live hub without hand-written timers |
| Charts | Recharts | Enough for the three trend sets; no D3 hand-rolling |
| Tests | pytest (backend, schemas, CLI), Vitest (frontend logic), `tsc --noEmit` | First automated tests in the repo |

Alternative considered: Svelte/SvelteKit (lighter, less boilerplate).
**React confirmed by Mo (2026-10-17).**

Production mode: `npm run build` → FastAPI serves the static bundle on
`127.0.0.1:8765`, one process, started by a script like today's
`dashboard.sh`. Dev mode: Vite dev server proxying `/api` to FastAPI.

## 2. Target repo layout

```
.claude/
  skills/               week-review, waivers, lineup, matchup-preview,
                        trade-lab, player-eval   (6 skills; espn-sync retired)
  shared/               protocols.md — status check, consensus, scoring,
                        projection trust, writing standard (cited by skills)
app/
  backend/              FastAPI app: reports API, live hub service, trends
  frontend/             Vite + React + TS
schemas/                Pydantic models: envelope, one module per report
                        type, season memory; exported JSON Schema
state/
  season.json           season memory (committed)
  proposals.json        pending memory proposals (committed while pending)
tools/
  espn_client.py        unchanged role (ESPN → data/)
  fp.py                 the agent's CLI: report / memory / fresh / usage
  sync_job.py           scheduled sync orchestrator (+ lock)
  launchd/              plist template + install script
  projection_accuracy.py
data/                   cache (gitignored)
reports/                generated reports (gitignored)
docs/                   spec.md, plan.md
strategy.md, CLAUDE.md
```

Removed by the end: `tools/dashboard_server.py`, `tools/dashboard/`,
`tools/dashboard.sh` (replaced by the app), `data/analyze_league.py`,
all `report-template.html` files, `reports/history.md`, all old HTML reports,
skills `espn-sync`, `team-review`, `league-outlook`, `sunday-recap`,
`trade-analyzer`, `waiver-wire`, `weekly-lineup`, `weekly-matchup`.

## 3. Report contract (implements spec §6)

### 3.1 Storage

```
reports/
  w06/  waivers.json  lineup.json  preview.json
  w05/  review.json            # Week in Review is filed under the week it reviews
  lab/  trade.json  player-eval.json   # single slots, overwritten
```

Weekly files are replaced on re-run; lab files are overwritten by the next
run. The backend watches `reports/` and pushes "report changed" to open pages
(server-sent events), replacing today's static-file polling.

Why the watcher: skills run in Claude Code, a separate process, and write
report files to disk; the browser can't see the disk and only knows what the
backend told it when the page loaded. The watcher (OS file-change
notifications) keeps the backend's report index current and pushes a short
"W6 waivers changed" event to open pages, which re-fetch that one report.
It changes *when* the UI learns about a report, not *what* is served. It is
a convenience; a refresh button would also work.

### 3.2 Envelope (every report)

Every report file has this same outer shape (the "envelope"); only
`sections` differs by type. This lets the app list, sort and head any report
without knowing its type. Example:

```json
{
  "type": "waivers", "schema_version": 1, "week": 6,
  "created_at": "2026-10-13T20:28:00-05:00",
  "data_freshness": { "free_agents.json": "2026-10-13T20:19:00-05:00" },
  "man_wolf": { "record": "5-0", "standing": 1, "opponent_id": 3 },
  "headline": "Hold: no claim this week, save #10",
  "sections": { "...": "waivers-specific" },
  "glossary": [], "sources": []
}
```

```
type, schema_version, week, created_at,
data_freshness   (snapshot of sync_meta at build time),
man_wolf         (record, standing, opponent_id for the week),
subject          (lab reports: trade partner/players, eval players),
headline         (the call, one sentence),
sections[]       (type-specific, see 3.3),
glossary[]       ({term, definition}),
sources[]        ({label, url, used_for})
```
- `glossary` implements the educator rule (define every stat on first
  use): the skill lists the terms it used with plain definitions; the app
  renders a collapsible glossary (and can later show hover definitions).
- `sources` implements the expert-consensus rule: every report cites what
  it used (`{"label": "FantasyPros ROS ECR", "url": "…", "used_for": "Kamara
  ROS rank"}`); the app renders a linked sources footer so claims can be
  checked.

Shared building blocks, defined once in `schemas/common.py`:
`PlayerRef {player_id, name, pro_team, position}` (ids are the join key;
names are display-only), `StatusTag` enum (`ACTIVE Q D O IR SUSP
UNCONFIRMED`), `ConsensusTag` (`AGREE DIVERGE_UP DIVERGE_DOWN` + reason),
`Prose` (markdown string, rendered safely), `Verdict` (call, confidence).

All of these are Pydantic classes, e.g.:

```python
class Verdict(BaseModel):
    call: str
    confidence: Literal["low", "medium", "high"]

Prose = Annotated[str, Field(json_schema_extra={"format": "markdown"})]
```

`Prose` is a string marked as markdown so the frontend renders it with
formatting (sanitised). Each class is defined once and used three ways:
`fp` validation, JSON Schema export, generated TypeScript types.

### 3.3 Per-type sections (first cut — finalised in the step that builds each)
This table is the first draft of what goes inside `sections` for each
type. Everything is JSON (nested objects/arrays) and each entry maps to a UI
component; e.g. one waivers `shortlist` item renders as a shortlist card:

```json
{
  "rank": 1,
  "player": { "player_id": 4430737, "name": "Kimani Vidal", "pro_team": "LAC", "position": "RB" },
  "status": "ACTIVE", "acquisition": "WAIVERS", "priority": "USE_N",
  "usage_trend": "Carry share 38% → 52% → 61% over W4–W6",
  "ppg_range": { "floor": 6, "median": 11, "ceiling": 18 },
  "consensus": { "tag": "AGREE", "reason": "…" },
  "paired_drop": { "player_id": 4241478, "name": "…" }
}
```

Field lists are finalised in step 3, when each skill is built.

| Type | Sections |
|---|---|
| `review` | matchups[5] (Man Wolf first): {teams, scores, decisive performances vs projection, lineup decisions that mattered, outlook per team}; trade_leverage[]; checkpoint (W4/8/11 only) |
| `waivers` | call; roster_needs; shortlist[] {player, status, acquisition FA/WAIVERS, priority USE_N/WAIT, usage trend, path to start, ppg range, schedule, consensus, risks, paired drop}; dst_stream[]; qb_note; stashes[]; league_angle; cut_order[]; watch_list[] {player, trigger} |
| `lineup` | slots[] {slot, player, reason, close_call_alt}; changes[]; fa_moves[] with cost; opponent {projected, flags}; margin vs toss-up band; accuracy line |
| `preview` | games[] keyed by ESPN event id {teams, scheme, line, run/pass defense, narrative, player_cards[] {player, role, usage, expectation, league_tag}}; man_wolf_exposure; opponent_exposure; waiver_watch; what_to_watch |
| `trade` | mode eval/proposal; verdict; deal {give[], get[]}; per_player[] {consensus, our read}; roster_fit before/after; partner_context; risks; counter / packages[] |
| `player-eval` | mode single/multi/compare; per player {status, role, efficiency, value ranges, replacement, calendar, consensus}; scorecard (compare); winner |

## 4. The agent's CLI: `tools/fp.py`

One entry point so skills stop re-describing plumbing:

```
fp report path    <type> [--week N]        # where to write; handles retention
fp report write   <type> [--week N] FILE   # validate against schema, then place
fp report section <type> --key K FILE      # merge one section (long reports,
                                           # e.g. one preview game at a time)
fp report validate FILE
fp memory list    [--open] [--kind K] [--player ID] [--team ID]
                                           # what a skill reads before analysing
fp memory propose FILE                     # stage proposals (state/proposals.json)
fp memory apply   <proposal ids>           # after Mo confirms
fp fresh  <capability>                     # freshness guard: sync if stale (5.2)
fp usage  <player_id> [--weeks 3]          # box-score shares (shared tool,
                                           # replaces per-run scratch code)
```
- **`fp report section`** saves a long report in pieces. The matchup
  preview covers 14–16 games (today's HTML is 186–515 KB); one giant JSON
  blob written at the end is fragile (one stray comma invalidates it). The
  skill writes each game as it finishes researching it; `fp` validates that
  piece and merges it into `reports/wNN/preview.json`. A failure at game 12
  leaves games 1–11 saved. This replaces the preview skill's scratch-notes
  step.
- **`fp memory list`** is the read side of season memory. A skill starts
  with `fp memory list --open` and gets only live items (~20 lines) instead
  of the whole season's prose:

  ```
  ACTION   open    W6  Colts D/ST stream: start vs ARI?            (awaiting outcome)
  WATCH    open    W6  Kimani Vidal: start W7 if carry share ≥ 55% (revisit W7)
  POSITION current     Cut order: Shipley > Fannin > Washington > …
  POSITION current     Hold Barkley; don't sell below an RB1 return
  ```

  `--player` / `--team` filter by subject (e.g. every item involving team
  15 before a trade evaluation with Imad).

Validation failures print the exact schema path that failed, so the skill
can fix and retry. `fp report section` exists because a full-slate preview
is too long to emit as one valid JSON blob safely.

## 5. Season memory (implements spec §7)

`state/season.json`:

```
items[]: {
  id, kind: action | watch | position,
  status: open | closed | superseded,
  created, week, updated,
  players[]: PlayerRef, team_ids[],
  summary,                       # one line
  detail,                        # optional short prose
  outcome,                       # actions: what happened, when
  trigger, revisit_week,         # watch items
  supersedes                     # positions: id of the one replaced
}
```
`players[]` and `team_ids[]` record who an entry involves, so skills find
memory by subject (ids, not names) via `fp memory list --player/--team`.

Write protocol: a skill ends by writing proposals via `fp memory propose`
and listing them in chat; Mo confirms; the skill runs `fp memory apply`.
Proposals left unconfirmed stay in `state/proposals.json` (this is the shape
a future UI approval screen reads, per spec §10).

**Migration from `history.md`** (step 1): extract only what's still live —
open actions (e.g. the W6 D/ST stream outcome), the current cut order and
watch list from the W6 waivers entry, and standing positions (e.g. Barkley
hold). Mo reviews the extracted file before it's committed. `history.md` is
deleted in step 4, once the last old skill is gone.

## 6. Sync (implements spec §5)
launchd is macOS's built-in job scheduler (the cron equivalent). Each job
is a `.plist` file in `~/Library/LaunchAgents/` (runs as Mo while logged
in), registered with `launchctl bootstrap gui/$(id -u) <plist>`, run on demand
with `launchctl kickstart`, inspected with `launchctl print`, removed with
`launchctl bootout`. Key facts for this project:
- `StartCalendarInterval` (clock times) / `StartInterval` (every N s). A run
  missed while asleep happens once on wake; runs missed while powered off
  are skipped — hence the freshness guard.
- Minimal environment: absolute paths only (no `~`, no shell `PATH`).
- The repo is under `~/Documents`, which macOS privacy protection guards; a
  background Python may get "Operation not permitted" until it is granted
  Full Disk Access (or the repo moves).
- Failures are silent: logs in `.run/sync.log`, exit code via
  `launchctl print`, and the app's sync-health banner.
- **Hands-on first (step 1):** install a throwaway "hello" job that logs the
  time every minute; inspect, kickstart, break it on purpose, remove it —
  this also tests the `~/Documents` permission question safely.
Full walkthrough: `.local/sandbox.md` §8 (not committed).

- `tools/sync_job.py light | nightly | finalize` wraps `espn_client.py`
  subcommands:
  - `light` (every 4h): `sync --free-agents-size 600`
  - `nightly` (03:00): `transactions`, current-week `week-stats`
  - `finalize` (Tue 06:00, after MNF): previous-week `week-stats` and
    `power-rankings` so `complete: true` is set
- **Lock:** `fcntl.flock` on `data/.sync.lock`, used by the job and
  `fp fresh`; a second writer waits (with timeout) rather than collides.
- **launchd:** plist in `tools/launchd/` installed to
  `~/Library/LaunchAgents/` by a script; `StartCalendarInterval` runs missed
  jobs on wake. Logs to `.run/sync.log`.
- **Freshness thresholds** live in one table in `fp.py`, keyed by
  capability (e.g. `waivers: free_agents < 6h, transactions < 24h`;
  `lineup: teams < 2h`; `review: previous week complete`).
- **ESPN cookie expiry** is the main failure mode of an unattended job: the
  job writes the failure to `sync_meta.json`, and the app shows a banner
  "sync failing since … — refresh ESPN cookies".

## 7. Build order

Steps run back to back. Each ends with an acceptance check; when it passes,
the pieces it replaces are deleted in the same branch. Steps 3a–3d are
independent of each other once steps 1–2 are done.

### Step 0 — Freeze the current setup
- After PR #1 merges: `git tag pre-redesign` on `main` and push the tag.
- Folder copy of the working tree including the gitignored `data/` and
  `config/league_config.json` (e.g. `fantasy-professor-frozen/`), so the
  old skills stay runnable from Claude Code in that folder.

### Step 1 — Foundation
1. Repo skeleton (§2), `reports/` added to `.gitignore`, dependencies,
   pytest.
2. `schemas/`: envelope, common types, season memory model; JSON Schema
   export; tests.
3. `tools/fp.py`: `report path/write/section/validate`, `memory *`,
   `fresh`, `usage`.
4. launchd hands-on with a throwaway job (§6), then `sync_job.py` + lock +
   launchd install; failure field in `sync_meta`.
5. `.claude/shared/protocols.md` (rules currently duplicated across
   skills).
6. Migrate live items from `history.md` → `state/season.json` (Mo reviews).
7. Delete the `espn-sync` skill; update `CLAUDE.md` data-flow section.

**Accept when:** tests pass; one manual run of each `sync_job` mode
succeeds and launchd is installed; `fp memory list --open` shows the
migrated items Mo approved.

### Step 2 — App shell + live hub
1. FastAPI app: port the `Dashboard` service (live/rosters groups, game
   detail, intervals, background polling) from `dashboard_server.py`; add the
   league-matchups payload for the scores strip; report-folder watcher
   (server-sent events).
2. Record ESPN fixtures (scoreboard, summary, box scores) during the next
   game window; parser tests against them.
3. React shell: nav (This week / Timeline / Trends / Live), sync-health
   banner.
4. Live hub: Man Wolf score panel, league scores strip, one card per NFL
   game, player rows (Man Wolf + opponent first, then other starters),
   points breakdown, last-play flash, fantasy-matchup chip — parity with
   `live.js`, driven by API data.
5. `app.sh start|stop|status|logs`.

**Accept when:** the hub renders correctly from recorded fixtures and in
one live game window. Then delete `dashboard_server.py`,
`tools/dashboard/`, `dashboard.sh`.

### Step 3 — The six skills (3a–3d in any order, or in parallel)
Each: schema + renderer + rewritten skill (citing `protocols.md`, using
`fp fresh`, `fp report write`, `fp memory`), then one real run on current
data rendered in the app.

- **3a Week in Review** (`review`) — replaces `team-review`,
  `league-outlook`, `sunday-recap`.
- **3b Trade Lab** (`trade`) — replaces `trade-analyzer`.
- **3c Waivers + Lineup** (`waivers`, `lineup`) — replace `waiver-wire`,
  `weekly-lineup`.
- **3d Matchup Preview + Player Eval** (`preview`, `player-eval`) — replace
  `weekly-matchup`, `player-eval`; preview writes per-game sections via
  `fp report section`.

Shared UI components (verdict banner, player row with status/consensus
tags, glossary, sources) are built with the first of these and reused.

**Accept when (per sub-step):** one real run validates and renders in the
app. Then delete the replaced skills and their `report-template.html`.

### Step 4 — Reading room, enrichment, trends, cleanup
1. Reading room: timeline by week + the two lab slots.
2. Hub enrichment: join `preview.json` / `lineup.json` player cards and
   lineup reasons onto live player rows by `player_id`.
3. Trends page: scoring & luck, lineup efficiency, league standing,
   computed in the backend from `data/`; delete `data/analyze_league.py`.
4. Delete old HTML reports and `reports/history.md`.
5. Final `CLAUDE.md` rewrite (capabilities, weekly rhythm, `fp` CLI, season
   memory protocol, app usage).
6. Mo removes the global `d-league-weekly-report` skill in claude.ai.

**Accept when:** spec §11 success criteria all hold.

## 8. Testing approach

- **Schemas:** round-trip tests per report type with a hand-written valid
  example and targeted invalid ones.
- **ESPN parsing:** record real scoreboard / summary / box-score responses
  as fixtures (scratch-captured during a live window) and test the live
  service's parsing against them — no live network in tests.
- **`fp` CLI:** retention rules (replace vs overwrite), section merging,
  memory propose/apply, lock behaviour.
- **Frontend:** `tsc --noEmit`, Vitest for pure logic (player ordering,
  tally, field-position math); visual checks in the browser.
- **Real-data check** at the end of each step, as listed above (current
  week's data for skills; one live game window for the hub).

## 9. Git workflow

Per existing practice: each step on its own feature branch → PR → `main`
(step 3 sub-steps can each be their own branch).
`state/season.json` changes made during normal skill runs go straight to
`main` (like ledger updates today). `reports/` and `data/` stay gitignored
(`reports/` is added to `.gitignore` in step 1).

## 10. Risks

| Risk | Mitigation |
|---|---|
| Rebuild breaks the weekly routine mid-season | Frozen copy (step 0) is the fallback for any week the new build can't cover |
| LLM-written JSON fails validation or drifts | `fp report write` validates with precise errors; skills retry; section-at-a-time writes for long reports |
| ESPN cookie expiry silently stalls the scheduled job | Failure recorded in `sync_meta`, banner in the app, `fp fresh` reports it to the skill |
| `espn_api` / ESPN site API changes | Fixture tests localise breakage to the parser |
| Scope creep during the build | New ideas go to the spec first (project memory rule) |

## 11. Decisions (confirmed by Mo, 2026-10-17)

1. **Frontend:** React.
2. **Season memory folder:** `state/`.
3. **Sync cadence:** light sync every 4h, nightly transactions, Tuesday
   06:00 finalise.
4. **No calendar phasing:** build as fast as possible in dependency order;
   the frozen copy (step 0) is the fallback.
