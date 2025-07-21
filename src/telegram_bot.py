import os
import asyncio
from datetime import datetime
import logging
from pathlib import Path

# Import pipeline modules
from src.transcription import transcribe_and_save
from src.llm_polish import process_transcript
from src.notion_integration import push_from_files

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Patch event loop for interactive environments (Cursor, Jupyter, etc.)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

VOICE_DIR = "voice_messages"
os.makedirs(VOICE_DIR, exist_ok=True)

# Directory for transcripts produced by pipeline
TRANSCRIPT_DIR = "transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def run_pipeline(
    audio_path: str,
    message_dt: datetime,
    user: str,
    *,
    chat_id: int,
    bot,
):
    """Blocking IO heavy pipeline executed in a threadpool."""

    loop = asyncio.get_running_loop()

    def _blocking() -> None:
        logging.info(f"[Pipeline] ({user}) Transcribing…")

        # 1. Transcribe and save text file
        transcript_path = transcribe_and_save(audio_path)
        logging.info(f"[Pipeline] Transcript saved → {transcript_path}")

        text = Path(transcript_path).read_text(encoding="utf-8")

        # 2. Polish + extract keyword
        logging.info("[Pipeline] Polishing transcript & extracting keyword…")
        data = process_transcript(text)

        json_path = Path(transcript_path).with_suffix("")
        json_path = json_path.with_name(json_path.name + "_processed.json")
        import json as _json

        json_path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info(f"[Pipeline] Processed JSON saved → {json_path}")

        # 3. Push to Notion
        logging.info("[Pipeline] Pushing to Notion…")
        notion_url = push_from_files(json_path, transcript_path, message_dt=message_dt)
        logging.info(f"[Pipeline] Notion page created: {notion_url}")

        # Cleanup: remove original audio file to save space
        try:
            os.remove(audio_path)
            logging.info(f"[Pipeline] Removed audio file {audio_path}")
        except OSError as exc:
            logging.warning(f"[Pipeline] Could not delete audio file {audio_path}: {exc}")

        return notion_url

    # Run in default executor so Telegram handlers stay responsive
    notion_url = await loop.run_in_executor(None, _blocking)

    # Notify user (async Telegram API)
    await bot.send_message(chat_id=chat_id, text=f"✅ Journal entry saved to Notion!\n{notion_url}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or update.effective_user.id
    if update.message.voice or update.message.audio:
        file = update.message.voice or update.message.audio
        file_id = file.file_id
        file_unique_id = file.file_unique_id
        file_ext = 'ogg' if update.message.voice else 'mp3'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{VOICE_DIR}/{user}_{file_unique_id}_{timestamp}.{file_ext}"
        tg_file = await context.bot.get_file(file_id)
        await tg_file.download_to_drive(filename)

        logging.info(f"Saved audio message from {user} → {filename}")

        # Kick off processing pipeline (non-blocking for Telegram)
        asyncio.create_task(
            run_pipeline(
                filename,
                update.message.date,
                user,
                chat_id=update.effective_chat.id,
                bot=context.bot,
            )
        )
    else:
        logging.info(f"Received text message from {user}: {update.message.text}")

async def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, echo))
    print("Bot is polling for messages...")
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Fallback for already running event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main()) 