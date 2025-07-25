#!/usr/bin/env python3
import asyncio
import json
import os
import requests
import html
from datetime import datetime, timedelta, timezone
import discord  # dolfies/discord.py-self

print("✅ discord loaded from:", discord.__file__, flush=True)

# ───── Загрузка переменных окружения ─────
DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CONFIG_JSON = os.environ["SUBNET_CONFIG_JSON"]

try:
    SUBNET_CONFIGS = json.loads(CONFIG_JSON)
except Exception as e:
    print(f"[ERROR] Failed to parse SUBNET_CONFIG_JSON: {e}", flush=True)
    exit(1)

# ───── Время завершения работы ─────
END_TIME = datetime.now(timezone.utc) + timedelta(hours=4)

# ───── Отправка сообщений в Telegram ─────
def send_telegram_message(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=5)
        print(f"[TELEGRAM] Status {resp.status_code} | {text}", flush=True)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}", flush=True)

# ───── Discord client ─────
client = discord.Client()

# ───── При запуске клиента ─────
@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})", flush=True)

    for subnet_id, conf in SUBNET_CONFIGS.items():
        try:
            channel = await client.fetch_channel(conf["DISCORD_CHANNEL_ID"])
            after = datetime.now(timezone.utc) - timedelta(minutes=15)
            print(f"[INFO] Fetching history for subnet {subnet_id} after {after.isoformat()}", flush=True)

            async for msg in channel.history(limit=100, after=after):
                if not msg.author.bot and msg.content.strip():
                    safe_content = html.escape(msg.content)
                    text = f"<pre>{msg.author.name}: {safe_content}</pre>"
                    print(f"[DISCORD-HISTORY] {text}", flush=True)
                    send_telegram_message(conf["TELEGRAM_CHAT_ID"], text)
        except Exception as e:
            print(f"[ERROR] Failed for subnet {subnet_id}: {e}", flush=True)
            send_telegram_message(conf["TELEGRAM_CHAT_ID"], f"<b>ERROR in {subnet_id}</b>: {html.escape(str(e))}")

# ───── При новом сообщении в Discord ─────
@client.event
async def on_message(message):
    now = datetime.now(timezone.utc)
    if now >= END_TIME:
        print("[INFO] Reached timeout, exiting.", flush=True)
        await client.close()
        return

    for subnet_id, conf in SUBNET_CONFIGS.items():
        if message.channel.id == conf["DISCORD_CHANNEL_ID"]:
            try:
                if not message.author.bot and message.content.strip():
                    safe_content = html.escape(message.content)
                    text = f"<b>{message.author.name}</b>: {safe_content}"
                    print(f"[DISCORD-REALTIME] {text}", flush=True)
                    send_telegram_message(conf["TELEGRAM_CHAT_ID"], text)
            except Exception as e:
                print(f"[ERROR] Realtime message error in subnet {subnet_id}: {e}", flush=True)

# ───── Запуск ─────
if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
