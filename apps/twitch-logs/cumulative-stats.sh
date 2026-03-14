#!/bin/sh
DB="/www/cumulative.json"
LOG="/logs/HungryBirdBot.log"
OUT="/www/stats.json"
BASE="/www/points_base.json"

# Count minutes watched from log using a more robust pattern
# Matches both variants: Status code: 204 or just the event
MIN=`grep -Ei "Send minute watched request" "$LOG" | wc -l || echo 0`

# Load previous max (survives log rotation)
if [ -f "$DB" ]; then
    PREV=`grep -o '"total":[0-9]*' "$DB" | cut -d':' -f2`
    [ -z "$PREV" ] && PREV=0
else
    PREV=0
fi

if [ "$MIN" -gt "$PREV" ]; then
    TOTAL=$MIN
else
    TOTAL=$PREV
fi

HOURS=`echo "scale=2; $TOTAL / 60" | bc`

# Check if stream is live via Twitch GQL
STREAM_DATA=`wget -qO- --timeout=5 \
  --header="Client-ID: kimne78kx3ncx6brgo4mv6wki5h1ko" \
  --post-data='{"query":"query{user(login:\"plssendeuro\"){stream{id viewersCount}}}"}' \
  https://gql.twitch.tv/gql 2>/dev/null`

if echo "$STREAM_DATA" | grep -q '"stream":{'; then
    IS_LIVE="true"
    # Improved viewersCount parsing (handles different JSON layouts)
    VIEWERS=`echo "$STREAM_DATA" | grep -o '"viewersCount":[0-9]*' | head -n1 | cut -d':' -f2`
    [ -z "$VIEWERS" ] && VIEWERS=0
else
    IS_LIVE="false"
    VIEWERS=0
fi

# Load base points snapshot set by irc-points-fetcher at stream start
BASE_POINTS=0
LIVE_SINCE=""
if [ -f "$BASE" ]; then
    BASE_POINTS=`tr -d ' ' < "$BASE" | grep -o '"base_points":[0-9]*' | cut -d':' -f2`
    [ -z "$BASE_POINTS" ] && BASE_POINTS=0
    LIVE_SINCE=`tr -d ' ' < "$BASE" | grep -o '"live_since":"[^"]*"' | cut -d'"' -f4`
fi

# Estimate current points:
# While live: base + floor(minutes_since_live_start)
# While offline: use last frozen value from DB
if [ "$IS_LIVE" = "true" ] && [ -n "$LIVE_SINCE" ] && [ "$LIVE_SINCE" != "null" ]; then
    NOW_EPOCH=`date +%s`
    # Clean LIVE_SINCE for BusyBox date -d compatibility
    # Format: 2026-03-14T04:15:11.234Z -> 2026-03-14 04:15:11
    CLEAN_LIVE=`echo "$LIVE_SINCE" | sed 's/T/ /; s/\..*//; s/Z//'`
    LIVE_EPOCH=`date -d "$CLEAN_LIVE" +%s 2>/dev/null || echo "$NOW_EPOCH"`
    DIFF=$((NOW_EPOCH - LIVE_EPOCH))
    [ "$DIFF" -lt 0 ] && DIFF=0
    ELAPSED_MIN=$((DIFF / 60))
    POINTS=$((BASE_POINTS + ELAPSED_MIN))
else
    # Offline: use last known points from DB, don't increment
    POINTS=`grep -o '"points":[0-9]*' "$DB" | cut -d':' -f2`
    [ -z "$POINTS" ] && POINTS=$BASE_POINTS
fi

# Calculate minutes and hours from actual points (1pt = 1min)
POINT_MINS=$POINTS
POINT_HOURS=`echo "scale=2; $POINT_MINS / 60" | bc`
TS=`date -Iseconds`

# Save cumulative database
printf '{"total":%s,"points":%s,"updated":"%s"}\n' "$TOTAL" "$POINTS" "$TS" > "$DB"

# Output for web widget (JSON)
printf '{"total_minutes":%s,"total_hours":"%s","points":%s,"is_live":%s,"viewers":%s,"timestamp":"%s"}\n' \
  "$TOTAL" "$HOURS" "$POINTS" "$IS_LIVE" "$VIEWERS" "$TS" > "$OUT"

# Write stats directly into HTML to avoid fetch/CORS issues in Grafana
cat > /www/stats.html << HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
    <title>Twitch Stats</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px;
            overflow: hidden;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.2);
            width: 100%;
            max-width: 400px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }
        h1 { font-size: 1.3rem; font-weight: 600; letter-spacing: 0.5px; }
        .live-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 14px;
            font-weight: 600;
        }
        .live-on  { background: rgba(255,0,0,0.3); animation: pulse 2s infinite; }
        .live-off { background: rgba(255,255,255,0.15); }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }
        .live-dot { width:8px; height:8px; border-radius:50%; }
        .dot-on  { background:#ff4444; }
        .dot-off { background:#666; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2,1fr);
            gap: 12px;
            margin-bottom: 16px;
        }
        .stat {
            background: rgba(255,255,255,0.15);
            border-radius: 12px;
            padding: 16px 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value { font-size:1.6rem; font-weight:700; margin-bottom:6px; display:block; line-height:1.2; }
        .stat-label { font-size:0.7rem; opacity:0.85; text-transform:uppercase; letter-spacing:1px; font-weight:500; }
        .timestamp { text-align:center; font-size:0.65rem; opacity:0.6; font-style:italic; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎮 Twitch Miner</h1>
            <div class="live-badge $([ "$IS_LIVE" = "true" ] && echo 'live-on' || echo 'live-off')">
                <span class="live-dot $([ "$IS_LIVE" = "true" ] && echo 'dot-on' || echo 'dot-off')"></span>
                <span>$([ "$IS_LIVE" = "true" ] && echo 'LIVE' || echo 'Offline')</span>
            </div>
        </div>
        <div class="stats-grid">
            <div class="stat">
                <span class="stat-value">~$POINTS</span>
                <span class="stat-label">Points Earned</span>
            </div>
            <div class="stat">
                <span class="stat-value">$VIEWERS</span>
                <span class="stat-label">👁️ Viewers</span>
            </div>
            <div class="stat">
                <span class="stat-value">$POINT_MINS</span>
                <span class="stat-label">Minutes</span>
            </div>
            <div class="stat">
                <span class="stat-value">${POINT_HOURS}h</span>
                <span class="stat-label">Hours</span>
            </div>
        </div>
        <div class="timestamp">Updated: $TS</div>
    </div>
</body>
</html>
HTMLEOF
