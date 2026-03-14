#!/usr/bin/env python3
"""
IRC Points Fetcher for BirdyPointyServry custom points system.

Logic:
- Poll Twitch GQL every 60s to detect stream going live
- When stream goes live: send !stats hungrybirdbot in IRC, parse response
- Save base points + live_since timestamp to points_base.json
- When stream goes offline: freeze (do nothing, stats.sh handles it)
- Only fetches once per stream session (not every poll)
"""

import socket
import time
import re
import json
import os
import requests
from datetime import datetime, timezone

CHANNEL = "plssendeuro"
BOT_NICK = "hungrybirdbot"
LOG_FILE = "/logs/HungryBirdBot.log"
OUT_FILE = "/www/points_base.json"
POLL_INTERVAL = 60  # seconds between live-checks
IRC_HOST = "irc.chat.twitch.tv"
IRC_PORT = 6667
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


def get_auth_token():
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        matches = re.findall(r'"auth_token":"([^"]+)"', content)
        return matches[-1] if matches else None
    except Exception:
        return None


def is_stream_live():
    try:
        resp = requests.post(
            "https://gql.twitch.tv/gql",
            headers={"Client-ID": CLIENT_ID},
            json={"query": f'query{{user(login:"{CHANNEL}"){{stream{{id viewersCount}}}}}}'},
            timeout=5,
        )
        data = resp.json()
        stream = data.get("data", {}).get("user", {}).get("stream")
        if stream:
            return True, stream.get("viewersCount", 0)
        return False, 0
    except Exception:
        return False, 0


def fetch_points_via_irc(token):
    """Connect to IRC, send !stats hungrybirdbot, parse response. Returns int or None."""
    try:
        irc = socket.socket()
        irc.connect((IRC_HOST, IRC_PORT))
        irc.settimeout(12)
        irc.send(f"PASS oauth:{token}\r\n".encode())
        irc.send(f"NICK {BOT_NICK}\r\n".encode())
        irc.send(f"JOIN #{CHANNEL}\r\n".encode())
        time.sleep(3)
        irc.send(f"PRIVMSG #{CHANNEL} :!stats {BOT_NICK}\r\n".encode())

        buf = ""
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                buf += irc.recv(4096).decode("utf-8", errors="ignore")
            except socket.timeout:
                break

        irc.close()

        # Parse: "Current Points: 30,802"
        match = re.search(r"Current Points:\s*([\d,]+)", buf)
        if match:
            return int(match.group(1).replace(",", ""))
        return None
    except Exception as e:
        print(f"[irc-fetcher] IRC error: {e}")
        return None


def load_base():
    try:
        with open(OUT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_base(data):
    with open(OUT_FILE, "w") as f:
        json.dump(data, f)
    print(f"[irc-fetcher] Saved: {data}")


def main():
    print(f"[irc-fetcher] Starting. Polling every {POLL_INTERVAL}s...")
    was_live = False
    session_fetched = False  # True once we've fetched for the current live session

    while True:
        live, viewers = is_stream_live()

        if live and not was_live:
            # Stream just went live — new session, reset fetch flag
            print(f"[irc-fetcher] Stream went LIVE ({viewers} viewers). Fetching points...")
            session_fetched = False

        if live and not session_fetched:
            token = get_auth_token()
            if token:
                points = fetch_points_via_irc(token)
                if points is not None:
                    base = load_base()
                    save_base({
                        "base_points": points,
                        "live_since": datetime.now(timezone.utc).isoformat(),
                        "viewers": viewers,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        # Carry over frozen total from previous session
                        "frozen_points": base.get("frozen_points", points),
                    })
                    session_fetched = True
                    print(f"[irc-fetcher] Base points set to {points}")
                else:
                    print("[irc-fetcher] Failed to parse points from IRC, will retry next poll")
            else:
                print("[irc-fetcher] No auth token yet, will retry next poll")

        if not live and was_live:
            # Stream just went offline — freeze current estimated value
            base = load_base()
            if base:
                # cumulative-stats.sh will have written the last estimated value
                # Just mark stream as offline so stats.sh stops incrementing
                base["live_since"] = None
                base["viewers"] = 0
                save_base(base)
                print("[irc-fetcher] Stream went OFFLINE. Frozen.")

        was_live = live
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
