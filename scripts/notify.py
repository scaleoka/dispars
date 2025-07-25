#!/usr/bin/env python3
import os
import asyncio
import json
import requests
from datetime import datetime, timedelta, timezone
import discord  # from discord.py-self

print("✅ discord loaded from:", discord.__file__)

DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUBNET_CONFIGS = json.loads(os.environ["SUBNET_CONFIG_JSON"])

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
        print(f"[ERROR] Telegram send failed to {chat_id}: {e}")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

channel_id_to_subnet = {cfg["DISCORD_CHANNEL_ID"]: sid for sid, cfg in SUBNET_CONFIGS.items()}

@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    after = datetime.now(timezone.utc) - timedelta(minutes=15)

    for subnet, cfg in SUBNET_CONFIGS.items():
        try:
            chan = await client.fetch_channel(cfg["DISCORD_CHANNEL_ID"])
            print(f"[INFO] Checking backlog for subnet {subnet} after {after.isoformat()}...")
            async for msg in chan.history(limit=100, after=after):
                if msg.author.id != client.user.id:
                    text = f"<b>{msg.author.name}</b>: {msg.content}"
                    send_telegram_message(cfg["TELEGRAM_CHAT_ID"], text)
        except Exception as e:
            print(f"[ERROR] Failed to fetch history for {subnet}: {e}")

@client.event
async def on_message(message):
    if datetime.now(timezone.utc) >= END_TIME:
        print("[INFO] Time exceeded. Shutting down.")
        await client.close()
        return

    channel_id = message.channel.id
    if channel_id not in channel_id_to_subnet:
        return
    if message.author == client.user:
        return

    subnet = channel_id_to_subnet[channel_id]
    chat_id = SUBNET_CONFIGS[subnet]["TELEGRAM_CHAT_ID"]
    text = f"<b>{message.author.name}</b>: {message.content}"
    send_telegram_message(chat_id, text)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
