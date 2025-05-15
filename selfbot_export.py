#!/usr/bin/env python3
import os
import json
import asyncio
from datetime import datetime, timedelta

import discord      # pip install discord.py-self
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Настройки ===
# CHANNEL_IDS_JSON приходит как CSV через секрет: "id1,id2,id3"
raw_ids = os.environ.get("CHANNEL_IDS", "")
if raw_ids:
    CHANNEL_IDS = [int(x.strip()) for x in raw_ids.split(",") if x.strip()]
else:
    CHANNEL_IDS = []

WEEK_DAYS  = 7
SHEET_ID   = os.environ["GOOGLE_SHEET_ID"]
CREDS_JSON = os.environ["GOOGLE_CREDS_JSON"]
USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]

# Инициализация Google Sheets
creds_info = json.loads(CREDS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
gs_client = gspread.authorize(
    ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
)

async def fetch_and_sheet():
    client = discord.Client()

    @client.event
    async def on_ready():
        cutoff = datetime.utcnow() - timedelta(days=WEEK_DAYS)
        sheet = gs_client.open_by_key(SHEET_ID)
        try:
            ws = sheet.worksheet("archive")
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title="archive", rows="2000", cols="7")

        # Заголовок с каналом, именем и номером подсети
        ws.append_row([
            "channel_id", "channel_name", "subnet_number",
            "message_id", "author", "timestamp", "content"
        ])

        total = 0
        for cid in CHANNEL_IDS:
            print(f"[DEBUG] Trying channel {cid}...")
            try:
                channel = client.get_channel(cid) or await client.fetch_channel(cid)
                print(f"[DEBUG] Resolved: {channel} (name={getattr(channel,'name',None)})")
            except Exception as e:
                print(f"[ERROR] Cannot resolve channel {cid}: {e}")
                continue

            name = getattr(channel, 'name', '')
            try:
                num = int(name.split('-')[-1])
            except:
                num = ''

            count_this = 0
            try:
                async for msg in channel.history(limit=None, after=cutoff):
                    count_this += 1
                    total += 1
                    ws.append_row([
                        str(cid), name, num,
                        str(msg.id), msg.author.name,
                        msg.created_at.isoformat(),
                        msg.content.replace("\n", " ")
                    ])
            except Exception as e:
                print(f"[ERROR] Could not read history {cid}: {e}")
                continue

            print(f"[DEBUG] Fetched {count_this} messages for channel {cid}")

        print(f"[INFO] Found {total} messages in total.")
        await client.close()

    await client.start(USER_TOKEN)

if __name__ == "__main__":
    asyncio.run(fetch_and_sheet())
