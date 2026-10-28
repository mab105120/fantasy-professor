#!/usr/bin/env python3
"""fp — the Fantasy Professor agent's CLI (plan §4).

One entry point for the plumbing every skill needs, so skills stop
re-describing it:

  fp report path     <type> [--week N]             where a report lives
  fp report write    <type> [--week N] [--draft] FILE|-
                                                   validate a body and place the report
  fp report section  <type> [--week N] --key K FILE|-
                                                   merge one piece into sections (long reports)
  fp report finalize <type> [--week N] [FILE|-]    mark a draft final (optionally add headline etc.)
  fp report validate FILE                          check a complete report file
  fp report schema   [--out DIR]                   export JSON Schema for reports + memory

  fp memory list     [--open] [--kind K] [--player ID] [--team ID] [--json]
  fp memory propose  FILE|- --source LABEL         stage changes for Mo to confirm
  fp memory proposals                              list staged changes
  fp memory apply    ID... | --all                 apply confirmed proposals
  fp memory reject   ID...                         discard proposals

  fp fresh  <capability> [--check]                 sync whatever is too stale for a capability
  fp sync-status                                   last scheduled/on-demand sync result
  fp usage  <player_id> [--weeks 3] [--json]       box-score target/carry shares

Report types: review, waivers, lineup, preview (weekly) · trade, player-eval (lab).
Run with the project venv: .venv/bin/python tools/fp.py ...
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fplib import fresh, memory, reports, sync, usage  # noqa: E402
from fplib.paths import Paths, write_json_atomic  # noqa: E402
from schemas.report import REPORT_TYPES  # noqa: E402


def cmd_report(paths: Paths, a) -> int:
    if a.action == "schema":
        from schemas import json_schemas
        out = Path(a.out)
        for name, schema in json_schemas().items():
            write_json_atomic(out / f"{name}.schema.json", schema)
        print(f"wrote JSON Schema to {out}/")
        return 0
    if a.action == "validate":
        reports.validate(reports.load_json_arg(a.file))
        print(f"{a.file}: valid")
        return 0
    week = a.week or reports.default_week(paths, a.type)
    if a.action == "path":
        print(reports.report_path(paths, a.type, week).relative_to(paths.root))
        return 0
    if a.action == "write":
        path = reports.write(paths, a.type, week, reports.load_json_arg(a.file), draft=a.draft)
    elif a.action == "section":
        path = reports.write_section(paths, a.type, week, a.key, reports.load_json_arg(a.file))
    else:  # finalize
        body = reports.load_json_arg(a.file) if a.file else None
        path = reports.finalize(paths, a.type, week, body)
    print(f"{a.action}: {path.relative_to(paths.root)}")
    return 0


def cmd_memory(paths: Paths, a) -> int:
    if a.action == "list":
        items = memory.select(memory.load(paths), open_only=a.open, kind=a.kind, player=a.player, team=a.team)
        if a.json:
            print(json.dumps([i.model_dump(mode="json", exclude_none=True) for i in items], indent=2))
        else:
            print("\n".join(memory.line(i) for i in items) or "(no matching memory items)")
        pending = memory.load_proposals(paths).proposals
        if pending and not a.json:
            print(f"\n{len(pending)} proposal(s) awaiting confirmation — fp memory proposals")
        return 0
    if a.action == "proposals":
        pending = memory.load_proposals(paths).proposals
        print("\n".join(memory.describe(p) for p in pending) or "(no pending proposals)")
        return 0
    if a.action == "propose":
        added = memory.propose(paths, reports.load_json_arg(a.file), a.source)
        print("\n".join(memory.describe(p) for p in added))
        print("\nShow these to Mo; apply only the ones he confirms: fp memory apply <ids>")
        return 0
    if a.action == "apply":
        if not a.ids and not a.all:
            raise SystemExit("give proposal ids, or --all")
        print("\n".join(memory.apply(paths, None if a.all else a.ids)))
        return 0
    n = memory.reject(paths, a.ids)
    print(f"rejected {n} proposal(s)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("report").add_subparsers(dest="action", required=True)
    for name in ("path", "write", "section", "finalize"):
        x = rp.add_parser(name)
        x.add_argument("type", choices=REPORT_TYPES)
        x.add_argument("--week", type=int)
        if name == "write":
            x.add_argument("--draft", action="store_true")
            x.add_argument("file")
        if name == "section":
            x.add_argument("--key", required=True, help="dotted path inside sections, e.g. games.401772810")
            x.add_argument("file")
        if name == "finalize":
            x.add_argument("file", nargs="?")
    rp.add_parser("validate").add_argument("file")
    rp.add_parser("schema").add_argument("--out", default="schemas/json")

    mp = sub.add_parser("memory").add_subparsers(dest="action", required=True)
    ls = mp.add_parser("list")
    ls.add_argument("--open", action="store_true")
    ls.add_argument("--kind", choices=("action", "watch", "position"))
    ls.add_argument("--player", type=int)
    ls.add_argument("--team", type=int)
    ls.add_argument("--json", action="store_true")
    mp.add_parser("proposals")
    pr = mp.add_parser("propose")
    pr.add_argument("file")
    pr.add_argument("--source", required=True, help="which skill or conversation proposed this")
    ap = mp.add_parser("apply")
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    mp.add_parser("reject").add_argument("ids", nargs="+")

    fr = sub.add_parser("fresh")
    fr.add_argument("capability", choices=sorted(fresh.REQUIREMENTS))
    fr.add_argument("--check", action="store_true", help="report only; don't sync")

    sub.add_parser("sync-status")

    us = sub.add_parser("usage")
    us.add_argument("player_id", type=int)
    us.add_argument("--weeks", type=int, default=3)
    us.add_argument("--json", action="store_true")

    a = p.parse_args(argv)
    paths = Paths()
    try:
        if a.cmd == "report":
            return cmd_report(paths, a)
        if a.cmd == "memory":
            return cmd_memory(paths, a)
        if a.cmd == "fresh":
            return 0 if fresh.ensure(paths, a.capability, check_only=a.check) else 1
        if a.cmd == "sync-status":
            print(json.dumps(sync.job_status(paths) or {"note": "no sync job has run yet"}, indent=2))
            return 0
        if a.cmd == "usage":
            u = usage.player_usage(paths, a.player_id, a.weeks)
            if a.json:
                print(json.dumps(u, indent=2))
            else:
                print(f"{u['name']} ({u['position']}, {u['pro_team']}) — last {len(u['games'])} completed games")
                for g in u["games"]:
                    if "note" in g:
                        print(f"  W{g['week']} vs {g['opponent']}: {g['note']}")
                        continue
                    ts = f"{g['target_share']:.0%}" if g["target_share"] is not None else "—"
                    cs = f"{g['carry_share']:.0%}" if g["carry_share"] is not None else "—"
                    print(f"  W{g['week']} vs {g['opponent']}: {g['targets']:.0f}/{g['team_targets']:.0f} tgt ({ts}), "
                          f"{g['carries']:.0f}/{g['team_carries']:.0f} car ({cs}), "
                          f"{g['receptions']:.0f} rec {g['receiving_yards']:.0f} yds, "
                          f"{g['rushing_yards']:.0f} rush yds, {g['touchdowns']:.0f} TD")
            return 0
    except (reports.ReportError, memory.MemoryError_, sync.SyncError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
