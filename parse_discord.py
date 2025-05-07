#!/usr/bin/env python3
import os
import json
import re
import time
from datetime import datetime, timedelta

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# Environment variables
TOKEN = os.getenv("DISCORD_USER_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", os.getenv("CHANNEL_IDS", "")) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

def get_sheets_client():
    creds_info = json.loads(CREDS_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scopes)
    return gspread.authorize(creds)

def on_response(response, channel_id, cutoff_ms, collector):
    url = response.url
    if f"/api/v9/channels/{channel_id}/messages" not in url:
        return
    try:
        data = response.json()
    except:
        return
    for m in data:
        ts = int(datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")).timestamp() * 1000)
        if ts < cutoff_ms:
            return
        collector.append(m)

def main():
    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)
    sheets_client = get_sheets_client()
    spreadsheet = sheets_client.open_by_key(SHEET_ID)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Inject token before any scripts run
        page.add_init_script(f"() => {{ window.localStorage.setItem('token', '{TOKEN}'); }}")

        for chan in CHANNEL_IDS:
            collected = []
            print(f"[INFO] Scraping channel {chan} ...")
            page.on("response", lambda resp: on_response(resp, chan, cutoff_ms, collected))
            page.goto(f"https://discord.com/channels/{GUILD_ID}/{chan}")

            last_scroll = None
            while True:
                page.keyboard.press("PageUp")
                time.sleep(0.3)
                scroll = page.evaluate("document.scrollingElement.scrollTop")
                if scroll == last_scroll:
                    break
                last_scroll = scroll

            print(f"[INFO] Collected {len(collected)} messages for {chan}")

            # Write to Google Sheets
            try:
                ws = spreadsheet.worksheet(chan)
                ws.clear()
            except gspread.exceptions.WorksheetNotFound:
                ws = spreadsheet.add_worksheet(title=chan, rows="1000", cols="5")
            ws.append_row(["channel_id", "message_id", "author", "timestamp", "content"])
            for m in collected:
                ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                ws.append_row([
                    chan,
                    m["id"],
                    m["author"]["username"],
                    ts.isoformat(),
                    m.get("content", "")
                ])

        browser.close()

if __name__ == "__main__":
    main()
