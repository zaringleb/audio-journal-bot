# 🎙️ Audio Journal Bot

A **voice-to-Notion journal** that transforms your spoken thoughts into organized, searchable entries. Simply send voice messages to a Telegram bot, and your audio is automatically transcribed, polished, and saved to Notion with proper organization.

## ✨ What It Does

1. **📱 Voice Input**: Send voice messages through Telegram
2. **🎯 Smart Transcription**: Uses OpenAI Whisper for accurate speech-to-text
3. **✍️ AI Polishing**: Cleans up transcripts while preserving your voice and meaning
4. **📚 Notion Integration**: Automatically creates organized journal entries with proper dates
5. **🗂️ Artifact Storage**: Saves both raw and polished transcripts for future reference

## 🚀 Quick Setup

### Prerequisites
- Python 3.9+
- Telegram Bot Token ([create here](https://t.me/BotFather))
- OpenAI API Key ([get here](https://platform.openai.com/api-keys))
- Notion Integration ([setup guide](https://developers.notion.com/docs/create-a-notion-integration))

### Installation

```bash
# Clone and enter the project
git clone <your-repo-url>
cd audio-journal-bot

# Setup Python environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration section)

# Run the bot
python -m src.telegram_bot
```

## ⚙️ Configuration

Create a `.env` file with your API credentials:

```env
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
NOTION_API_KEY=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id

# Optional
ALLOWED_USERNAME=your_telegram_username  # Restrict bot to specific user
NOTION_TEST_DATABASE_ID=xxxxx  # Testing Notion DB
```

### Notion Database Setup

Your Notion database should have these properties:
- **Title** (Title): Entry summary/keyword
- **Date** (Date): Journal date
- **Structured** (Rich Text): AI-polished transcript
- **Raw** (Rich Text): Original transcript

## 💡 How It Works

```
Telegram bot → Voice Message → Whisper API → LLM Polishing → Notion
```

1. **Send a voice message** to your Telegram bot
2. **Audio is transcribed** using OpenAI Whisper
3. **AI polishes the text** while preserving your voice and meaning
4. **Entry is created** in Notion with proper date logic (entries before 4 AM count as previous day)
5. **Artifacts are saved** locally in organized directories for backup

## 📁 Project Structure

```
audio-journal-bot/
├── src/                    # Core application code
│   ├── telegram_bot.py     # Bot entry point and message handling
│   ├── transcription.py    # OpenAI Whisper integration
│   ├── llm_polish.py       # AI text polishing
│   ├── notion_integration.py # Notion API integration
│   ├── text_utils.py       # Text chunking utilities
│   └── date_utils.py       # Date logic
├── journal_entries/        # Organized archives per entry
│   └── YYYYMMDD_HHMMSS_id/ # Each entry gets unique directory
│       ├── raw_transcript.txt
│       ├── polished.json
│       └── metadata.json
├── voice_messages/         # Temporary audio files (auto-deleted)
├── tests/                  # Unit tests
└── .env                    # Your API credentials
```

### ✅ **Current Capabilities**
- **Voice transcription** with high accuracy
- **Intelligent text polishing** that preserves meaning
- **Automatic Notion organization** with date-based logic
- **Robust error handling** with user feedback
- **Comprehensive logging** for debugging
- **Organized local archives** for each entry
- **User authentication** (optional username restriction)


## 🛠️ Usage

1. **Start the bot**: `python -m src.telegram_bot`
2. **Send voice messages** to your Telegram bot
3. **Receive confirmation** when entries are saved to Notion
4. **Check your Notion database** for organized entries
5. **Find local archives** in `journal_entries/` directories

## 🧪 Testing
```bash
source .venv/bin/activate
python -m unittest discover -s tests -v # Run all tests
python -m unittest tests.test_text_utils -v # Test specific modules
RUN_NOTION_TESTS=1 python -m unittest tests.test_notion_integration -v # Test Notion integration (requires API setup)
```

### Logs
The bot provides detailed logging to help diagnose issues. Logs are saved to `logs/bot.log` with automatic rotation (10MB per file, keeps 5 backups).

## 📜 License

MIT License - feel free to use, modify, and distribute as needed.

---

**Built for personal journaling with privacy and organisation in mind.** 🔒 
