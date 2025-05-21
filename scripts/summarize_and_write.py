#!/usr/bin/env python3
import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
import openai
import gspread

# --- Настройки API ---
openai.api_key = os.environ['OPENAI_API_KEY']
SRC_SHEET_ID = os.environ['SRC_SHEET_ID']
DST_SHEET_ID = os.environ['DST_SHEET_ID']
creds = json.loads(os.environ['GOOGLE_CREDS_JSON'])
gc = gspread.service_account_from_dict(creds)

# --- Вспомогательные функции ---
DISCORD_EPOCH = 1420070400000

def parse_date(ts):
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

def estimate_tokens(text):
    return int(len(text) / 4)  # грубая оценка

# --- Подготовка ---
print("🔄 Загрузка данных из таблицы...")
yesterday = datetime.utcnow().date() - timedelta(days=1)
sh_src = gc.open_by_key(SRC_SHEET_ID)
df = sh_src.worksheet("archive").get_all_records()

messages_by_subnet = defaultdict(list)

for row in df:
    if parse_date(row['timestamp']) == yesterday.strftime('%d.%m.%Y'):
        subnet = str(row['subnet_number'])
        messages_by_subnet[subnet].append(row['content'])

if not messages_by_subnet:
    print("⚠️ Нет сообщений за вчера.")
    exit()

# --- Формируем единый запрос ---
prompt_blocks = []
for subnet, messages in messages_by_subnet.items():
    block = f"Subnet {subnet}:\n" + "\n".join(messages)
    prompt_blocks.append(block)

full_prompt = "\n\n".join(prompt_blocks)
total_tokens = estimate_tokens(full_prompt)
print(f"📊 GPT-ввод: ~{total_tokens} токенов")

# --- Промпт ---
system_prompt = (
    "Ты аналитик. Тебе поступает список сообщений на английском языке, сгруппированных по подсетям.\n"
    "Для каждой подсети составь краткий отчёт по трём категориям:\n"
    "🛑 Проблемы\n🔄 Обновления\n🚀 Релизы / Планы\n\n"
    "Если по категории нет информации — поставь прочерк. Ответ строго в следующем формате:\n\n"
    "Subnet 70\n🛑 ...\n🔄 ...\n🚀 ...\n\nSubnet 88\n🛑 ...\n🔄 ...\n🚀 ..."
)

# --- GPT-запрос ---
print("🧠 Отправка в GPT...")
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": full_prompt}
    ],
    temperature=0
)
result = response.choices[0].message.content.strip()
print("✅ Ответ получен")

# --- Запись в таблицу ---
sh_dst = gc.open_by_key(DST_SHEET_ID)
sheet = sh_dst.worksheet("Dis и выводы")
header = sheet.row_values(1)
yesterday_str = yesterday.strftime('%d.%m.%Y')
if yesterday_str not in header:
    raise Exception("❌ В таблице нет колонки с датой " + yesterday_str)
col = header.index(yesterday_str) + 1

# --- Разбор ответа ---
print("✍️ Запись результатов...")
netids = sheet.col_values(1)[1:]  # без заголовка
current_subnet = None
buffer = []
updates = {}
for line in result.splitlines():
    if line.strip().startswith("Subnet"):
        if current_subnet and buffer:
            updates[current_subnet] = "\n".join(buffer).strip()
        current_subnet = line.strip().split()[1]
        buffer = []
    elif current_subnet:
        buffer.append(line)
if current_subnet and buffer:
    updates[current_subnet] = "\n".join(buffer).strip()

# --- Пишем в ячейки ---
for subnet, summary in updates.items():
    if subnet in netids:
        row = netids.index(subnet) + 2
        sheet.update_cell(row, col, summary)
        print(f"✅ {subnet} → row {row}, col {col}")
    else:
        print(f"⚠️ Subnet {subnet} не найдена в таблице")

print("🎉 Готово. Примерная стоимость: ${:.4f}".format(0.0005 * total_tokens / 1000 + 0.0015 * 2000 / 1000))
