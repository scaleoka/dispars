import os
import time
import requests
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables:
# DISCORD_USER_TOKEN: Your user token (self-bot)
# GUILD_ID: ID of the Discord server (guild)
# CHANNEL_IDS: comma-separated list of channel IDs to parse
# WEEK_DAYS: number of days back to fetch (default 7)
# GOOGLE_SHEET_ID: target Google Sheet ID
# GOOGLE_CREDS_JSON_PATH: path to service-account JSON credentials file

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_IDS = [c.strip() for c in os.getenv("CHANNEL_IDS", "").split(",") if c.strip()]
WEEK_DAYS = int(os.getenv("WEEK_DAYS", "7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_PATH = os.getenv("GOOGLE_CREDS_JSON_PATH")

API_BASE = "https://discord.com/api/v9"
HEADERS = {"Authorization": DISCORD_USER_TOKEN}

def get_sheets_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_PATH, scope)
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
        time.sleep(1)
    return all_msgs

def main():
    if not GUILD_ID:
        raise RuntimeError("GUILD_ID env variable is not set.")
    if not CHANNEL_IDS:
        raise RuntimeError("CHANNEL_IDS env variable is not set.")

    now = datetime.utcnow()
    start = now - timedelta(days=WEEK_DAYS)
    after_ms = int(start.timestamp() * 1000)

    guild_url = f"{API_BASE}/guilds/{GUILD_ID}/channels"
    resp = requests.get(guild_url, headers=HEADERS)
    resp.raise_for_status()
    all_channels = resp.json()

    channel_info = {ch["id"]: ch for ch in all_channels if ch.get("type") == 0}
    category_names = {ch["id"]: ch["name"] for ch in all_channels if ch.get("type") == 4}

    grouped = {}
    for chan in CHANNEL_IDS:
        ch = channel_info.get(chan)
        parent = ch.get("parent_id") if ch else None
        cat = category_names.get(parent, "Uncategorized")
        grouped.setdefault(cat, []).append(chan)

    client = get_sheets_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    for category, chans in grouped.items():
        try:
            worksheet = spreadsheet.worksheet(category)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=category, rows="1000", cols="5")

        worksheet.append_row(["channel_id", "message_id", "author", "timestamp", "content"])
        for chan in chans:
            msgs = fetch_messages(chan, after_ms)
            for m in msgs:
                ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                worksheet.append_row([
                    chan,
                    m["id"],
                    m["author"]["username"],
                    ts.isoformat(),
                    m.get("content", "")
                ])

if __name__ == "__main__":
    main()
