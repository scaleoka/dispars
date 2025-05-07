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

# Discord API and headers
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
    while True:
        # getMessages signature: getMessages(channelID, num, before_message_id)
        chunk = bot.getMessages(channel_id, 100, before)
        if not chunk:
            break
        for m in chunk:
            # convert ISO timestamp to milliseconds
            ts = int(datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00')).timestamp() * 1000)
            if ts < cutoff_ms:
                return all_msgs
            all_msgs.append(m)
        # paginate: set before to last message ID
        before = chunk[-1]['id']
        time.sleep(1)  # rate limit handling
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

    # Debug
    print(f"Channels to parse ({len(CHANNEL_IDS)}): {CHANNEL_IDS}")
    print("Google Sheet ID:", SHEET_ID)
    print("Creds JSON length:", len(GOOGLE_CREDS_JSON or ""))

    # Compute cutoff timestamp
    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)

    # Initialize Discum client
    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # Initialize Sheets client
    sheets_client = get_sheets_client()
    spreadsheet = sheets_client.open_by_key(SHEET_ID)

    # Process each channel
    for channel in CHANNEL_IDS:
        # Worksheet title: last 50 chars of channel ID if too long
        title = channel[-50:] if len(channel) > 50 else channel
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")

        # Header
        ws.append_row(["channel_id", "message_id", "author", "timestamp", "content"])

        # Fetch and write messages
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

    # Close gateway
    bot.gateway.close()

if __name__ == '__main__':
    main()
