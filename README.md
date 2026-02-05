# daily-report-bot
AI-powered Telegram bot that turns free-form daily updates into structured project reports...

## ✨ Features

- 🧠 **AI-powered parsing** via OpenRouter (using `glm-4.5-air:free`)
- 📋 **Structured output** by predefined projects from `projects.txt`
- ⏱️ **Automatic time extraction** (`1.5 ч`, `30 мин`, `2 часа 15 минут` → суммируется)
- 🟩🟧🟥 **Progress indicators**:
  - 🟩 — fully completed  
  - 🟧 — in progress / partial  
  - 🟥 — not done
- 👤 **Personalized hashtags** by user surname (saved once per Telegram ID)
- 📅 **Auto-date tagging**: `#вечерний_отчет_05_02_26`
- 📁 **Separate prompt file** — easy to customize system instructions

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/your-username/daily-report-bot.git
cd daily-report-bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp config.example.env .env
```
Then edit .env with your credentials:
```env
TELEGRAM_TOKEN=your_bot_token_from_BotFather
OPENROUTER_API_KEY=your_key_from_openrouter.ai
CUTOFF_HOUR=12
```

### 4. Define your projects
Edit `projects.txt` — one project per line:
```txt
Project 1
Project 2
```

### 5. (Optional) Customize the AI prompt
Edit `prompt.txt` to change how the LLM formats reports.

### 6. Run the bot
```bash
python bot.py
```
>💡 First time? Send /start in Telegram — bot will ask for your surname.

---

### 🔐 Security Notes
Never commit `.env` — it’s already in .gitignore.  
User data (surnames.json) stores only Telegram user IDs and surnames. Clear it before public sharing.  
The bot runs locally — no external server required.  

### 🛠 Tech Stack
Python 3.9+  
aiogram 3.x — modern async Telegram framework  
OpenRouter — unified API for LLMs  
httpx — async HTTP client  
python-dotenv — environment management  

### 📜 License
This project is licensed under the MIT License — see LICENSE for details.

>Made with ❤️ for creative teams who hate formatting reports.
