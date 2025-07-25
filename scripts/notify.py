#!/usr/bin/env python3
import os
import sys
import asyncio
import requests
import json
from datetime import datetime, timedelta, timezone
import discord  # from discord.py-self

print("✅ discord loaded from:", discord.__file__)

# === Discord → Telegram маппинг ===
# Пример: {"1358854051634221328": "-4864009644", ...}
CHANNEL_MAP = json.loads(os.environ["CHANNEL_MAP_JSON"])

DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# Завершение через 4 часа
END_TIME = datetime.now(timezone.utc) + timedelta(hours=4)

# === Telegram ===
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

# === Discord Client ===
client = discord.Client()

@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    now = datetime.now(timezone.utc)
    after = now - timedelta(minutes=10)

    for discord_channel_id_str, telegram_chat_id in CHANNEL_MAP.items():
        discord_channel_id = int(discord_channel_id_str)
        try:
            channel = await client.fetch_channel(discord_channel_id)
            print(f"[INFO] Fetching messages from {discord_channel_id} between {after.isoformat()} and {now.isoformat()}...")
            async for msg in channel.history(limit=100):
                if after <= msg.created_at <= now and msg.author.id != client.user.id:
                    text = f"<b>{msg.author.name}</b>: {msg.content}"
                    send_telegram_message(telegram_chat_id, text)
        except Exception as e:
            print(f"[ERROR] Failed fetching for {discord_channel_id}: {e}")

@client.event
async def on_message(message):
    now = datetime.now(timezone.utc)
    if now >= END_TIME:
        print("[INFO] 4 часа истекли, выходим.")
        await client.close()
        return

    channel_id_str = str(message.channel.id)
    if channel_id_str in CHANNEL_MAP and message.author != client.user:
        text = f"<b>{message.author.name}</b>: {message.content}"
        send_telegram_message(CHANNEL_MAP[channel_id_str], text)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
