#!/usr/bin/env python3
import os
import time
import json
import re
import discum
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# —————— Configuration from environment ——————
DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
CHANNEL_IDS_RAW    = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS        = [c for c in re.split(r"[\s,]+", CHANNEL_IDS_RAW) if c]
WEEK_DAYS          = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID           = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON  = os.getenv("GOOGLE_CREDS_JSON")
# —————————————————————————————————————————————

def get_sheets_client():
    """Authorize gspread using the JSON in GOOGLE_CREDS_JSON."""
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON env var is not set.")
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scopes)
    return gspread.authorize(creds)

def fetch_messages(bot, channel_id, cutoff_ms):
    """Paginate through getMessages until we hit messages older than cutoff."""
    all_msgs = []
    before = None
    while True:
        chunk = bot.getMessages(channel_id, 100, before)
        if not chunk:
            break
        for m in chunk:
            ts = int(datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")).timestamp() * 1000)
            if ts < cutoff_ms:
                return all_msgs
            all_msgs.append(m)
        before = chunk[-1]["id"]
        time.sleep(1)
    return all_msgs

def main():
    # — Validate environment —
    if not DISCORD_USER_TOKEN:
        raise RuntimeError("DISCORD_USER_TOKEN env var is not set.")
    if not CHANNEL_IDS:
        raise RuntimeError("CHANNEL_IDS env var is not set.")
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID env var is not set.")

    # — Compute cutoff (one week ago by default) —
    cutoff_ms = int(
        (datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000
    )

    print(f"[INFO] Channels: {CHANNEL_IDS}")
    print(f"[INFO] Sheet ID: {SHEET_ID}")
    print(f"[INFO] Cutoff (ms since epoch): {cutoff_ms}")

    # — Init Discum (self-bot) client —
    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # — Init Sheets client and open spreadsheet —
    sheets = get_sheets_client()
    spreadsheet = sheets.open_by_key(SHEET_ID)

    # — For each channel, create/clear worksheet and append messages —
    for chan in CHANNEL_IDS:
        # Worksheet titles must be <= 100 chars
        title = chan if len(chan) <= 100 else chan[-100:]

        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")

        # Header row
        ws.append_row(
            ["channel_id", "message_id", "author", "timestamp", "content"]
        )

        # Fetch and append
        msgs = fetch_messages(bot, chan, cutoff_ms)
        print(f"[INFO] Fetched {len(msgs)} messages for channel {chan}")

        for m in msgs:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            ws.append_row([
                chan,
                m["id"],
                m["author"]["username"],
                ts.isoformat(),
                m.get("content", "")
            ])

    # — Clean up gateway —
    bot.gateway.close()

if __name__ == "__main__":
    main()
