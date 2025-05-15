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
creds_json = os.environ.get('GOOGLE_CREDS_JSON')
creds_dict = json.loads(creds_json)
# Load service account from dict
gc = gspread.service_account_from_dict(creds_dict)

# --- OpenAI API key ---
openai.api_key = os.environ.get('OPENAI_API_KEY')

# --- Parameters ---
src_key = os.environ.get('SRC_SHEET_ID')
dst_key = os.environ.get('DST_SHEET_ID')

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

# --- Read and group messages by subnet for today ---
sh_src = gc.open_by_key(src_key)
sheet = sh_src.worksheet('archive')
rows = sheet.get_all_values()
header = rows[0]
print(f"DEBUG: Header columns: {header}")

today_str = datetime.now().strftime('%d.%m.%Y')
print(f"DEBUG: Today's date: {today_str}")

# Detect columns
try:
    ts_idx = header.index('timestamp')
    id_idx = header.index('subnet_id')
    msg_idx = header.index('message')
except ValueError:
    ts_idx, id_idx, msg_idx = 0, 1, 2
    print(f"DEBUG: Using default column indices ts={ts_idx}, id={id_idx}, msg={msg_idx}")

groups = defaultdict(list)
for row in rows[1:]:
    ts = row[ts_idx]
    date_part = parse_date(ts)
    if date_part == today_str:
        subnet = str(row[id_idx])
        msg = row[msg_idx]
        groups[subnet].append(msg)

print(f"DEBUG: Found {len(groups)} subnets with messages: {list(groups.keys())}")

# Analyze each subnet
by_subnet = {}
for subnet, msgs in groups.items():
    if msgs:
        print(f"DEBUG: Analyzing subnet {subnet} with {len(msgs)} messages")
        by_subnet[subnet] = analyze_with_openai(msgs)
    else:
        by_subnet[subnet] = '—'

print(f"DEBUG: Analysis results prepared for {len(by_subnet)} subnets")

# --- Write results into destination sheet ---
sh_dst = gc.open_by_key(dst_key)
sheet_dst = sh_dst.worksheet('Dis и выводы')

# Find today's column in header row (e.g., AX for today)
today_str = datetime.now().strftime('%d.%m.%Y')
header_dst = sheet_dst.row_values(1)
if today_str not in header_dst:
    print(f"ERROR: Today's date {today_str} not found in header row.")
    exit(1)
col_idx = header_dst.index(today_str) + 1
print(f"DEBUG: Writing results to column {col_idx} matching header {today_str}")

# Map NetID rows and write summaries
netids = sheet_dst.col_values(1)[1:]
for subnet, summary in by_subnet.items():
    if subnet in netids:
        row_idx = netids.index(subnet) + 2
        sheet_dst.update_cell(row_idx, col_idx, summary)
        print(f"DEBUG: Wrote summary for subnet {subnet} at row {row_idx}, col {col_idx}")
    else:
        print(f"DEBUG: Subnet {subnet} not found in Dis и выводы sheet; skipping")
netids = sheet_dst.col_values(1)[1:]
for subnet, summary in by_subnet.items():
    if subnet in netids:
        row_idx = netids.index(subnet) + 2
        sheet_dst.update_cell(row_idx, col_idx, summary)
        print(f"DEBUG: Wrote summary for subnet {subnet} at row {row_idx}, col {col_idx}")
    else:
        print(f"DEBUG: Subnet {subnet} not found in Dis и выводы sheet; skipping")
netids = sheet_dst.col_values(1)[1:]
for subnet, summary in by_subnet.items():
    if subnet in netids:
        row_idx = netids.index(subnet) + 2
        sheet_dst.update_cell(row_idx, col_idx, summary)
        print(f"DEBUG: Wrote summary for subnet {subnet} at row {row_idx}, col {col_idx}")
    else:
        print(f"DEBUG: Subnet {subnet} not found in Dis и выводы sheet; skipping")
