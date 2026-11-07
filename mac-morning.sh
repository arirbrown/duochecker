#!/bin/bash
# Mac morning burst: checks every 30s from 6:00 to 7:00 ET from home internet.
# Started by launchd shortly before 6:00 ET (see com.ari.duochecker.morning.plist).
cd "$(dirname "$0")" || exit 1
set -a; . "$HOME/.duochecker.env"; set +a

read -r wait left <<<"$(/usr/bin/python3 - <<'EOF'
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
et = ZoneInfo("America/New_York")
now = datetime.fromisoformat(os.environ["NOW"]).astimezone(et) if os.getenv("NOW") else datetime.now(et)
start = now.replace(hour=6, minute=0, second=0, microsecond=0)
end = start + timedelta(hours=1)
if now >= end or start - now > timedelta(hours=4):
    print("skip 0")
else:
    print(int(max(0, (start - now).total_seconds())), int((end - max(now, start)).total_seconds()))
EOF
)"

if [ "$wait" = skip ]; then echo "$(date) outside 6-7am ET, skipping"; exit 0; fi
echo "$(date) waiting ${wait}s for 6:00 ET, then checking every 30s for ${left}s"
[ -n "$DRY_RUN" ] && exit 0
exec /usr/bin/caffeinate -i /bin/bash -c "sleep $wait; exec /usr/bin/python3 checker.py --interval 30 --duration $left --state \"$HOME/.duochecker-state.json\""
