#!/usr/bin/env python3
import os
import json
import re
import time
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
filtered_actual_subnets = [s for s in actual_subnets if str(s).strip().isdigit()]
actual_list_str = ', '.join(sorted(filtered_actual_subnets, key=int))

# --- Формируем единый запрос ---
prompt_blocks = []
for subnet, messages in messages_by_subnet.items():
    block = f"Subnet {subnet}:\n" + "\n".join(str(m) for m in messages)
    prompt_blocks.append(block)

full_prompt = "\n\n".join(prompt_blocks)
user_prompt = (
    f"В предоставленных сообщениях встречаются только подсети: {actual_list_str}.\n\n"
    f"{full_prompt}"
)
total_tokens = estimate_tokens(full_prompt)
print(f"📊 GPT-ввод: ~{total_tokens} токенов")

# --- Промпт ---
system_prompt = (
    "Ты профессиональный аналитик. Тебе поступает список сообщений на английском языке, сгруппированных по подсетям. "
    "Твоя задача — для КАЖДОЙ подсети, приведённой в сообщениях ниже, написать максимально подробный и насыщенный отчёт. "
    "Не пропускай даже мельчайшие детали: упоминай всё — ссылки, технические детали, инсайды, настроения, вопросы, догадки, обещания, реакции, даже если они кажутся несущественными. "
    "Не сокращай, не обобщай — если кто-то что-то уточнил, спросил, выразил мнение или эмоцию — включай это в текст. "
    "Не интерпретируй сообщения слишком поверхностно, лучше приведи факты или цитаты, чтобы показать суть обсуждения. "
    "Работай ТОЛЬКО с теми подсетями, для которых есть сообщения ниже — никаких других анализов не делай и не придумывай! "
    "Не пропускай ни одну подсеть из списка. Даже если сообщений мало — всё равно напиши шаблонный отчёт и поставь прочерки по категориям, если нечего добавить.\n\n"
    "Структурируй информацию строго по категориям:\n"
    "🛑 Проблемы — любые жалобы, ошибки, затруднения, негатив, неясности, спорные моменты, просьбы о помощи, даже если их немного;\n"
    "🔄 Обновления — любые ответы, предложения, дополнительные сведения, обсуждения технических деталей, исправления, рекомендации, промежуточные итоги, даже мелкие;\n"
    "🚀 Релизы / Планы — все планы, анонсы, обсуждения будущих шагов, ожидания, обещания, упоминания релизов, задачи, даже если неофициальные или от участников;\n\n"
    "Если по какой-то категории нет информации — ставь прочерк.\n"
    "Формат ответа СТРОГО такой (не добавляй лишних подсетей и не меняй структуру):\n\n"
    "Subnet <номер>\n"
    "🛑 ...\n"
    "🔄 ...\n"
    "🚀 ...\n\n"
    "Пример:\n"
    "Subnet 70\n"
    "🛑 Жалоба на низкие выплаты за прошлый месяц и вопрос, почему снизились баллы;\n"
    "🔄 Команда пояснила, что система скоринга изменилась, и предложила почитать FAQ. Один из участников поделился своим опытом, что выплаты у него тоже упали, но постепенно восстановились;\n"
    "🚀 Ожидается обновление системы скоринга, команда обещала анонсировать релиз в канале новостей.\n\n"
    "Не упускай ни одной детали! Анализируй только те подсети, сообщения по которым есть ниже."
)

# --- БАТЧЕВАЯ GPT-ОБРАБОТКА ---
BATCH_SIZE = 10   # <= для снижения нагрузки

subnet_items = list(messages_by_subnet.items())
all_updates = {}

