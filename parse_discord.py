#!/usr/bin/env python3
import os, json, re, time
import discum
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

# env
TOKEN = os.getenv("DISCORD_USER_TOKEN")
RAW_IDS = os.getenv("CHANNEL_IDS","")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", RAW_IDS) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS","7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# Sheets client
def get_sheets():
    info = json.loads(CREDS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        info,
        ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

# Новый fetch через gateway
def fetch_via_gateway(bot, channel_id, cutoff_ms):
    messages = []
    def collector(resp, guild_id, channel_id):
        for m in resp.json():
            ts = int(datetime.fromisoformat(m["timestamp"].replace("Z","+00:00")).timestamp()*1000)
            if ts < cutoff_ms:
                bot.gateway.close()        # остановить дальнейший прогон
                return
            messages.append(m)
        # дёргаем ещё, начиная с последнего
        bot.gateway.fetchMessages(channel_id, num=100, before=messages[-1]["id"])

    # навешиваем collector и первый запрос
    bot.gateway.command(collector)
    bot.gateway.fetchMessages(channel_id, num=100)
    bot.gateway.run()  # блокирующий вызов, пока не закроем gateway  
    return messages

def main():
    cutoff_ms = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp()*1000)
    bot = discum.Client(token=TOKEN, log=False)
    sheet = get_sheets().open_by_key(SHEET_ID)

    for chan in CHANNEL_IDS:
        cutoff = cutoff_ms
        msgs = fetch_via_gateway(bot, chan, cutoff)
        print(f"[INFO] Channel {chan}: fetched {len(msgs)} msgs")
        # записываем
        try: ws = sheet.worksheet(chan)
        except: ws = sheet.add_worksheet(title=chan, rows="1000", cols="5")
        ws.clear()
        ws.append_row(["channel_id","message_id","author","timestamp","content"])
        for m in msgs:
            ts = datetime.fromisoformat(m["timestamp"].replace("Z","+00:00"))
            ws.append_row([chan, m["id"], m["author"]["username"], ts.isoformat(), m.get("content","")])

if __name__=="__main__":
    main()
