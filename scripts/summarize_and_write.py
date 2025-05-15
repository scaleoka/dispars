import os
import json
from collections import defaultdict
from datetime import datetime
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Discord epoch for Snowflake parsing
DISCORD_EPOCH = 1420070400000  # milliseconds

# --- Google Sheets authorization ---
creds_json = os.environ['GOOGLE_CREDS_JSON']
creds_dict = json.loads(creds_json)
# Load service account from dict
gc = gspread.service_account_from_dict(creds_dict)

# --- OpenAI API key ---
openai.api_key = os.environ['OPENAI_API_KEY']

# --- Parameters ---
src_key = os.environ['SRC_SHEET_ID']
dst_key = os.environ['DST_SHEET_ID']

def parse_date(ts: str) -> str:
    """
    Parse timestamp string which may be ISO format, 'dd.MM.YYYY', or Discord snowflake ID.
    Returns date formatted as 'dd.MM.YYYY'.
    """
    # Try ISO format
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        # Try dd.MM.YYYY
        try:
            dt = datetime.strptime(ts, '%d.%m.%Y')
        except ValueError:
            # Try Snowflake
            if ts.isdigit():
                snowflake = int(ts)
                ms = (snowflake >> 22) + DISCORD_EPOCH
                dt = datetime.fromtimestamp(ms / 1000.0)
            else:
                # Fallback to today
                dt = datetime.now()
    return dt.strftime('%d.%m.%Y')

# --- Helper to analyze messages ---
def analyze_with_openai(messages):
    system_prompt = (
        "Ты классифицируешь список сообщений по трём категориям: "
        "🛑 Проблемы, 🔄 Обновления, 🚀 Релизы/Планы. "
        "Ответь строго JSON-объектом со свойствами 'problems', 'updates', 'plans'."
    )
    user_prompt = "\n".join(messages)
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )
    text = resp.choices[0].message.content.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    result = []
    if data.get('problems'):
        result.append('🛑 Проблемы:')
        for item in data['problems']:
            result.append(f"- {item}")
    if data.get('updates'):
        result.append('🔄 Обновления:')
        for item in data['updates']:
            result.append(f"- {item}")
    if data.get('plans'):
        result.append('🚀 Релизы/Планы:')
        for item in data['plans']:
            result.append(f"- {item}")
    return "\n".join(result)

# --- Read and group messages by subnet for today ---
sh_src = gc.open_by_key(src_key)
sheet = sh_src.worksheet('archive')
rows = sheet.get_all_values()
header = rows[0]
# Detect columns
try:
    ts_idx = header.index('timestamp')
    id_idx = header.index('subnet_id')
    msg_idx = header.index('message')
except ValueError:
    ts_idx, id_idx, msg_idx = 0, 1, 2

groups = defaultdict(list)
today_str = datetime.now().strftime('%d.%m.%Y')
for row in rows[1:]:
    ts = row[ts_idx]
    date_part = parse_date(ts)
    if date_part == today_str:
        subnet = str(row[id_idx])
        msg = row[msg_idx]
        groups[subnet].append(msg)

# Analyze each subnet
by_subnet = {}
for subnet, msgs in groups.items():
    by_subnet[subnet] = analyze_with_openai(msgs) if msgs else '—'

# --- Write results into destination sheet ---
sh_dst = gc.open_by_key(dst_key)
sheet_dst = sh_dst.worksheet('DIs и выводы')

# Find or add today's column
header_dst = sheet_dst.row_values(1)
if today_str in header_dst:
    col_idx = header_dst.index(today_str) + 1
else:
    sheet_dst.add_cols(1)
    col_idx = len(header_dst) + 1
    sheet_dst.update_cell(1, col_idx, today_str)

# Map NetID rows and write summaries
netids = sheet_dst.col_values(1)[1:]
for subnet, summary in by_subnet.items():
    if subnet in netids:
        row_idx = netids.index(subnet) + 2
        sheet_dst.update_cell(row_idx, col_idx, summary)
