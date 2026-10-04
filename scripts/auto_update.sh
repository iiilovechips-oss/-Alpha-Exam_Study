#!/bin/zsh
# Automatic Canvas sync. The Mac starts this once a day; it only does the real work when the last
# automatic run was about two days ago or more. That way a day when the Mac was off or asleep is
# simply caught up the next morning. To change how often it runs, change EVERY_HOURS.
EVERY_HOURS=47   # just under two days, so a run at 8:00 is not skipped for being a few minutes "early"

cd "$(dirname "$0")/.." || exit 1
mkdir -p reports
STAMP=reports/.last-auto-update          # an empty file; its date is when the last automatic run started

if [ -f "$STAMP" ] && [ -n "$(find "$STAMP" -mmin -$((EVERY_HOURS * 60)))" ]; then
  exit 0                                 # ran recently: nothing to do today
fi
touch "$STAMP"
echo "=== automatic update, $(date) ===" >> reports/auto-update.log
uv run exam-study update >> reports/auto-update.log 2>&1
