import os
import json
from collections import defaultdict
from datetime import datetime
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Google Sheets authorization ---
creds_json = os.environ['GOOGLE_CREDS_JSON']
creds_dict = json.loads(creds_json)
# Use from_json_keyfile_dict to load directly from dict
gc = gspread.service_account_from_dict(creds_dict)

# --- OpenAI API key ---
openai.api_key = os.environ['OPENAI_API_KEY']

# --- Parameters from environment ---
src_key = os.environ['SRC_SHEET_ID']
dst_key = os.environ['DST_SHEET_ID']

# --- Helper: analyze group of messages ---
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
        # Если не JSON, просто возвращаем весь блок как one-string
        return text
    # Format into markdown
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

# --- Read today's rows and group by subnet ---
sh_src = gc.open_by_key(src_key)
sheet = sh_src.worksheet('archive')
rows = sheet.get_all_values()

# Assume header: ["timestamp", "subnet_id", "message"]
# Adjust indices if needed
header = rows[0]
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
    try:
        date_part = datetime.fromisoformat(ts).strftime('%d.%m.%Y')
    except ValueError:
        date_part = datetime.strptime(ts, '%d.%m.%Y').strftime('%d.%m.%Y')
    if date_part == today_str:
        subnet = str(row[id_idx])
        msg = row[msg_idx]
        groups[subnet].append(msg)

# Analyze each group
by_subnet = {}
for subnet, msgs in groups.items():
    if msgs:
        by_subnet[subnet] = analyze_with_openai(msgs)
    else:
        by_subnet[subnet] = '—'

# --- Write results into destination sheet ---
sh_dst = gc.open_by_key(dst_key)
sheet_dst = sh_dst.worksheet('DIs и выводы')

# Find or create today's column
header_dst = sheet_dst.row_values(1)
if today_str in header_dst:
    col_idx = header_dst.index(today_str) + 1
else:
    sheet_dst.add_cols(1)
    col_idx = len(header_dst) + 1
    sheet_dst.update_cell(1, col_idx, today_str)

# Map NetID rows
netids = sheet_dst.col_values(1)[1:]
for subnet, summary in by_subnet.items():
    if subnet in netids:
        row_idx = netids.index(subnet) + 2
        sheet_dst.update_cell(row_idx, col_idx, summary)
