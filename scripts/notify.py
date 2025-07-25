#!/usr/bin/env python3
import asyncio
import json
import os
import requests
from datetime import datetime, timedelta, timezone
import discord  # from dolfies/discord.py-self

print("✅ discord loaded from:", discord.__file__)

DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CONFIG_JSON = os.environ["SUBNET_CONFIG_JSON"]

try:
    SUBNET_CONFIGS = json.loads(CONFIG_JSON)
except Exception as e:
    print(f"[ERROR] Failed to parse SUBNET_CONFIG_JSON: {e}")
    exit(1)

END_TIME = datetime.now(timezone.utc) + timedelta(hours=4)

def send_telegram_message(chat_id: str, text: str):
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

client = discord.Client()

@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    for subnet_id, conf in SUBNET_CONFIGS.items():
        try:
            channel = await client.fetch_channel(conf["DISCORD_CHANNEL_ID"])
            after = datetime.now(timezone.utc) - timedelta(minutes=15)
            print(f"[INFO] Fetching for subnet {subnet_id} after {after.isoformat()}")

            async for msg in channel.history(limit=100, after=after):
                if msg.author.id != client.user.id:
                    text = f"<b>{msg.author.name}</b>: {msg.content}"
                    send_telegram_message(conf["TELEGRAM_CHAT_ID"], text)
        except Exception as e:
            print(f"[ERROR] Failed for subnet {subnet_id}: {e}")

@client.event
async def on_message(message):
    now = datetime.now(timezone.utc)
    if now >= END_TIME:
        print("[INFO] Reached timeout, exiting.")
        await client.close()
        return

    for conf in SUBNET_CONFIGS.values():
        if message.channel.id == conf["DISCORD_CHANNEL_ID"] and message.author.id != client.user.id:
            text = f"<b>{message.author.name}</b>: {message.content}"
            send_telegram_message(conf["TELEGRAM_CHAT_ID"], text)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