for batch_start in range(0, len(subnet_items), BATCH_SIZE):
    batch = subnet_items[batch_start:batch_start+BATCH_SIZE]
    batch_subnets = [subnet for subnet, _ in batch]
    batch_blocks = [
        f"Subnet {subnet}:\n" + "\n".join(str(m) for m in messages)
        for subnet, messages in batch
    ]
    batch_prompt = "\n\n".join(batch_blocks)
    batch_list_str = ', '.join(batch_subnets)
    user_prompt = (
        f"В предоставленных сообщениях встречаются только подсети: {batch_list_str}.\n\n"
        f"{batch_prompt}"
    )

    # --- ОБРАБОТКА RATE LIMIT ---
    for attempt in range(10):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0
            )
            break
        except openai.RateLimitError:
            wait_sec = 5 + attempt * 5
            print(f"💤 Rate limit exceeded, ждём {wait_sec} секунд...")
            time.sleep(wait_sec)
    else:
        raise Exception("Не удалось получить ответ от OpenAI: Rate limit не исчез после повторных попыток")

    result = response.choices[0].message.content.strip()
    print(f"📤 Ответ GPT для батча {batch_start // BATCH_SIZE + 1} (первые 500 символов):")
    print(result[:500])
    
    # --- Разбор результата батча ---
    current_subnet = None
    buffer = []
    batch_updates = {}
    for line in result.splitlines():
        if re.match(r'^[\*\s]*Subnet\s+\d+[.:]?[\*\s]*', line.strip()):
            if current_subnet and buffer:
                try:
                    normalized_subnet = str(int(float(current_subnet)))
                except:
                    normalized_subnet = current_subnet.strip()
                batch_updates[normalized_subnet] = "\n".join(buffer).strip()
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
        batch_updates[normalized_subnet] = "\n".join(buffer).strip()
    
    # --- Добавляем в общий результат ---
    all_updates.update(batch_updates)

print(f"📦 Собрано итоговых отчётов: {len(all_updates)} подсетей")
print(f"🔍 Сообщения найдены для {len(actual_subnets)} подсетей: {sorted(actual_subnets)}")
if set(all_updates.keys()) - actual_subnets:
    print(f"⚠️ GPT попытался добавить несуществующие сабнеты: {set(all_updates.keys()) - actual_subnets}")

# --- Запись в таблицу ---
sh_dst = gc.open_by_key(GOOGLE_SHEET2_ID)
sheet = sh_dst.worksheet("Dis и выводы")
header = sheet.row_values(1)
yesterday_str = yesterday.strftime('%d.%m.%Y')

# === БЛОК: если нужной даты нет в первой строке — создаём столбец справа ===
if not any(h.strip() == yesterday_str for h in header):
    new_col_index = len(header) + 1  # gspread uses 1-based index
    sheet.add_cols(1)
    sheet.update_cell(1, new_col_index, yesterday_str)
    print(f"➕ Добавлена новая колонка для даты: {yesterday_str}")
    header.append(yesterday_str)
    col = new_col_index
else:
    col = next(i for i, h in enumerate(header) if h.strip() == yesterday_str) + 1

netids = [str(int(i)) for i in sheet.col_values(1)[1:] if i.strip()]

# --- Фильтруем только те подсети, что реально были в actual_subnets ---
filtered_updates = {k: v for k, v in all_updates.items() if k in actual_subnets}

cell_list = []
for subnet, summary in filtered_updates.items():
    if subnet in netids:
        row = netids.index(subnet) + 2
        cell = gspread.cell.Cell(row=row, col=col, value=summary)
        cell_list.append(cell)
        print(f"📝 Подготовлено: {subnet} → row {row}, col {col}")
    else:
        print(f"⚠️ Subnet {subnet} не найдена в таблице")

if cell_list:
    sheet.update_cells(cell_list)
    print(f"✅ Обновлено {len(cell_list)} ячеек одним запросом")
else:
    print("⚠️ Нет данных для записи!")

print("🎉 Готово. Примерная стоимость: ${:.4f}".format(0.0005 * total_tokens / 1000 + 0.0015 * 2000 / 1000))
