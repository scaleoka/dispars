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
    
actual_subnets = set(messages_by_subnet.keys())   

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
    "Анализируй и составляй отчёт только для тех подсетей, для которых приведены сообщения ниже. "
    "Не нужно придумывать отчёты для других подсетей. "
    "Для каждой подсети составь максимально полный и детальный отчёт. "
    "Не пропускай даже незначительные детали: любые ссылки, технические уточнения, мнения участников, реакции и т.п. "
    "Если что-то упоминается — это должно быть отражено. "
    "Всегда пиши на русском языке.\n\n"
    "Структурируй информацию по следующим категориям:\n"
    "🛑 Проблемы — жалобы, неполадки, путаница, негатив\n"
    "🔄 Обновления — пояснения, ответы, уточнения, действия команды\n"
    "🚀 Релизы / Планы — будущие действия, обещания, задачи, ссылки на релизы\n\n"
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
print("📤 Ответ GPT (первые 1000 символов):")
print(result[:1000])
        
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
    if re.match(r'^[\*\s]*Subnet\s+\d+[.:]?[\*\s]*', line.strip()):
        if current_subnet and buffer:
            try:
                normalized_subnet = str(int(float(current_subnet)))
            except:
                normalized_subnet = current_subnet.strip()
            updates[normalized_subnet] = "\n".join(buffer).strip()
        match = re.search(r'Subnet\s+(\d+(?:\.\d+)?)', line)
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
print(f"🔍 Сообщения найдены для {len(actual_subnets)} подсетей: {sorted(actual_subnets)}")
if set(updates.keys()) - actual_subnets:
    print(f"⚠️ GPT попытался добавить несуществующие сабнеты: {set(updates.keys()) - actual_subnets}")


# --- ВОТ ТУТ! Фильтруем только те подсети, что реально были в actual_subnets ---
filtered_updates = {k: v for k, v in updates.items() if k in actual_subnets}

# --- Группируем записи для батча ---
cell_list = []
for subnet, summary in filtered_updates.items():    # <--- ТОЛЬКО filtered_updates!
    if subnet in netids:
        row = netids.index(subnet) + 2
        cell = gspread.cell.Cell(row=row, col=col, value=summary)
        cell_list.append(cell)
        print(f"📝 Подготовлено: {subnet} → row {row}, col {col}")
    else:
        print(f"⚠️ Subnet {subnet} не найдена в таблице")

# --- Массовое обновление (batch update) ---
if cell_list:
    sheet.update_cells(cell_list)
    print(f"✅ Обновлено {len(cell_list)} ячеек одним запросом")
else:
    print("⚠️ Нет данных для записи!")

print("🎉 Готово. Примерная стоимость: ${:.4f}".format(0.0005 * total_tokens / 1000 + 0.0015 * 2000 / 1000))
