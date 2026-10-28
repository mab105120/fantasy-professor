#!/usr/bin/env bash
# Remove the scheduled sync jobs installed by tools/launchd/install.sh.
set -euo pipefail
DOMAIN="gui/$(id -u)"
for mode in light nightly finalize; do
  label="com.fantasyprofessor.sync.$mode"
  launchctl bootout "$DOMAIN/$label" 2>/dev/null && echo "stopped $label" || true
  rm -f "$HOME/Library/LaunchAgents/$label.plist"
done
