#!/usr/bin/env python3
import os
import time
import json
import re
import sys
import discum
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Environment variables:
# DISCORD_USER_TOKEN, CHANNEL_IDS, WEEK_DAYS, GOOGLE_SHEET_ID, GOOGLE_CREDS_JSON

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
    service_email = creds_info.get("client_email")
    print(f"[DEBUG] Service account email: {service_email}")
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scopes)

    # Try programmatic share (will 404 if no view access)
    try:
        drive = build("drive", "v3", credentials=creds)
        drive.permissions().create(
            fileId=SHEET_ID,
            body={
                "type": "user",
                "role": "writer",
                "emailAddress": service_email
            },
            fields="id",
            sendNotificationEmail=False
        ).execute()
        print("[INFO] Granted writer permission to service account.")
    except HttpError as e:
        if e.resp.status in (403, 404):
            print(f"[WARN] Could not share spreadsheet programmatically ({e.resp.status}).")
            print("       Make sure this exact email above is added as Editor in the sheet's Share dialog.")
        else:
            raise

    return gspread.authorize(creds)

def fetch_messages(bot, channel_id, cutoff_ms):
    all_msgs = []
    before = None
    while True:
        chunk = bot.getMessages(channel_id, 100, before)
        if not chunk:
            break
        for m in chunk:
            ts = int(datetime.fromisoformat(m["timestamp"].replace("Z","+00:00")).timestamp()*1000)
            if ts < cutoff_ms:
                return all_msgs
            all_msgs.append(m)
        before = chunk[-1]["id"]
        time.sleep(1)
    return all_msgs

def main():
    if not (DISCORD_USER_TOKEN and CHANNEL_IDS and SHEET_ID and GOOGLE_CREDS_JSON):
        print("[ERROR] One or more required env vars missing.")
        sys.exit(1)

    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)
    print(f"[INFO] Channels: {CHANNEL_IDS}")
    print(f"[INFO] Sheet ID: {SHEET_ID}")
    print(f"[INFO] Cutoff (ms): {cutoff_ms}")

    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # Sheets client & open
    sheets_client = get_sheets_client()
    try:
        spreadsheet = sheets_client.open_by_key(SHEET_ID)
    except Exception as e:
        print(f"[ERROR] Cannot open spreadsheet with ID {SHEET_ID}: {e}")
        sys.exit(1)

    for channel in CHANNEL_IDS:
        title = channel[-50:] if len(channel) > 50 else channel
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")
        ws.append_row(["channel_id","message_id","author","timestamp","content"])
        msgs = fetch_messages(bot, channel, cutoff_ms)
        print(f"[INFO] Fetched {len(msgs)} messages for {channel}")
        for m in msgs:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z","+00:00"))
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
