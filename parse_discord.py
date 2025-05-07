#!/usr/bin/env python3
import os
import time
import json
import re
import discum
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables:
# DISCORD_USER_TOKEN: your user token (self-bot, used by Discum)
# CHANNEL_IDS: comma- or whitespace-separated list of channel IDs
# WEEK_DAYS: days back to fetch (default 7)
# GOOGLE_SHEET_ID: Google Sheets ID
# GOOGLE_CREDS_JSON: full JSON credentials string for your service account

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
raw_ids = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", raw_ids) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

def get_sheets_client():
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON env variable is not set.")
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    print(f"[DEBUG] Service account email: {creds_info.get('client_email')}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scopes)
    return gspread.authorize(creds)

def fetch_messages(bot, channel_id, cutoff_ms):
    """Use Discum.getMessages (gateway-powered REST) to paginate history."""
    all_msgs = []
    before = None
    while True:
        chunk = bot.getMessages(channel_id, 100, before)
        if not chunk:
            break
        print(f"[DEBUG] Retrieved {len(chunk)} messages from {channel_id}")
        for m in chunk:
            ts = int(datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")).timestamp()*1000)
            if ts < cutoff_ms:
                print(f"[DEBUG] Hit cutoff on message {m['id']} → stopping.")
                return all_msgs
            all_msgs.append(m)
        before = chunk[-1]["id"]
        time.sleep(1)
    return all_msgs

def main():
    # Validate
    missing = [v for v in ["DISCORD_USER_TOKEN","CHANNEL_IDS","GOOGLE_SHEET_ID","GOOGLE_CREDS_JSON"]
               if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)
    print(f"[INFO] Channels: {CHANNEL_IDS}")
    print(f"[INFO] Sheet ID: {SHEET_ID}")
    print(f"[INFO] Cutoff (ms): {cutoff_ms}")

    # Init Discum client
    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # Init Sheets client
    sheets_client = get_sheets_client()
    spreadsheet = sheets_client.open_by_key(SHEET_ID)

    for channel in CHANNEL_IDS:
        title = channel  if len(channel)<=100 else channel[-100:]
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")

        ws.append_row(["channel_id","message_id","author","timestamp","content"])
        msgs = fetch_messages(bot, channel, cutoff_ms)
        print(f"[INFO] Fetched {len(msgs)} messages for {channel}")
        for m in msgs:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            ws.append_row([
                channel,
                m["id"],
                m["author"]["username"],
                ts.isoformat(),
                m.get("content","")
            ])

    bot.gateway.close()

if __name__ == "__main__":
    main()
