#!/usr/bin/env python3
"""
Updates the Grafana 'Twitch Miner' panel content directly via API every 30s.
Uses built-in urllib to avoid runtime dependencies (no requests needed).
"""

import os
import time
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://grafana:3000")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASS = os.environ.get("GF_ADMIN_PASSWORD", "changeme")
DASHBOARD_UID = "7ec1fa7d-b7d6-4e4d-98ff-ce42beaeaa67"
PANEL_TITLE = "Twitch Miner"
STATS_FILE = "/www/stats.json"
INTERVAL = 30

def get_auth_header():
    import base64
    auth = f"{GRAFANA_USER}:{GRAFANA_PASS}"
    encoded_auth = base64.b64encode(auth.encode()).decode()
    return f"Basic {encoded_auth}"

def update_panel():
    try:
        if not os.path.exists(STATS_FILE):
            print(f"[{datetime.now()}] Stats file {STATS_FILE} not found.")
            return

        with open(STATS_FILE, "r") as f:
            stats = json.load(f)

        headers = {
            "Authorization": get_auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # 1. Get current dashboard
        req = urllib.request.Request(f"{GRAFANA_URL}/api/dashboards/uid/{DASHBOARD_UID}", headers=headers)
        with urllib.request.urlopen(req) as resp:
            db_data = json.loads(resp.read().decode())
        
        dashboard = db_data["dashboard"]
        
        # 2. Update the specific panel
        updated = False
        for panel in dashboard.get("panels", []):
            if panel.get("title") == PANEL_TITLE:
                content = f"""
<div style="font-family: inherit; color: #d8d9da; text-align: center; padding: 10px; background: rgba(30, 30, 30, 0.4); border-radius: 8px;">
    <h3 style="margin: 0 0 10px 0; color: #a673ff; font-size: 1.2em;">🕹️ {PANEL_TITLE}</h3>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 1.1em;">
        <div style="background: rgba(255, 255, 255, 0.05); padding: 5px; border-radius: 4px;">
            <p style="margin: 0; color: #8e8e8e; font-size: 0.8em; text-transform: uppercase;">Points</p>
            <p style="margin: 0; font-weight: bold; color: #00ffbc;">{stats.get('points', 0):,}</p>
        </div>
        <div style="background: rgba(255, 255, 255, 0.05); padding: 5px; border-radius: 4px;">
            <p style="margin: 0; color: #8e8e8e; font-size: 0.8em; text-transform: uppercase;">Time</p>
            <p style="margin: 0; font-weight: bold;">{stats.get('total_hours', '0.0')}h</p>
        </div>
    </div>
    <div style="margin-top: 10px; font-size: 0.85em; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: {'#00ff00' if stats.get('is_live') else '#ff4b4b'};">
            ● {'LIVE' if stats.get('is_live') else 'OFFLINE'} ({stats.get('viewers', 0)} viewers)
        </span>
        <span style="color: #6e6e6e; font-size: 0.8em;">
            Updated: {datetime.now().strftime('%H:%M:%S')}
        </span>
    </div>
</div>"""
                panel["content"] = content
                updated = True
                break

        if updated:
            # 3. Save dashboard back
            # Dashboard saving requires the whole object with "dashboard", "overwrite", etc.
            payload = json.dumps({
                "dashboard": dashboard,
                "overwrite": True
            }).encode('utf-8')
            
            save_req = urllib.request.Request(f"{GRAFANA_URL}/api/dashboards/db", data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(save_req) as resp:
                print(f"[{datetime.now()}] Updated panel '{PANEL_TITLE}' successfully. v{dashboard.get('version')}")
        else:
            print(f"[{datetime.now()}] Panel '{PANEL_TITLE}' not found in dashboard.")

    except Exception as e:
        print(f"[{datetime.now()}] Exception: {str(e)}")

if __name__ == "__main__":
    print(f"[{datetime.now()}] Starting Grafana panel updater (urllib version)...")
    while True:
        update_panel()
        time.sleep(INTERVAL)
