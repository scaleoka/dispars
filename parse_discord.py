import os
import time
import json
import re
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# env vars
TOKEN = os.getenv("DISCORD_USER_TOKEN")
CHANNEL_IDS = [c for c in re.split(r"[\s,]+", os.getenv("CHANNEL_IDS","")) if c]
WEEK_DAYS = int(os.getenv("WEEK_DAYS","7"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# Google Sheets client
def get_sheets():
    info = json.loads(CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scopes)
    return gspread.authorize(creds)

# Скроллим канал, собираем сообщения из DOM
def scrape_channel(page, chan_id, cutoff_ts):
    url = f"https://discord.com/channels/{os.getenv('GUILD_ID')}/{chan_id}"
    page.goto(url)
    # вставляем токен в localStorage и перезагружаем
    page.evaluate(f"""() => {{ 
        window.localStorage.token = "{TOKEN}";
    }}""")
    page.reload()

    messages = []
    last_height = 0
    while True:
        # Парсим видимые сообщения
        elems = page.query_selector_all("div.message-2qnXI6")
        for el in elems:
            try:
                ts = el.query_selector("time") .get_attribute("datetime")
                t = datetime.fromisoformat(ts.replace("Z","+00:00"))
            except:
                continue
            if (datetime.utcnow() - t).days > WEEK_DAYS:
                return messages
            author = el.query_selector("h2 .username-1A8OIy").inner_text()
            content_el = el.query_selector("div.markup-2BOw-j")
            text = content_el.inner_text() if content_el else ""
            msg_id = el.get_attribute("id") or ""
            item = {"id": msg_id, "author":author, "timestamp":t.isoformat(), "content": text}
            if item not in messages:
                messages.append(item)

        # Скроллим наверх, пока не упремся в cutoff
        page.keyboard.press("PageUp")
        time.sleep(0.5)
        new_height = page.evaluate("document.scrollingElement.scrollTop")
        if abs(new_height - last_height) < 10:
            break
        last_height = new_height

    return messages

def main():
    sheet = get_sheets().open_by_key(SHEET_ID)
    cutoff = datetime.utcnow() - timedelta(days=WEEK_DAYS)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for chan in CHANNEL_IDS:
            print(f"Scraping {chan} …")
            msgs = scrape_channel(page, chan, cutoff)
            print(f" → got {len(msgs)} messages")
            # создаём лист
            try:
                ws = sheet.worksheet(chan)
                ws.clear()
            except:
                ws = sheet.add_worksheet(title=chan, rows="1000", cols="5")
            ws.append_row(["channel_id","message_id","author","timestamp","content"])
            for m in msgs:
                ws.append_row([chan, m["id"], m["author"], m["timestamp"], m["content"]])
        browser.close()

if __name__=="__main__":
    main()
