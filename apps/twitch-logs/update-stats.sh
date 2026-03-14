#!/bin/bash
LOG_FILE="/opt/twitch-miner/logs/HungryBirdBot.log"
OUTPUT_FILE="/opt/twitch-logs-nginx/www/stats.json"

# Count minute requests from full log
MINUTE_REQUESTS=$(grep -c "Send minute watched request" "$LOG_FILE" 2>/dev/null || echo 0)

# Create JSON
cat > "$OUTPUT_FILE" << EOF
{
  "minute_requests": $MINUTE_REQUESTS,
  "timestamp": "$(date -Iseconds)"
}
EOF

echo "Stats updated: $MINUTE_REQUESTS minute requests"
EOFSH
chmod +x /opt/twitch-logs-nginx/update-stats.sh
/opt/twitch-logs-nginx/update-stats.sh
