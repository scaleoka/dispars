#!/usr/bin/env python3
import os
import time
import json
import re
import requests
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables:
# DISCORD_USER_TOKEN: Your user token (self-bot)
# CHANNEL_IDS: comma- or newline-separated list of channel IDs
# WEEK_DAYS: number of days back to fetch (default 7)
# GOOGLE_SHEET_ID: target Google Sheet ID
# GOOGLE_CREDS_JSON: full JSON credentials string for service account

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
raw_ids = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", raw_ids) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

API_BASE = "https://discord.com/api/v9"
HEADERS = {
    "Authorization": DISCORD_USER_TOKEN,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

def get_sheets_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON env variable is not set.")
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def fetch_messages(channel_id, after_ts, before_ts=None):
    url = f"{API_BASE}/channels/{channel_id}/messages"
    params = {"limit": 100, "after": after_ts}
    if before_ts:
        params["before"] = before_ts
    all_msgs = []
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_msgs.extend(data)
        params["after"] = data[-1]["id"]
        time.sleep(1)  # rate‐limit friendly
    return all_msgs

def main():
    if not DISCORD_USER_TOKEN:
        raise RuntimeError("DISCORD_USER_TOKEN env variable is not set.")
    if not CHANNEL_IDS:
        raise RuntimeError("CHANNEL_IDS env variable is not set.")
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID env variable is not set.")

    # Debug
    print(f"Parsed CHANNEL_IDS ({len(CHANNEL_IDS)}): {CHANNEL_IDS}")
    print("Using SHEET_ID:", SHEET_ID)
    print("CREDS JSON length:", len(GOOGLE_CREDS_JSON or ""))

    now = datetime.utcnow()
    start = now - timedelta(days=WEEK_DAYS)
    after_ms = int(start.timestamp() * 1000)

    client = get_sheets_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    for chan in CHANNEL_IDS:
        title = chan
        # Create or clear worksheet
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")

        ws.append_row(["channel_id", "message_id", "author", "timestamp", "content"])
        msgs = fetch_messages(chan, after_ms)
        for m in msgs:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            ws.append_row([
                chan,
                m["id"],
                m["author"]["username"],
                ts.isoformat(),
                m.get("content", "")
            ])

if __name__ == "__main__":
    main()
