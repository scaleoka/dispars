import sys
import os

# Удаляем модуль discord, если случайно был импортирован из неверного места
if "discord" in sys.modules:
    del sys.modules["discord"]

# Убираем текущую директорию из sys.path, если она мешает
cwd = os.getcwd()
if cwd in sys.path:
    sys.path.remove(cwd)

# Теперь импортируем правильный discord
import discord
print("✅ discord loaded from:", discord.__file__)

#!/usr/bin/env python3
import os
import asyncio
import requests
import discord  # pip install discord.py-self

# === Настройки ===
DISCORD_CHANNEL_ID = 1375534889486778409
DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

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

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID:
        return
    if message.author == client.user:
        return

    msg_text = f"<b>{message.author.name}</b>: {message.content}"
    send_telegram_message(msg_text)

if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))

