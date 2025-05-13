#!/usr/bin/env python3
import os, json
from datetime import datetime, timedelta
import plyvel
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Настройки (отредактируйте под себя) ===

# Путь к распакованной LevelDB-копии (скопируйте %APPDATA%\discord\Local Storage\leveldb сюда)
DB_PATH = os.path.expanduser("leveldb")

# Сервис-аккаунт JSON из Google Cloud (либо путь, либо храните тут содержимое)
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")  # предпочительно из GitHub Secrets
# или если хотите из файла:
# CREDS_JSON = open("creds.json", "r").read()

# ID Google Sheet и список каналов
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CHANNEL_IDS = {
    "1349119225868058644","1349121405903573114","1349122541754515538",
    "1264939518641963070","1353733356470276096","1342559689690583202",
    "1347299108238397572","1358854051634221328","1361438967198908577",
    "1361761424153645217","1364253568961609859","1364655778149171250",
    "1366426072765431808","1366426973781364816","1366845111945658409",
    "1366897804068393000"
}

# Сколько дней назад брать
WEEK_DAYS = 7

# ============================================

def get_sheets_client():
    if not CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON не установлено")
    info = json.loads(CREDS_JSON)
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
    return gspread.authorize(creds)

def parse_leveldb(db_path, channels, cutoff_dt):
    db = plyvel.DB(db_path, create_if_missing=False)
    out = []
    for key, raw in db:
        try:
            text = raw.decode("utf-8", errors="ignore")
        except:
            continue
        if '"channel_id"' not in text:
            continue
        try:
            obj = json.loads(text)
        except:
            continue
        ch = obj.get("channel_id")
        ts = obj.get("timestamp")
        if ch in channels and ts:
            dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
            if dt >= cutoff_dt:
                out.append({
                    "channel_id": ch,
                    "message_id": obj.get("id"),
                    "author":       obj.get("author",{}).get("username",""),
                    "timestamp":   dt.isoformat(),
                    "content":     obj.get("content","")
                })
    db.close()
    return out

def main():
    cutoff = datetime.utcnow() - timedelta(days=WEEK_DAYS)
    print(f"[INFO] Ищем сообщения с {cutoff.isoformat()}…")

    msgs = parse_leveldb(DB_PATH, CHANNEL_IDS, cutoff)
    print(f"[INFO] Найдено {len(msgs)} сообщений.")

    sheet = get_sheets_client().open_by_key(SHEET_ID)
    try:
        ws = sheet.worksheet("archive")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="archive", rows="2000", cols="5")

    ws.append_row(["channel_id","message_id","author","timestamp","content"])
    for m in msgs:
        ws.append_row([m["channel_id"],m["message_id"],m["author"],m["timestamp"],m["content"]])

    print("[INFO] Данные записаны в лист «archive».")
    
if __name__=="__main__":
    main()
