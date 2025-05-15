#!/usr/bin/env python3
import os
import json
import asyncio
from datetime import datetime, timedelta

import discord      # pip install discord.py-self
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Настройки ===
DB_PATH     = os.path.join(os.getcwd(), "leveldb")
# Список ID каналов: задаётся через секрет CHANNEL_IDS_JSON (формат JSON-массив или CSV)
raw_ids    = os.environ.get("CHANNEL_IDS_JSON", "")
if raw_ids:
    try:
        CHANNEL_IDS = json.loads(raw_ids)
    except json.JSONDecodeError:
        CHANNEL_IDS = [int(x) for x in raw_ids.split(",") if x]
else:
    CHANNEL_IDS = []

WEEK_DAYS    = 7
SHEET_ID     = os.environ["GOOGLE_SHEET_ID"]
CREDS_JSON   = os.environ["GOOGLE_CREDS_JSON"]["GOOGLE_CREDS_JSON"]
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
            ws = sheet.add_worksheet(title="archive", rows="2000", cols="7")

        # Заголовок с именем и номером подсети
        ws.append_row([
            "channel_id", "channel_name", "subnet_number",
            "message_id", "author", "timestamp", "content"
        ])

        total = 0
        # Сбор сообщений
        for cid in CHANNEL_IDS:
            # Пытаемся получить канал из кеша, иначе вытаскиваем по API
            channel = client.get_channel(cid)
            if channel is None:
                try:
                    channel = await client.fetch_channel(cid)
                except Exception as e:
                    print(f"[ERROR] Cannot fetch channel {cid}: {e}")
                    continue

            name = getattr(channel, 'name', '')
            # номер подсети: последняя часть после дефиса
            try:
                num = int(name.split('-')[-1])
            except:
                num = ''

            try:
                async for msg in channel.history(limit=None, after=cutoff):
                    total += 1
                    ws.append_row([
                        str(cid), name, num,
                        str(msg.id), msg.author.name,
                        msg.created_at.isoformat(),
                        msg.content.replace("
", " ")
                    ])
            except Exception as e:
                print(f"[ERROR] Could not read history for {cid}: {e}")
                continue

        print(f"[INFO] Found {total} messages in total.")
        await client.close()

    # Запуск клиента в режиме user (self‑bot)
    await client.start(USER_TOKEN)

if __name__ == "__main__":
    asyncio.run(fetch_and_sheet())
