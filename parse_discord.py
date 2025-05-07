#!/usr/bin/env python3
import os
import json
import time
import re
import discum
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables:
# DISCORD_USER_TOKEN: Your user token (self-bot)
# CHANNEL_IDS: comma- or newline-separated list of channel IDs to parse
# WEEK_DAYS: number of days back to fetch (default 7)
# GOOGLE_SHEET_ID: target Google Sheet ID
# GOOGLE_CREDS_JSON: full JSON credentials string for service account

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
raw_ids = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", raw_ids) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# Initialize Sheets client using service-account JSON from env
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

# Fetch messages via Discum until cutoff timestamp
def fetch_messages(bot, channel_id, cutoff_ms):
    all_msgs = []
    before = None
    while True:
        chunk = bot.getMessages(channel_id, num=100, before=before)
        if not chunk:
            break
        for m in chunk:
            # parse timestamp to ms
            ts = int(datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00')).timestamp() * 1000)
            if ts < cutoff_ms:
                return all_msgs
            all_msgs.append(m)
        before = chunk[-1]['id']
        time.sleep(1)
    return all_msgs

# Main logic
def main():
    if not DISCORD_USER_TOKEN:
        raise RuntimeError("DISCORD_USER_TOKEN env variable is not set.")
    if not CHANNEL_IDS:
        raise RuntimeError("CHANNEL_IDS env variable is not set or empty.")
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID env variable is not set.")

    # Compute cutoff
    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)

    # Initialize Discum client
    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # Initialize Google Sheets
    client = get_sheets_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    # Process each channel
    for channel in CHANNEL_IDS:
        title = channel[-50:] if len(channel) > 50 else channel
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")

        # Header
        ws.append_row(["channel_id", "message_id", "author", "timestamp", "content"])

        # Fetch and append
        msgs = fetch_messages(bot, channel, cutoff_ms)
        for m in msgs:
            ts = datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00'))
            ws.append_row([
                channel,
                m['id'],
                m['author']['username'],
                ts.isoformat(),
                m.get('content', '')
            ])

    bot.gateway.close()

if __name__ == '__main__':
    main()
