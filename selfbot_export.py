#!/usr/bin/env python3
import os, json, asyncio
from datetime import datetime, timedelta

import discord      # pip install discord.py-self
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# config
CHANNEL_IDS = [1349119225868058644, 1349121405903573114]
WEEK_DAYS    = 7
SHEET_ID     = os.environ["GOOGLE_SHEET_ID"]
CREDS        = json.loads(os.environ["GOOGLE_CREDS_JSON"])
USER_TOKEN   = os.environ["DISCORD_USER_TOKEN"]

# Sheets client
scope = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
gs = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(CREDS, scope))
ws = None

async def fetch_and_sheet():
    global ws
    client = discord.Client()

    @client.event
    async def on_ready():
        nonlocal ws
        cutoff = datetime.utcnow() - timedelta(days=WEEK_DAYS)
        sheet = gs.open_by_key(SHEET_ID)
        try:
            ws = sheet.worksheet("archive")
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet("archive", rows="2000", cols="5")
        ws.append_row(["channel_id","message_id","author","timestamp","content"])

        for cid in CHANNEL_IDS:
            ch = client.get_channel(cid)
            if not ch:
                print(f"[WARN] channel {cid} not found")
                continue

            async for m in ch.history(limit=None, after=cutoff):
                ws.append_row([
                  str(cid),
                  str(m.id),
                  m.author.name,
                  m.created_at.isoformat(),
                  m.content
                ])
        print("[INFO] Done.")
        await client.close()

    await client.start(USER_TOKEN, bot=False)

if __name__=="__main__":
    asyncio.run(fetch_and_sheet())
