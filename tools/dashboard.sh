#!/usr/bin/env bash
# Start/stop the live weekly-matchup dashboard (tools/dashboard_server.py) in the background.
# The server also runs the live polling: it keeps scores, rosters and in-progress game
# detail fresh on their intervals whether or not a browser is open.
#
#   tools/dashboard.sh start [--no-open] [server flags...]   e.g. start --live 5 --rosters 120
#   tools/dashboard.sh stop | restart [flags...] | status | logs
#
# PID and log live in .run/ (gitignored). Port comes from --port (default 8765).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.run"
PIDFILE="$RUN/dashboard.pid"
LOG="$RUN/dashboard.log"
PORTFILE="$RUN/dashboard.port"

running() { [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }
url() { echo "http://127.0.0.1:$(cat "$PORTFILE" 2>/dev/null || echo 8765)"; }

start() {
  local open=1 port=8765 args=() prev=""
  for a in "$@"; do
    if [[ "$a" == "--no-open" ]]; then open=0; continue; fi
    [[ "$prev" == "--port" ]] && port="$a"
    [[ "$a" == --port=* ]] && port="${a#--port=}"
    args+=("$a"); prev="$a"
  done
  if running; then
    echo "Dashboard already running (pid $(cat "$PIDFILE")) at $(url)"
    return 0
  fi
  rm -f "$PIDFILE"
  mkdir -p "$RUN"
  echo "$port" > "$PORTFILE"
  cd "$ROOT"
  nohup python3 tools/dashboard_server.py ${args[@]+"${args[@]}"} >"$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  for _ in $(seq 1 30); do
    if curl -sf -o /dev/null "$(url)/api/config"; then
      echo "Dashboard running (pid $(cat "$PIDFILE")) at $(url)"
      head -1 "$LOG"
      [[ $open == 1 ]] && open "$(url)"
      return 0
    fi
    if ! running; then break; fi
    sleep 1
  done
  echo "Dashboard failed to start. Last log lines:" >&2
  tail -20 "$LOG" >&2
  stop >/dev/null 2>&1 || true
  return 1
}

stop() {
  if ! running; then
    rm -f "$PIDFILE"
    echo "Dashboard not running"
    return 0
  fi
  local pid; pid="$(cat "$PIDFILE")"
  kill "$pid"
  for _ in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
  kill -0 "$pid" 2>/dev/null && kill -9 "$pid"
  rm -f "$PIDFILE"
  echo "Dashboard stopped (pid $pid)"
}

status() {
  if running; then
    echo "Dashboard running (pid $(cat "$PIDFILE")) at $(url)"
    curl -s "$(url)/api/config" && echo
  else
    echo "Dashboard not running"
    return 1
  fi
}

cmd="${1:-start}"; shift || true
case "$cmd" in
  start)   start "$@" ;;
  stop)    stop ;;
  restart) stop; start "$@" ;;
  status)  status ;;
  logs)    tail -f "$LOG" ;;
  *) echo "usage: tools/dashboard.sh {start [--no-open] [server flags]|stop|restart [flags]|status|logs}" >&2; exit 2 ;;
esac
