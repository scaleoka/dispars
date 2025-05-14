#!/usr/bin/env python3
import os
import json
import asyncio
from datetime import datetime, timedelta

import discord      # pip install discord.py-self
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Настройки ===
CHANNEL_IDS = [
    1349119225868058644,
    1349121405903573114
]
WEEK_DAYS    = 7
SHEET_ID     = os.environ["GOOGLE_SHEET_ID"]
CREDS_JSON   = os.environ["GOOGLE_CREDS_JSON"]
USER_TOKEN   = os.environ["DISCORD_USER_TOKEN"]

# Инициализация Google Sheets
creds_info = json.loads(CREDS_JSON)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
gs_client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope))

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
            ws = sheet.add_worksheet(title="archive", rows="2000", cols="5")

        # Заголовок
        ws.append_row(["channel_id", "message_id", "author", "timestamp", "content"])

        # Сбор сообщений
        for cid in CHANNEL_IDS:
            channel = client.get_channel(cid)
            if channel is None:
                print(f"[WARN] Channel {cid} not found, skipping.")
                continue

            async for msg in channel.history(limit=None, after=cutoff):
                ws.append_row([
                    str(cid),
                    str(msg.id),
                    msg.author.name,
                    msg.created_at.isoformat(),
                    msg.content.replace("\n", " ")
                ])

        print("[INFO] Done writing to Google Sheets.")
        await client.close()

    await client.start(USER_TOKEN, bot=False)

if __name__ == "__main__":
    asyncio.run(fetch_and_sheet())
