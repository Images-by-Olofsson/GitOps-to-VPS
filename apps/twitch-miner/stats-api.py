#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
import re
import requests
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)

TWITCH_CHANNEL = "plssendeuro"
LOG_FILE = "/usr/src/app/logs/HungryBirdBot.log"

@app.route("/stats")
def get_stats():
    # Parse hours watched from logs
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        minute_requests = content.count("Send minute watched request")
        hours_watched = round(minute_requests / 180, 2)
        estimated_points = int(hours_watched * 40)
    except:
        hours_watched = 0
        estimated_points = 0
    
    # Check if stream is live
    try:
        url = "https://gql.twitch.tv/gql"
        headers = {"Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko"}
        query = {
            "query": """
                query {
                    user(login: "plssendeuro") {
                        stream {
                            id
                            title
                            viewersCount
                        }
                    }
                }
            """
        }
        response = requests.post(url, json=query, headers=headers, timeout=5)
        data = response.json()
        stream = data.get("data", {}).get("user", {}).get("stream")
        
        if stream:
            is_live = True
            stream_title = stream.get("title", "N/A")
            viewers = stream.get("viewersCount", 0)
        else:
            is_live = False
            stream_title = "Offline"
            viewers = 0
    except:
        is_live = False
        stream_title = "Unknown"
        viewers = 0
    
    return jsonify({
        "channel": TWITCH_CHANNEL,
        "is_live": is_live,
        "stream_title": stream_title,
        "viewers": viewers,
        "hours_watched": hours_watched,
        "estimated_points": estimated_points,
        "last_updated": datetime.now().isoformat()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
PYEOF
chmod +x /opt/twitch-miner/stats-api.py && echo "Stats API created"
