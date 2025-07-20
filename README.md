# 📝 Audio Journal Bot

An end-to-end **voice-to-Notion journal** built with Python. Speak your thoughts on Telegram, and the bot will:

1. Collect voice messages via Telegram.
2. Automatically transcribe audio with OpenAI Whisper.
3. Chunk & organise the text in Notion (grouped by day).
4. *(planned)* Search, review & analyse your journal in Notion.

---

## 📂 Project Structure
```
audio-journal-bot/
├── src/                # Python package
│   ├── telegram_bot.py # Current bot entry-point
│   ├── transcription.py # Whisper wrapper
│   └── llm_polish.py   # LLM-powered transcript polishing
├── voice_messages/     # Saved .ogg/.mp3 voice notes
├── .env                # Secrets (TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, …)
├── requirements.txt    # Python dependencies
├── README.md           # You are here 🡅
├── tests/              # Unit tests
└── .gitignore          # Ignore venv, .env, etc.
```

## 🚀 Quick-start
```bash
# Clone & enter repo
git clone <repo-url> && cd audio-journal-bot

# Create and activate venv
python3 -m venv .venv && source .venv/bin/activate

# Install deps
pip install -r requirements.txt

# Add secrets
cp .env.example .env  # or create manually

# Run the bot
python src/telegram_bot.py

# Run unit tests
python -m unittest discover -s tests -v
```

---

## 🛣️ Roadmap / Task Board
Classic Cursor-style checklist – ticked items are **done** in this repo.

| Status | Task |
| :---: | --- |
| ✅ | Initialise repo & directory structure |
| ✅ | Add `.gitignore`, `.env` template |
| ✅ | Pin core dependencies in `requirements.txt` |
| ✅ | Basic Telegram bot skeleton |
| ✅ | Print all incoming messages |
| ✅ | Save voice/audio messages to `voice_messages/` and log filename |
| ✅ | Transcribe audio with OpenAI Whisper |
| ✅ | Chunk transcription (≈1-2k tokens each) |
| ✅ | Polish transcript with LLM |
| ⬜ | Notion integration – create daily pages & append chunks |
| ⬜ | Error handling & retry logic (tenacity) |
| ⬜ | CLI script for searching history |
| ⬜ | Dockerfile & dev-container setup |
| ⬜ | Optional webhook deployment (serverless) |

---

## 🔧 Configuration
Create a `.env` file with:
```
TELEGRAM_BOT_TOKEN=xxxxx
OPENAI_API_KEY=xxxxx
NOTION_API_KEY=xxxxx
NOTION_DATABASE_ID=xxxxx  # Target Notion DB / page
```

---

## 🏗️ Architecture Overview
```
[User] --voice-->  Telegram Bot  --file-->  /voice_messages
                                   |                              
                                   | Whisper (OpenAI)
                                   v
                               Transcribed Text
                                   |
                                   v
                            Chunk & Summarise
                                   |
                                   v
                               Notion API
                                   |
                                   v
                         Daily Notion Journal Page
```

* **Telegram Bot** – Receives messages, downloads audio.
* **Whisper API** – Performs speech-to-text.
* **Processing layer** – Splits text into manageable chunks.
* **Notion Client** – Persists data, grouped by date.

---

## 📜 License
MIT – see `LICENSE` for details. 