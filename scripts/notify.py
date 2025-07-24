#!/usr/bin/env python3
import os
import sys
import asyncio
import requests
import discord
from datetime import datetime, timedelta, timezone

# --- Очистка окружения ---
if "discord" in sys.modules:
    del sys.modules["discord"]
if os.getcwd() in sys.path:
    sys.path.remove(os.getcwd())

print("✅ discord loaded from:", discord.__file__)

# --- Настройки ---
DISCORD_CHANNEL_ID = 1375534889486778409
DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

sent_message_ids = set()

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

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    # --- Чтение истории за час ---
    channel = await client.fetch_channel(DISCORD_CHANNEL_ID)
    since_time = datetime.now(timezone.utc) - timedelta(hours=1)
    print(f"[INFO] Checking messages since {since_time.isoformat()}")

    async for msg in channel.history(limit=100, after=since_time):
        if msg.author == client.user:
            continue
        if msg.id in sent_message_ids:
            continue
        msg_text = f"<b>{msg.author.name}</b>: {msg.content}"
        send_telegram_message(msg_text)
        sent_message_ids.add(msg.id)

    print("[INFO] Listening for new messages for 1 hour...")
    await asyncio.sleep(60 * 60)
    print("[INFO] Timeout reached. Logging out.")
    await client.close()

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID:
        return
    if message.author == client.user:
        return
    if message.id in sent_message_ids:
        return

    msg_text = f"<b>{message.author.name}</b>: {message.content}"
    send_telegram_message(msg_text)
    sent_message_ids.add(message.id)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
