#!/usr/bin/env python3
import os
import json
import re
from collections import defaultdict
from datetime import datetime
import openai
import gspread

# --- Constants ---
DISCORD_EPOCH = 1420070400000  # milliseconds for Discord snowflake parsing

# --- Environment & Authentication ---
creds_json = os.environ.get('GOOGLE_CREDS_JSON')
if not creds_json:
    raise RuntimeError('GOOGLE_CREDS_JSON environment variable is missing')
creds_dict = json.loads(creds_json)
gc = gspread.service_account_from_dict(creds_dict)

openai.api_key = os.environ.get('OPENAI_API_KEY')
src_key = os.environ.get('SRC_SHEET_ID')
dst_key = os.environ.get('DST_SHEET_ID')
if not src_key or not dst_key:
    raise RuntimeError('SRC_SHEET_ID and DST_SHEET_ID are required')

# --- Date parsing ---
def parse_date(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime('%d.%m.%Y')
    except:
        try:
            return datetime.strptime(ts, '%d.%m.%Y').strftime('%d.%m.%Y')
        except:
            if ts.isdigit():
                ms = (int(ts) >> 22) + DISCORD_EPOCH
                return datetime.fromtimestamp(ms / 1000.0).strftime('%d.%m.%Y')
    return datetime.now().strftime('%d.%m.%Y')

# --- OpenAI logic ---
def analyze_with_openai(messages: list[str]) -> str:
    system_prompt = (
        "Ты классифицируешь список сообщений. Верни строго JSON-объект с ключами "
        "'problems', 'updates', 'plans'. Тексты внутри массивов должны быть на русском языке, "
        "короткими фразами. Никаких ```json или markdown — только JSON."
    )
    user_prompt = "\n".join(messages)
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )
    raw = response.choices[0].message.content.strip()

    # --- clean up JSON block ---
    if raw.lower().startswith("json"):
        raw = raw[raw.find("{"):]
    if raw.startswith("```") and raw.endswith("```"):
        raw = raw.strip("`")

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.replace("\n", " ")[:500]

    # --- format result ---
    result = []
    result.append("🛑 " + "; ".join(data.get("problems", [])) if data.get("problems") else "🛑 —")
    result.append("🔄 " + "; ".join(data.get("updates", [])) if data.get("updates") else "🔄 —")
    result.append("🚀 " + "; ".join(data.get("plans", [])) if data.get("plans") else "🚀 —")
    return "   ".join(result)

# --- Main ---
def main():
    sh_src = gc.open_by_key(src_key)
    sheet_src = sh_src.worksheet('archive')
    rows = sheet_src.get_all_values()
    header = rows[0]

    try:
        ts_idx = header.index('timestamp')
        id_idx = header.index('subnet_number')
        msg_idx = header.index('content')
    except ValueError as e:
        raise RuntimeError(f"Column missing: {e}")

    today_str = datetime.now().strftime('%d.%m.%Y')
    print(f"DEBUG: Filtering for {today_str}")

    groups = defaultdict(list)
    for row in rows[1:]:
        date = parse_date(row[ts_idx])
        if date == today_str:
            subnet = str(row[id_idx])
            msg = row[msg_idx]
            groups[subnet].append(msg)

    print(f"DEBUG: Subnets with messages: {list(groups.keys())}")

    summaries = {}
    for subnet, msgs in groups.items():
        print(f"DEBUG: Analyzing subnet {subnet}")
        summaries[subnet] = analyze_with_openai(msgs)

    # Write back
    sh_dst = gc.open_by_key(dst_key)
    sheet_dst = sh_dst.worksheet('Dis и выводы')
    header_dst = sheet_dst.row_values(1)
    if today_str not in header_dst:
        raise RuntimeError(f"Date {today_str} not found in header row")
    col_idx = header_dst.index(today_str) + 1

    netids = sheet_dst.col_values(1)[1:]
    for subnet, result in summaries.items():
        if subnet in netids:
            row = netids.index(subnet) + 2
            sheet_dst.update_cell(row, col_idx, result)
            print(f"✅ {subnet} → row {row}, col {col_idx}")
        else:
            print(f"⚠️ Subnet {subnet} not found in NetUID")

if __name__ == '__main__':
    main()
