#!/usr/bin/env python3
import os
import sys
import asyncio
import requests
from datetime import datetime, timedelta, timezone
import discord  # from discord.py-self
import json

print("✅ discord loaded from:", discord.__file__)

# === Discord → Telegram маппинг ===
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
    after = now - timedelta(hours=1)

    # Ищем сообщения за предыдущий час
    for discord_channel_id, telegram_chat_id in CHANNEL_MAP.items():
        try:
            channel = await client.fetch_channel(discord_channel_id)
            async for msg in channel.history(limit=100, after=after):
                if msg.author.id != client.user.id:
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

    if message.channel.id in CHANNEL_MAP and message.author != client.user:
        text = f"<b>{message.author.name}</b>: {message.content}"
        send_telegram_message(CHANNEL_MAP[message.channel.id], text)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
