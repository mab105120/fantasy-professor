#!/usr/bin/env bash
# Install (or reinstall) the three scheduled sync jobs as launchd agents for
# the current user. See docs/plan.md §6 and .local/sandbox.md §8.
#
#   tools/launchd/install.sh            install/refresh all three jobs
#   tools/launchd/install.sh --dry-run  print the generated plists, change nothing
#
# Jobs: light (every 4h), nightly (03:00), finalize (Tue 06:00).
# Logs: .run/sync.log. Check a job: launchctl print gui/$(id -u)/com.fantasyprofessor.sync.light
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
AGENTS="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1

[[ -x "$PYTHON" ]] || { echo "missing $PYTHON — create the venv first (see CLAUDE.md)"; exit 1; }

schedule() {
  case "$1" in
    light)    printf '  <key>StartInterval</key>\n  <integer>14400</integer>\n' ;;
    nightly)  printf '  <key>StartCalendarInterval</key>\n  <dict>\n    <key>Hour</key><integer>3</integer>\n    <key>Minute</key><integer>0</integer>\n  </dict>\n' ;;
    finalize) printf '  <key>StartCalendarInterval</key>\n  <dict>\n    <key>Weekday</key><integer>2</integer>\n    <key>Hour</key><integer>6</integer>\n    <key>Minute</key><integer>0</integer>\n  </dict>\n' ;;
  esac
}

render() {
  local mode="$1" sched
  sched="$(schedule "$mode")"
  python3 - "$ROOT/tools/launchd/sync.plist.template" "$mode" "$PYTHON" "$ROOT" "$sched" <<'PY'
import sys
tpl, mode, py, root, sched = sys.argv[1:]
print(open(tpl).read().replace("@MODE@", mode).replace("@PYTHON@", py)
      .replace("@ROOT@", root).replace("@SCHEDULE@", sched.rstrip("\n")), end="")
PY
}

mkdir -p "$ROOT/.run"
for mode in light nightly finalize; do
  label="com.fantasyprofessor.sync.$mode"
  plist="$AGENTS/$label.plist"
  if (( DRY )); then echo "----- $plist"; render "$mode"; continue; fi
  mkdir -p "$AGENTS"
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  render "$mode" > "$plist"
  plutil -lint "$plist" >/dev/null
  launchctl bootstrap "$DOMAIN" "$plist"
  echo "installed $label"
done
(( DRY )) || echo "Run one now:  launchctl kickstart -k $DOMAIN/com.fantasyprofessor.sync.light   (then: tail .run/sync.log)"
