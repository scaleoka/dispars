#!/usr/bin/env python3
import os
import asyncio
import requests
import json
import re
from datetime import datetime, timedelta, timezone
import discord  # from discord.py-self

print("✅ discord loaded from:", discord.__file__)

# === Discord → Telegram маппинг ===
CHANNEL_MAP = json.loads(os.environ["CHANNEL_MAP_JSON"])

DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# Завершение через 4 часа
END_TIME = datetime.now(timezone.utc) + timedelta(hours=4)

# === Telegram ===
def escape_html(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

def sanitize_message_content(content: str) -> str:
    # Удалим упоминания вроде <@1234567890>
    content = re.sub(r"<@!?(\d+)>", "@user", content)
    return escape_html(content)

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=5)
        if not resp.ok:
            print(f"[ERROR] Telegram send failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"[ERROR] Telegram send exception: {e}")

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
            print(f"[INFO] Fetching messages from {discord_channel_id} since {after.isoformat()}...")

            async for msg in channel.history(limit=100, after=after):
                if msg.author.id == client.user.id:
                    continue
                clean = sanitize_message_content(msg.content)
                text = f"<b>{escape_html(msg.author.name)}</b>: {clean}"
                print(f"[INFO] Sending message from {msg.author.name} in channel {discord_channel_id}")
                send_telegram_message(telegram_chat_id, text)
        except Exception as e:
            print(f"[ERROR] Failed fetching from {discord_channel_id}: {e}")

@client.event
async def on_message(message):
    now = datetime.now(timezone.utc)
    if now >= END_TIME:
        print("[INFO] 4 часа истекли, выходим.")
        await client.close()
        return

    channel_id_str = str(message.channel.id)
    if channel_id_str in CHANNEL_MAP and message.author.id != client.user.id:
        clean = sanitize_message_content(message.content)
        text = f"<b>{escape_html(message.author.name)}</b>: {clean}"
        print(f"[INFO] Live message from {message.author.name} in channel {channel_id_str}")
        send_telegram_message(CHANNEL_MAP[channel_id_str], text)

@client.event
async def on_error(event, *args, **kwargs):
    print(f"[ERROR] Uncaught error in {event}: {args}, {kwargs}")

if __name__ == "__main__":
    print("[DEBUG] Starting Discord client...")
    try:
        asyncio.run(client.start(DISCORD_USER_TOKEN))
    except Exception as e:
        print(f"[FATAL] Discord client failed to start: {e}")
