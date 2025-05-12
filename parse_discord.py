#!/usr/bin/env python3
import os, json, asyncio
from datetime import datetime, timedelta

import discord
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ─── Environment ───────────────────────────────────────────────
BOT_TOKEN         = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_IDS       = [c for c in os.getenv("CHANNEL_IDS","").split(",") if c]
WEEK_DAYS         = int(os.getenv("WEEK_DAYS","7"))
GOOGLE_SHEET_ID   = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
# ────────────────────────────────────────────────────────────────

def get_sheets_client():
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

async def fetch_and_write():
    cutoff = datetime.utcnow() - timedelta(days=WEEK_DAYS)
    sheet = get_sheets_client().open_by_key(GOOGLE_SHEET_ID)
    # запрашиваем привилегированный интент
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        for chan_id in CHANNEL_IDS:
            channel = client.get_channel(int(chan_id))
            # создаём или очищаем страницу
            try:
                ws = sheet.worksheet(chan_id)
                ws.clear()
            except gspread.exceptions.WorksheetNotFound:
                ws = sheet.add_worksheet(title=chan_id, rows="1000", cols="5")
            ws.append_row(["channel_id","message_id","author","timestamp","content"])
            # вытаскиваем историю
            msgs = await channel.history(after=cutoff, oldest_first=True, limit=None).flatten()
            for m in msgs:
                ws.append_row([
                    chan_id,
                    m.id,
                    m.author.name,
                    m.created_at.isoformat(),
                    m.content
                ])
        await client.close()

    await client.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(fetch_and_write())
