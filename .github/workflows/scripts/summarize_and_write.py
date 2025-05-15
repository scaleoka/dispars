import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1) Авторизация
scope = ['https://spreadsheets.google.com/feeds']
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
gc = gspread.authorize(creds)

# 2) Исходная таблица
src_key = '18deC7WjmIkqZfg0RDtF_XoEM-TVnHdgUurazyAhl24Q'
sh_src = gc.open_by_key(src_key)
sheet_src = sh_src.worksheet('archive')
rows = sheet_src.get_all_values()

# 3) Группируем и анализируем через OpenAI
by_subnet = analyze_with_openai(rows)  # ваша реализация

# 4) Таблица-назначение + лист
dst_key = '1vR3npH1Kgqu0IyXZnfx9vYauLPNl8kGjrkdCkA2R71o'
sh_dst = gc.open_by_key(dst_key)
sheet_dst = sh_dst.worksheet('DIs и выводы')

# 5) Заголовок и колонка для сегодняшней даты
header = sheet_dst.row_values(1)
today = datetime.now().strftime('%d.%m.%Y')
if today in header:
    col_idx = header.index(today) + 1
else:
    sheet_dst.add_cols(1)
    col_idx = len(header) + 1
    sheet_dst.update_cell(1, col_idx, today)

# 6) Пишем в строки по NetID
netids = sheet_dst.col_values(1)[1:]  # строки 2…N
for subnet, text in by_subnet.items():
    if subnet in netids:
        row = netids.index(subnet) + 2
        sheet_dst.update_cell(row, col_idx, text or '—')
