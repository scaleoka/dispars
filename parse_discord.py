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
# DISCORD_USER_TOKEN, CHANNEL_IDS, WEEK_DAYS, GOOGLE_SHEET_ID, GOOGLE_CREDS_JSON

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
raw_ids = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", raw_ids) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

API_BASE = "https://discord.com/api/v9"
HEADERS = {"Authorization": DISCORD_USER_TOKEN}

from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import json

def get_sheets_client():
    # Scope для Sheets и Drive
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON env variable is not set.")
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    # Создаём ServiceAccountCredentials
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scopes)

    # Программно даём сервис-аккаунту права writer на этот файл
    drive_service = build('drive', 'v3', credentials=creds)
    drive_service.permissions().create(
        fileId=SHEET_ID,
        body={
            'type': 'user',
            'role': 'writer',
            'emailAddress': creds_info['client_email']
        },
        fields='id',
        sendNotificationEmail=False
    ).execute()

    # Теперь авторизуем gspread
    return gspread.authorize(creds)

def fetch_messages(bot, channel_id, cutoff_ms):
    all_msgs, before = [], None
    while True:
        chunk = bot.getMessages(channel_id, 100, before)
        if not chunk: break
        for m in chunk:
            ts = int(datetime.fromisoformat(m['timestamp'].replace('Z','+00:00')).timestamp()*1000)
            if ts < cutoff_ms: return all_msgs
            all_msgs.append(m)
        before = chunk[-1]['id']
        time.sleep(1)
    return all_msgs

def main():
    # Validations & debug
    print("[INFO] Channels:", CHANNEL_IDS)
    print("[INFO] Sheet ID:", SHEET_ID)
    if not (DISCORD_USER_TOKEN and CHANNEL_IDS and SHEET_ID):
        raise RuntimeError("One of required env vars is missing")

    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp()*1000)
    print("[INFO] Cutoff (ms):", cutoff_ms)

    bot = discum.Client(token=DISCORD_USER_TOKEN, log=False)

    # Sheets
    sheets_client = get_sheets_client()
    try:
        spreadsheet = sheets_client.open_by_key(SHEET_ID)
    except gspread.exceptions.APIError as e:
        print(f"\n[ERROR] Cannot open sheet {SHEET_ID}.")
        print("        Make sure you shared this sheet with the service account above.")
        raise

    for channel in CHANNEL_IDS:
        title = channel[-50:] if len(channel)>50 else channel
        try:
            ws = spreadsheet.worksheet(title); ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="5")
        ws.append_row(["channel_id","message_id","author","timestamp","content"])
        msgs = fetch_messages(bot, channel, cutoff_ms)
        print(f"[INFO] Fetched {len(msgs)} msgs for {channel}")
        for m in msgs:
            ts = datetime.fromisoformat(m['timestamp'].replace('Z','+00:00'))
            ws.append_row([channel, m['id'], m['author']['username'], ts.isoformat(), m.get('content',"")])

    bot.gateway.close()

if __name__ == "__main__":
    main()
