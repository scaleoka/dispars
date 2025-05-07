#!/usr/bin/env python3
import os, json, re, time
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# --- Настройки из окружения ---
TOKEN = os.getenv("DISCORD_USER_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
RAW_IDS = os.getenv("CHANNEL_IDS", "")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", RAW_IDS) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS","7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# --- Инициализация Google Sheets ---
def get_sheets():
    info = json.loads(CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scopes)
    return gspread.authorize(creds)

# --- Основной скрипт ---
def main():
    cutoff = int((datetime.utcnow() - timedelta(days=WEEK_DAYS)).timestamp() * 1000)
    sheet = get_sheets().open_by_key(SHEET_ID)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        # Вставляем token в localStorage
        page.goto("https://discord.com/app")
        page.evaluate(f"""() => {{ window.localStorage.setItem('token', "{TOKEN}"); }}""")
        page.reload()

        for chan in CHANNEL_IDS:
            collected = []
            print(f"=== Parsing channel {chan} ===")
            # Перехват XHR
            page.on("response", lambda resp: _on_response(resp, chan, cutoff, collected))
            # Открываем URL канала
            page.goto(f"https://discord.com/channels/{GUILD_ID}/{chan}")
            # Скроллим вверх, пока не собрали всё
            last_scroll = None
            while True:
                page.keyboard.press("PageUp")
                time.sleep(0.3)
                scroll = page.evaluate("document.scrollingElement.scrollTop")
                if last_scroll is not None and scroll == last_scroll:
                    break
                last_scroll = scroll

            print(f"Collected {len(collected)} messages for {chan}")
            # Записываем в Google Sheets
            try:
                ws = sheet.worksheet(chan)
                ws.clear()
            except:
                ws = sheet.add_worksheet(title=chan, rows="1000", cols="5")
            ws.append_row(["channel_id","message_id","author","timestamp","content"])
            for m in collected:
                ts = datetime.fromisoformat(m["timestamp"].replace("Z","+00:00"))
                ws.append_row([chan, m["id"], m["author"]["username"], ts.isoformat(), m.get("content","")])

        browser.close()

# Функция-коллектор для XHR-ответов
def _on_response(response, channel_id, cutoff_ms, collector):
    url = response.url
    if f"/api/v9/channels/{channel_id}/messages" not in url:
        return
    try:
        data = response.json()
    except:
        return
    for m in data:
        ts = int(datetime.fromisoformat(m["timestamp"].replace("Z","+00:00")).timestamp()*1000)
        if ts < cutoff_ms:
            return
        collector.append(m)

if __name__ == "__main__":
    main()
