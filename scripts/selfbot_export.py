#!/usr/bin/env python3
import asyncio
import json
import os
import requests
from datetime import datetime, timedelta, timezone
import discord  # from dolfies/discord.py-self

print("✅ discord loaded from:", discord.__file__, flush=True)

DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CONFIG_JSON = os.environ["SUBNET_CONFIG_JSON"]

try:
    SUBNET_CONFIGS = json.loads(CONFIG_JSON)
except Exception as e:
    print(f"[ERROR] Failed to parse SUBNET_CONFIG_JSON: {e}", flush=True)
    exit(1)

END_TIME = datetime.now(timezone.utc) + timedelta(hours=4)

# ───── Отправка plain text сообщений в Telegram ─────
def send_telegram_message(chat_id: str, text: str):
    payload = {
        "chat_id": chat_id,
        "text": text,  # Никаких Markdown или HTML!
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            timeout=5
        )
        print(f"[TELEGRAM] Status {resp.status_code} | {text}", flush=True)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}", flush=True)

# ───── Discord client ─────
client = discord.Client()

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
                    raw = f"{msg.author.name}: {msg.content}"
                    print(f"[DISCORD-HISTORY] {raw}", flush=True)
                    send_telegram_message(conf["TELEGRAM_CHAT_ID"], raw)
        except Exception as e:
            print(f"[ERROR] Failed for subnet {subnet_id}: {e}", flush=True)
            send_telegram_message(conf["TELEGRAM_CHAT_ID"], f"ERROR in {subnet_id}: {str(e)}")

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
                    raw = f"{message.author.name}: {message.content}"
                    print(f"[DISCORD-REALTIME] {raw}", flush=True)
                    send_telegram_message(conf["TELEGRAM_CHAT_ID"], raw)
            except Exception as e:
                print(f"[ERROR] Realtime message error in subnet {subnet_id}: {e}", flush=True)

# ───── Запуск клиента ─────
if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
