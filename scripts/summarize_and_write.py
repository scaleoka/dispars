#!/usr/bin/env python3
import os
import json
from collections import defaultdict
from datetime import datetime, timedelta
import openai
import gspread

# --- Constants ---
DISCORD_EPOCH = 1420070400000  # for Discord snowflake parsing

# --- Auth ---
creds_json = os.environ.get('GOOGLE_CREDS_JSON')
if not creds_json:
    raise RuntimeError('GOOGLE_CREDS_JSON is missing')
creds_dict = json.loads(creds_json)
gc = gspread.service_account_from_dict(creds_dict)

openai_key = os.environ.get('OPENAI_API_KEY')
if not openai_key:
    raise RuntimeError('OPENAI_API_KEY is missing')
openai.api_key = openai_key

src_key = os.environ.get('SRC_SHEET_ID')
dst_key = os.environ.get('DST_SHEET_ID')
if not src_key or not dst_key:
    raise RuntimeError('SRC_SHEET_ID and DST_SHEET_ID are required')

# --- Timestamp parsing ---
def parse_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        try:
            dt = datetime.strptime(ts, '%d.%m.%Y')
        except ValueError:
            if ts.isdigit():
                ms = (int(ts) >> 22) + DISCORD_EPOCH
                dt = datetime.fromtimestamp(ms / 1000.0)
            else:
                dt = datetime.now()
    return dt.strftime('%d.%m.%Y')

# --- GPT анализ ---
def analyze_with_openai(messages: list[str]) -> str:
    system_prompt = (
        "Ты аналитик. Тебе поступает список сообщений на английском языке. "
        "Проанализируй их и составь краткий структурированный отчёт по трём категориям:\n"
        "🛑 Проблемы\n🔄 Обновления\n🚀 Релизы / Планы\n\n"
        "Для каждой категории выдели тезисные пункты (в виде списка), сохраняя детали и контекст. "
        "Пиши на русском языке. Не упрощай и не сокращай важные формулировки. "
        "Не пересказывай — выжимай суть. Каждое сообщение — как блок фактов.\n\n"
        "Формат ответа строго следующий:\n\n"
        "🛑 Проблемы\n• …\n• …\n\n"
        "🔄 Обновления\n• …\n• …\n\n"
        "🚀 Релизы / Планы\n• …\n• …"
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
    return response.choices[0].message.content.strip()

# --- Main logic ---
def main():
    # Дата вчерашнего дня
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    target_date = yesterday.strftime('%d.%m.%Y')
    print(f"DEBUG: Filtering messages for date {target_date}")

    # Чтение исходных данных
    sh_src = gc.open_by_key(src_key)
    sheet_src = sh_src.worksheet('archive')
    rows = sheet_src.get_all_values()
    header = rows[0]

    try:
        ts_idx = header.index('timestamp')
        id_idx = header.index('subnet_number')
        msg_idx = header.index('content')
    except ValueError as e:
        raise RuntimeError(f"Required column not found: {e}")

    groups = defaultdict(list)
    for row in rows[1:]:
        date_part = parse_date(row[ts_idx])
        if date_part == target_date:
            subnet = str(row[id_idx])
            groups[subnet].append(row[msg_idx])
    print(f"DEBUG: Found messages for subnets: {list(groups.keys())}")

    summaries = {}
    for subnet, msgs in groups.items():
        print(f"DEBUG: Analyzing subnet {subnet} ({len(msgs)} messages)")
        summaries[subnet] = analyze_with_openai(msgs)

    # Запись в целевой лист
    sh_dst = gc.open_by_key(dst_key)
    sheet_dst = sh_dst.worksheet('Dis и выводы')
    header_dst = sheet_dst.row_values(1)

    if target_date not in header_dst:
        raise RuntimeError(f"Date {target_date} not found in destination header")
    col_idx = header_dst.index(target_date) + 1
    print(f"DEBUG: Writing to column {col_idx} (header '{target_date}')")

    netids = sheet_dst.col_values(1)[1:]
    for subnet, summary in summaries.items():
        if subnet in netids:
            row_idx = netids.index(subnet) + 2
            sheet_dst.update_cell(row_idx, col_idx, summary)
            print(f"✅ Wrote summary for subnet {subnet} → row {row_idx}, col {col_idx}")
        else:
            print(f"⚠️ Subnet {subnet} not found in NetID column — skipped.")

if __name__ == '__main__':
    main()
