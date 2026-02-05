import asyncio
import os
import re
import json
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import httpx
from dotenv import load_dotenv

# === Конфигурация и вспомогательные функции ===
load_dotenv()

def load_projects() -> list[str]:
    if not os.path.exists("projects.txt"):
        return []
    with open("projects.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def load_surnames() -> dict:
    if os.path.exists(SURNAME_FILE):
        try:
            with open(SURNAME_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_surnames(surnames: dict):
    with open(SURNAME_FILE, "w", encoding="utf-8") as f:
        json.dump(surnames, f, ensure_ascii=False, indent=2)

# === Константы ===
CURRENT_PROJECTS = load_projects()
SURNAME_FILE = "surnames.json"
USER_SURNAMES = load_surnames()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ Не задан TELEGRAM_TOKEN в .env")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ Не задан OPENROUTER_API_KEY в .env")

# === Вспомогательные функции времени ===
def parse_time_to_minutes(time_str: str) -> int:
    time_str = time_str.lower().strip()
    time_str = re.sub(r'часов?|часа?|час', 'ч', time_str)
    time_str = re.sub(r'минут?|мин', 'мин', time_str)
    time_str = re.sub(r',', '.', time_str)

    total_minutes = 0
    hour_match = re.search(r'(\d+(?:\.\d+)?)\s*ч', time_str)
    if hour_match:
        total_minutes += int(float(hour_match.group(1)) * 60)
    min_match = re.search(r'(\d+)\s*мин', time_str)
    if min_match:
        total_minutes += int(min_match.group(1))
    return total_minutes

def extract_time_entries(text: str) -> list[str]:
    lines = text.splitlines()
    time_entries = []
    for line in lines:
        line = line.strip()
        if not line or line in CURRENT_PROJECTS or line.endswith(":") or line.startswith("#"):
            continue
        if any(word in line for word in ["мин", "час", "ч"]):
            if " - " in line:
                time_part = line.rsplit(" - ", 1)[1]
                time_entries.append(time_part)
    return time_entries

def format_total_time(minutes: int) -> str:
    if minutes == 0:
        return "0 мин"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours} ч {mins} мин" if mins > 0 else f"{hours} ч"
    return f"{mins} мин"

# === Инициализация бота ===
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# === Состояния FSM ===
class ReportState(StatesGroup):
    awaiting_surname = State()
    awaiting_confirmation = State()

# === Промпты ===
def get_prompts() -> str:
    if not os.path.exists("prompt.txt"):
        raise FileNotFoundError("❌ Файл prompt.txt не найден! Создайте его в корне проекта.")
    
    with open("prompt.txt", "r", encoding="utf-8") as f:
        template = f.read()

    projects_block = "\n\n".join([f"{proj}\n-" for proj in CURRENT_PROJECTS])
    projects_names = ", ".join(CURRENT_PROJECTS)

    return template.format(projects_names=projects_names, projects_block=projects_block)

def get_report_info() -> str:
    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)
    date_str = now.strftime("%d_%m_%y")
    return f"#вечерний_отчет_{date_str}"

# === LLM ===
async def call_llm(text: str) -> str:
    prompt = get_prompts().format(user_text=text)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/report-bot",
        "X-Title": "ReportBot",
        "Content-Type": "application/json"
    }
    data = {
        "model": "z-ai/glm-4.5-air:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800
    }
    try:
        async with httpx.AsyncClient(timeout=50.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    lines = content.splitlines()
                    if len(lines) > 2:
                        content = "\n".join(lines[1:-1])
                return content
            else:
                return f"⚠️ Ошибка OpenRouter ({response.status_code})"
    except Exception as e:
        return f"⚠️ Ошибка сети: {str(e)}"

# === Обработка отчёта ===
async def process_report(message: types.Message, user_text: str, state: FSMContext):
    if len(user_text) < 10:
        await message.answer("Пожалуйста, опишите подробнее (минимум 10 символов).")
        return

    hashtag = get_report_info()
    await message.answer("🧠 Обрабатываю вечерний отчёт...")

    result = await call_llm(user_text)

    data = await state.get_data()
    surname = data.get("surname", "Пользователь")
    surname_tag = f"#{surname}"

    time_entries = extract_time_entries(result)
    total_minutes = sum(parse_time_to_minutes(entry) for entry in time_entries)
    total_time_str = format_total_time(total_minutes)
    total_hours_decimal = total_minutes / 60
    full_report = f"{hashtag}\n{surname_tag}\n\n{result}\n\n⏱️ Всего: {total_time_str} ({total_hours_decimal:.2f} ч)"

    await message.answer(full_report)
    await state.clear()

# === Обработчики ===
@dp.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in USER_SURNAMES:
        await message.answer(
            "📝 Отправляй текст с итогами дня\n\n"
            "Я оформлю вечерний отчёт по всем проектам!"
        )
    else:
        await message.answer("👋 Привет! Пожалуйста, укажите вашу фамилию:")
        await state.set_state(ReportState.awaiting_surname)

@dp.message(StateFilter(ReportState.awaiting_surname))
async def save_surname(message: types.Message, state: FSMContext):
    surname = message.text.strip()
    if len(surname) < 2:
        await message.answer("Фамилия должна быть не короче 2 символов. Попробуйте снова:")
        return

    surname_clean = re.sub(r"[^а-яА-ЯёЁa-zA-Z\-]", "", surname)
    if not surname_clean:
        await message.answer("Фамилия должна содержать хотя бы одну букву. Попробуйте снова:")
        return

    user_id = str(message.from_user.id)
    USER_SURNAMES[user_id] = surname_clean
    save_surnames(USER_SURNAMES)

    await state.set_state(None)
    await message.answer(
        f"✅ Фамилия сохранена: {surname_clean}\n\n"
        "Теперь отправляйте текст с итогами дня"
    )

@dp.message(~StateFilter(ReportState.awaiting_surname))
async def handle_input(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id not in USER_SURNAMES:
        await message.answer("Сначала укажите фамилию через команду /start.")
        return

    await state.update_data(surname=USER_SURNAMES[user_id])

    if message.text:
        await process_report(message, message.text, state)
    else:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")

# === Запуск ===
async def main():
    print(f"✅ Бот запущен! Актуальные проекты: {', '.join(CURRENT_PROJECTS)}")
    print(f"📁 Фамилии хранятся в: {SURNAME_FILE}")
    print("📄 Системный промпт загружается из: prompt.txt")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())