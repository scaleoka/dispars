#!/usr/bin/env python3
import asyncio
import json
import os
import requests
from datetime import datetime, timedelta, timezone
import discord  # from dolfies/discord.py-self

print("✅ discord loaded from:", discord.__file__)

# ───── Чтение конфигов из переменных окружения ─────
DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CONFIG_JSON = os.environ["SUBNET_CONFIG_JSON"]

try:
    SUBNET_CONFIGS = json.loads(CONFIG_JSON)
except Exception as e:
    print(f"[ERROR] Failed to parse SUBNET_CONFIG_JSON: {e}")
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
        response = requests.post(url, data=payload, timeout=5)
        if response.status_code == 200:
            print(f"[TELEGRAM ✅] Sent to chat {chat_id}: {text}")
        else:
            print(f"[TELEGRAM ❌] Failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

# ───── Discord client ─────
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# ───── При подключении ─────
@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    for subnet_id, conf in SUBNET_CONFIGS.items():
        try:
            channel = await client.fetch_channel(conf["DISCORD_CHANNEL_ID"])
            after = datetime.now(timezone.utc) - timedelta(minutes=15)
            print(f"[INFO] Fetching history for subnet {subnet_id} after {after.isoformat()}")

            async for msg in channel.history(limit=100, after=after):
                if not msg.author.bot:
                    text = f"<b>{msg.author.name}</b>: {msg.content}"
                    print(f"[DISCORD ⏪] {msg.created_at.isoformat()} | {text}")
                    send_telegram_message(conf["TELEGRAM_CHAT_ID"], text)
        except Exception as e:
            print(f"[ERROR] Failed for subnet {subnet_id}: {e}")

# ───── При поступлении нового сообщения ─────
@client.event
async def on_message(message):
    now = datetime.now(timezone.utc)
    if now >= END_TIME:
        print("[INFO] Reached timeout, exiting.")
        await client.close()
        return

    for subnet_id, conf in SUBNET_CONFIGS.items():
        if message.channel.id == conf["DISCORD_CHANNEL_ID"]:
            if not message.author.bot:
                text = f"<b>{message.author.name}</b>: {message.content}"
                print(f"[DISCORD 📩] {datetime.now().isoformat()} | Subnet {subnet_id} | {text}")
                send_telegram_message(conf["TELEGRAM_CHAT_ID"], text)

# ───── Запуск клиента ─────
if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
