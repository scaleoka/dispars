#!/usr/bin/env python3
import os, json
from datetime import datetime, timedelta

import plyvel
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Настройки ===
DB_PATH     = os.path.join(os.getcwd(), "leveldb")
SHEET_ID    = os.getenv("GOOGLE_SHEET_ID")
CHANNEL_IDS = {
    "1349119225868058644","1349121405903573114","1349122541754515538",
    "1264939518641963070","1353733356470276096","1342559689690583202",
    "1347299108238397572","1358854051634221328","1361438967198908577",
    "1361761424153645217","1364253568961609859","1364655778149171250",
    "1366426072765431808","1366426973781364816","1366845111945658409",
    "1366897804068393000"
}
WEEK_DAYS   = 7
# ==================

def get_sheets_client():
    raw = os.getenv("GOOGLE_CREDS_JSON")
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON не задан")
    creds_info = json.loads(raw)
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def open_leveldb(path):
    """
    Пытаемся открыть LevelDB; при ошибке — ремонтируем и открываем снова.
    """
    try:
        return plyvel.DB(path, create_if_missing=False)
    except (plyvel.CorruptionError, plyvel.IOError) as e:
        print(f"[WARN] LevelDB error: {e!r}")
        print("[WARN] Attempting repair...")
        plyvel.repair_db(path)
        return plyvel.DB(path, create_if_missing=False)

def parse_leveldb(db_path, channels, cutoff_dt):
    db = open_leveldb(db_path)
    out = []
    for _, raw in db:
        try:
            js = raw.decode("utf-8", errors="ignore")
            if '"channel_id"' not in js:
                continue
            obj = json.loads(js)
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
                    "author":      obj.get("author",{}).get("username",""),
                    "timestamp":   dt.isoformat(),
                    "content":     obj.get("content","")
                })
    db.close()
    return out

def main():
    cutoff = datetime.utcnow() - timedelta(days=WEEK_DAYS)
    print(f"[INFO] Parsing since {cutoff.isoformat()}…")

    msgs = parse_leveldb(DB_PATH, CHANNEL_IDS, cutoff)
    print(f"[INFO] Found {len(msgs)} messages.")

    sheet = get_sheets_client().open_by_key(SHEET_ID)
    try:
        ws = sheet.worksheet("archive")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="archive", rows="2000", cols="5")

    ws.append_row(["channel_id","message_id","author","timestamp","content"])
    for m in msgs:
        ws.append_row([
            m["channel_id"], m["message_id"],
            m["author"],   m["timestamp"],
            m["content"]
        ])

    print("[INFO] Done.")

if __name__=="__main__":
    main()
