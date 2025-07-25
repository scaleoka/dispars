#!/usr/bin/env python3
import os
import sys
import asyncio
import requests
from datetime import datetime, timedelta, timezone
import discord  # from discord.py-self

print("✅ discord loaded from:", discord.__file__)

# === Настройки ===
DISCORD_CHANNEL_ID = 1375534889486778409
DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Время завершения через 4 часа
START_TIME = datetime.now(timezone.utc)
END_TIME = START_TIME + timedelta(hours=4)

# === Telegram ===
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

# === Discord Client ===
client = discord.Client()  # без intents

@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    # Получаем сообщения за предыдущий час
    now = datetime.now(timezone.utc)
    after = now - timedelta(hours=1)
    before = now
    channel = await client.fetch_channel(DISCORD_CHANNEL_ID)

    print(f"[INFO] Fetching messages between {after.isoformat()} and {before.isoformat()}...")
    async for msg in channel.history(limit=100, after=after, before=before):
        if msg.author.id != client.user.id:
            text = f"<b>{msg.author.name}</b>: {msg.content}"
            send_telegram_message(text)

@client.event
async def on_message(message):
    now = datetime.now(timezone.utc)
    if now >= END_TIME:
        print("[INFO] 4 hours passed, closing connection.")
        await client.close()
        return

    if message.channel.id != DISCORD_CHANNEL_ID:
        return
    if message.author == client.user:
        return

    text = f"<b>{message.author.name}</b>: {message.content}"
    send_telegram_message(text)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
