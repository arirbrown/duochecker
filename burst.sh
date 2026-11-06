#!/usr/bin/env bash
# Runs checker.py every 30s from 6:00 to 7:00 ET (or for 1h right away when started by hand).
set -euo pipefail
now=${NOW:-$(date +%s)}
start=$(TZ=America/New_York date -d "$(TZ=America/New_York date -d "@$now" +%F) 06:00" +%s)
end=$((start + 3600))
if [ "${GITHUB_EVENT_NAME:-}" = workflow_dispatch ]; then start=$now; end=$((now + 3600)); fi
if [ "$now" -ge "$end" ] || [ $((start - now)) -gt 3600 ]; then echo "outside the 6-7am ET window, skipping"; exit 0; fi
if [ "$start" -gt "$now" ]; then echo "sleeping $((start - now))s until 6:00 ET"; [ -n "${DRY_RUN:-}" ] || sleep $((start - now)); fi
left=$((end - $(date +%s)))
[ -n "${NOW:-}" ] && left=$((end - (start > now ? start : now)))
echo "checking every 30s for ${left}s"
[ -n "${DRY_RUN:-}" ] || exec python3 checker.py --interval 30 --duration "$left" --state /tmp/burst-state.json
