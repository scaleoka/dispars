#!/usr/bin/env python3
import os
import json
from collections import defaultdict
from datetime import datetime
import openai
import gspread

# --- Constants ---
DISCORD_EPOCH = 1420070400000  # milliseconds for Discord snowflake parsing

# --- Environment & Authentication ---
# Google Sheets service account credentials
creds_json = os.environ.get('GOOGLE_CREDS_JSON')
if not creds_json:
    raise RuntimeError('GOOGLE_CREDS_JSON environment variable is missing')
creds_dict = json.loads(creds_json)
# Authenticate gspread client
gc = gspread.service_account_from_dict(creds_dict)

# OpenAI API key
openai_key = os.environ.get('OPENAI_API_KEY')
if not openai_key:
    raise RuntimeError('OPENAI_API_KEY environment variable is missing')
openai.api_key = openai_key

# Sheet IDs
src_key = os.environ.get('SRC_SHEET_ID')
dst_key = os.environ.get('DST_SHEET_ID')
if not src_key or not dst_key:
    raise RuntimeError('SRC_SHEET_ID and DST_SHEET_ID environment variables are required')

# --- Helper Functions ---
def parse_date(ts: str) -> str:
    """
    Parse timestamp string which may be ISO format, 'dd.MM.YYYY', or Discord snowflake ID.
    Returns date formatted as 'dd.MM.YYYY'.
    """
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        try:
            dt = datetime.strptime(ts, '%d.%m.%Y')
        except ValueError:
            if ts.isdigit():
                snowflake = int(ts)
                ms = (snowflake >> 22) + DISCORD_EPOCH
                dt = datetime.fromtimestamp(ms / 1000.0)
            else:
                dt = datetime.now()
    return dt.strftime('%d.%m.%Y')


def analyze_with_openai(messages: list[str]) -> str:
    """
    Send messages list to OpenAI Chat API to classify into three categories.
    Returns a concise summary string with emojis.
    """
    system_prompt = (
        "Верни строго JSON-объект с ключами 'problems', 'updates', 'plans'. "
        "Каждое значение — массив коротких строк."
    )
    user_prompt = "
".join(messages)
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_prompt}
        ],
        temperature=0
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content.strip("`
json")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        text = content.replace('
', ' ')
        return text[:500]
    parts = []
    if data.get('problems'):
        parts.append("🛑 " + "; ".join(data['problems']))
    else:
        parts.append("🛑 —")
    if data.get('updates'):
        parts.append("🔄 " + "; ".join(data['updates']))
    else:
        parts.append("🔄 —")
    if data.get('plans'):
        parts.append("🚀 " + "; ".join(data['plans']))
    else:
        parts.append("🚀 —")
    return "   ".join(parts)

def main():
    # Open source sheet and read all data
    sh_src = gc.open_by_key(src_key)
    sheet_src = sh_src.worksheet('archive')
    rows = sheet_src.get_all_values()
    header = rows[0]
    print(f"DEBUG: Source header: {header}")

    # Detect column indices
    try:
        ts_idx = header.index('timestamp')
        id_idx = header.index('subnet_number')
        msg_idx = header.index('content')
    except ValueError as e:
        raise RuntimeError(f"Required column not found: {e}")

    today_str = datetime.now().strftime('%d.%m.%Y')
    print(f"DEBUG: Filtering messages for date {today_str}")

    # Group messages by subnet
    groups: dict[str, list[str]] = defaultdict(list)
    for row in rows[1:]:
        date_part = parse_date(row[ts_idx])
        if date_part == today_str:
            subnet = str(row[id_idx])
            groups[subnet].append(row[msg_idx])
    print(f"DEBUG: Found messages for subnets: {list(groups.keys())}")

    # Analyze each subnet
    summaries: dict[str, str] = {}
    for subnet, msgs in groups.items():
        print(f"DEBUG: Analyzing subnet {subnet} ({len(msgs)} messages)")
        summaries[subnet] = analyze_with_openai(msgs)

    # Open destination sheet
    sh_dst = gc.open_by_key(dst_key)
    sheet_dst = sh_dst.worksheet('Dis и выводы')

    # Find today's column
    header_dst = sheet_dst.row_values(1)
    if today_str not in header_dst:
        raise RuntimeError(f"Date {today_str} not found in destination header")
    col_idx = header_dst.index(today_str) + 1
    print(f"DEBUG: Writing to column {col_idx} heading '{today_str}'")

    # Write summaries to sheet
    netids = sheet_dst.col_values(1)[1:]
    for subnet, summary in summaries.items():
        if subnet in netids:
            row_idx = netids.index(subnet) + 2
            sheet_dst.update_cell(row_idx, col_idx, summary)
            print(f"DEBUG: Wrote summary for subnet {subnet} at row {row_idx}")
        else:
            print(f"DEBUG: Subnet {subnet} not found; skipped")

if __name__ == '__main__':
    main()
