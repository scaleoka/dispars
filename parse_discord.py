#!/usr/bin/env python3
import os
import time
import json
import re
import discum
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables:
# DISCORD_USER_TOKEN: Your user token (self-bot)
# CHANNEL_IDS: comma- or whitespace-separated list of channel IDs to parse
# WEEK_DAYS: days back to fetch (default 7)
# GOOGLE_SHEET_ID: Google Sheet ID
# GOOGLE_CREDS_JSON: full JSON credentials string for service account

# Load environment
DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
raw_ids = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", raw_ids) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# Discord API headers for Discum (via WebSocket) and REST fallback
API_BASE = "https://discord.com/api/v9"
HEADERS = {
    "Authorization": DISCORD_USER_TOKEN,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

# Initialize Google Sheets client
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

# Fetch messages using Discum until cutoff timestamp
def fetch_messages(bot, channel_id, cutoff_ms):
    all_msgs = []
    before = None
    print(f"[DEBUG] Start fetching for channel {channel_id}, cutoff {cutoff_ms}")
    while True:
        print(f"[DEBUG] Requesting messages before id={before}")
        chunk = bot.getMessages(channel_id, 100, before)
        if not chunk:
            print(f"[DEBUG] No more messages returned for channel {channel_id}")
            break
        print(f"[DEBUG] Retrieved chunk of size {len(chunk)}")
        for m in chunk:
            ts = int(datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00')).timestamp() * 1000)
            if ts < cutoff_ms:
                print(f"[DEBUG] Message {m['id']} is before cutoff, stopping fetch.")
                return all_msgs
            all_msgs.append(m)
        before = chunk[-1]['id']
        time.sleep(1)
    print(f"[DEBUG] Finished fetching channel {channel_id}, total msgs collected: {len(all_msgs)}")
    return all_msgs

# Main function
def main():
    # Validate
    if not DISCORD_USER_TOKEN:
        raise RuntimeError("DISCORD_USER_TOKEN env variable is not set.")
    if not CHANNEL_IDS:
        raise RuntimeError("CHANNEL_IDS env variable is not set.")
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID env variable is not set.")

    # Debug prints
    print(f"[INFO] Channels to parse ({len(CHANNEL_IDS)}): {CHANNEL_IDS}")
    print("[INFO] Google Sheet ID:", SHEET_ID)
    print("[INFO] Creds JSON length:", len(GOOGLE_CREDS_JSON or ""))

    # Compute cutoff timestamp
    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)
    print(f"[INFO] Messages cutoff (ms since epoch): {cutoff_ms}")

    # Initialize Discum client
    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # Initialize Sheets client
    sheets_client = get_sheets_client()
    spreadsheet = sheets_client.open_by_key(SHEET_ID)

    # Process each channel
    for channel in CHANNEL_IDS:
        # Worksheet title
        title = channel[-50:] if len(channel) > 50 else channel
        print(f"[INFO] Processing channel sheet '{title}'")
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")

        # Write header
        ws.append_row(["channel_id", "message_id", "author", "timestamp", "content"])

        # Fetch and write messages
        msgs = fetch_messages(bot, channel, cutoff_ms)
        print(f"[INFO] Fetched {len(msgs)} messages for channel {channel}")
        for m in msgs:
            ts = datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00'))
            ws.append_row([
                channel,
                m['id'],
                m['author']['username'],
                ts.isoformat(),
                m.get('content', '')
            ])

    # Close Discum gateway
    bot.gateway.close()

if __name__ == '__main__':
    main()
