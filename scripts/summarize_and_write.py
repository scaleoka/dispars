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
GOOGLE_SHEET_ID = os.environ['GOOGLE_SHEET_ID']       # id источника
GOOGLE_SHEET2_ID = os.environ['GOOGLE_SHEET2_ID']     # id приёмника
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
sh_src = gc.open_by_key(GOOGLE_SHEET_ID)
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
    block = f"Subnet {subnet}:\n" + "\n".join(str(m) for m in messages)
    prompt_blocks.append(block)

full_prompt = "\n\n".join(prompt_blocks)
total_tokens = estimate_tokens(full_prompt)
print(f"📊 GPT-ввод: ~{total_tokens} токенов")

# --- Промпт ---
system_prompt = (
    "Ты аналитик. Тебе поступает список сообщений на английском языке, сгруппированных по подсетям. "
    "Для каждой подсети составь как можно более детальный и полный отчёт. "
    "Не пропускай даже незначительные детали: любые ссылки, технические уточнения, мнения участников, реакции и т.п. "
    "Если что-то упоминается — это должно быть отражено. "
    "Всегда пиши на русском языке.\n\n"
    "Структурируй информацию по следующим категориям:\n"
    "🛑 Проблемы — описания жалоб, неполадок, путаницы, негатива\n"
    "🔄 Обновления — любые пояснения, ответы, уточнения, действия команды\n"
    "🚀 Релизы / Планы — всё, что связано с будущими действиями, обещаниями, задачами, ссылками на релизы и т.п.\n\n"
    "Если по какой-то категории нет информации — поставь прочерк.\n\n"
    "Формат ответа строго такой:\n\n"
    "Subnet 70\n"
    "🛑 ...\n"
    "🔄 ...\n"
    "🚀 ...\n\n"
    "Subnet 88\n"
    "🛑 ...\n"
    "🔄 ...\n"
    "🚀 ..."
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
sh_dst = gc.open_by_key(GOOGLE_SHEET2_ID)
sheet = sh_dst.worksheet("Dis и выводы")
header = sheet.row_values(1)
yesterday_str = yesterday.strftime('%d.%m.%Y')

# Если нет колонки с нужной датой — добавить в конец!
if not any(h.strip() == yesterday_str for h in header):
    sheet.update_cell(1, len(header) + 1, yesterday_str)
    print(f"➕ Добавлена новая колонка для даты: {yesterday_str}")
    header.append(yesterday_str)  # чтобы col вычислился верно

col = next(i for i, h in enumerate(header) if h.strip() == yesterday_str) + 1

# --- Разбор ответа ---
print("✍️ Запись результатов...")
netids = [str(int(i)) for i in sheet.col_values(1)[1:] if i.strip()]
current_subnet = None
buffer = []
updates = {}

for line in result.splitlines():
    if re.match(r'^Subnet\s+\d+[.:]?', line.strip()):
        if current_subnet and buffer:
            updates[current_subnet] = "\n".join(buffer).strip()
        match = re.search(r'Subnet\s+(\d+(?:\.\d+)?)', line.strip())
        current_subnet = match.group(1) if match else None
        buffer = []
    elif current_subnet:
        buffer.append(line)

if current_subnet and buffer:
    try:
        normalized_subnet = str(int(float(current_subnet)))
    except:
        normalized_subnet = current_subnet.strip()
    updates[normalized_subnet] = "\n".join(buffer).strip()

print(f"📦 Ключи подсетей для записи: {list(updates.keys())}")
print(f"📦 NetID в таблице: {netids}")

# --- Пишем в ячейки ---
for subnet, summary in updates.items():
    if subnet in netids:
        row = netids.index(subnet) + 2
        sheet.update_cell(row, col, summary)
        print(f"✅ {subnet} → row {row}, col {col}")
    else:
        print(f"⚠️ Subnet {subnet} не найдена в таблице")

print("🎉 Готово. Примерная стоимость: ${:.4f}".format(0.0005 * total_tokens / 1000 + 0.0015 * 2000 / 1000))
