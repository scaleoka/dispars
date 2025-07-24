import sys
import os
import asyncio
import requests
from datetime import datetime, timedelta

# Удаляем конфликтующие модули и пути
if "discord" in sys.modules:
    del sys.modules["discord"]
if os.getcwd() in sys.path:
    sys.path.remove(os.getcwd())

# Импорт нужного discord
import discord
print("\u2705 discord loaded from:", discord.__file__)

# === Настройки ===
DISCORD_CHANNEL_ID = 1375534889486778409
DISCORD_USER_TOKEN = os.environ["DISCORD_USER_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Время окончания работы (конец текущего часа)
END_TIME = datetime.utcnow().replace(minute=59, second=59, microsecond=0)


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
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"[INFO] Logged in as {client.user} (ID: {client.user.id})")

    # Получаем непрочитанные сообщения за предыдущий час
    now = datetime.utcnow()
    prev_hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    prev_hour_end = prev_hour_start + timedelta(hours=1)

    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        print("[ERROR] Channel not found")
        await client.close()
        return

    async for message in channel.history(after=prev_hour_start, before=prev_hour_end, oldest_first=True):
        if message.author != client.user:
            msg_text = f"<b>{message.author.name}</b>: {message.content}"
            send_telegram_message(msg_text)


@client.event
async def on_message(message):
    if datetime.utcnow() > END_TIME:
        print("[INFO] Time's up. Exiting.")
        await client.close()
        return

    if message.channel.id != DISCORD_CHANNEL_ID:
        return
    if message.author == client.user:
        return

    msg_text = f"<b>{message.author.name}</b>: {message.content}"
    send_telegram_message(msg_text)


if __name__ == "__main__":
    asyncio.run(client.start(DISCORD_USER_TOKEN))
