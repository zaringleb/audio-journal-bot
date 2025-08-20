import os
import asyncio
from datetime import datetime
import logging
from pathlib import Path

# Import pipeline modules
from src.transcription import transcribe_audio
from src.llm_polish import process_transcript
from src.notion_integration import create_entry_from_memory

from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERNAME = os.getenv("ALLOWED_USERNAME")

VOICE_DIR = "voice_messages"
os.makedirs(VOICE_DIR, exist_ok=True)

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        RotatingFileHandler(
            "logs/bot.log",
            maxBytes=10 * 1024 * 1024,  # 10MB per file
            backupCount=5,  # Keep 5 old files
        )
        # No StreamHandler() = no console spam
    ],
)

# Reduce noise from HTTP client per-request INFO logs (e.g., getUpdates polling)
logging.getLogger("httpx").setLevel(logging.WARNING)


def pipeline_blocking(audio_path: str, message_dt: datetime, user: str) -> str:
    """Execute the journal processing pipeline in a blocking manner.

    This function runs the complete pipeline: transcription → polishing → Notion.
    It's designed to run in a thread pool to avoid blocking the async event loop.

    Args:
        audio_path: Path to the downloaded audio file
        message_dt: Original message timestamp from Telegram
        user: Username or user ID for logging

    Returns:
        Notion page URL

    Raises:
        Exception: Any error during pipeline execution (caller should handle)
    """
    try:
        logging.info(f"[Pipeline] ({user}) Transcribing…")

        # 1. Transcribe audio (in memory)
        raw_transcript = transcribe_audio(audio_path)
        logging.info(
            f"[Pipeline] Transcription completed ({len(raw_transcript)} characters)"
        )

        # 2. Polish + extract keyword (in memory)
        logging.info("[Pipeline] Polishing transcript & extracting keyword…")
        polished_data = process_transcript(raw_transcript)
        logging.info(
            f"[Pipeline] Polishing completed, title: {polished_data.get('summary', 'Untitled')}"
        )

        # 3. Push to Notion and save artifacts
        logging.info("[Pipeline] Pushing to Notion and saving artifacts…")
        notion_url, entry_dir = create_entry_from_memory(
            raw_transcript=raw_transcript,
            polished_data=polished_data,
            message_dt=message_dt,
        )
        logging.info(f"[Pipeline] Notion page created: {notion_url}")
        logging.info(f"[Pipeline] Artifacts saved to: {entry_dir}")

        return notion_url

    except Exception as exc:
        # Log the full error details for debugging
        logging.error(
            f"[Pipeline] ({user}) Failed with error: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        # Re-raise the exception so the calling code can handle user notification
        raise
    finally:
        # Always cleanup: remove original audio file to save space
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logging.info(f"[Pipeline] Removed audio file {audio_path}")
        except OSError as cleanup_exc:
            logging.warning(
                f"[Pipeline] Could not delete audio file {audio_path}: {cleanup_exc}"
            )


def get_error_message(exc: Exception) -> str:
    """Generate user-friendly error message based on exception type and content."""
    error_type = type(exc).__name__
    exc_str = str(exc).lower()

    if "openai" in exc_str or "whisper" in exc_str:
        return "❌ Failed to transcribe audio. OpenAI/Whisper service may be temporarily unavailable. Please try again later."
    elif "notion" in exc_str:
        return "❌ Failed to save to Notion. Please check your Notion integration settings and try again."
    elif "json" in exc_str or "parse" in exc_str:
        return "❌ Failed to process transcript. There may be an issue with the AI response format. Please try again."
    elif "file" in exc_str or "path" in exc_str:
        return "❌ Failed to process audio file. The file may be corrupted or in an unsupported format."
    else:
        return f"❌ Processing failed due to an unexpected error ({error_type}). Please try again or contact support if the issue persists."


async def run_pipeline(
    audio_path: str,
    message_dt: datetime,
    user: str,
    *,
    chat_id: int,
    bot,
):
    """Execute the journal processing pipeline with comprehensive error handling.

    This function orchestrates the pipeline execution in a thread pool and handles
    user notifications for both success and failure cases.
    """
    loop = asyncio.get_running_loop()

    try:
        # Run pipeline in thread pool to avoid blocking the event loop
        notion_url = await loop.run_in_executor(
            None, pipeline_blocking, audio_path, message_dt, user
        )

        # Notify user of success
        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ Journal entry saved to Notion!\n[Open in Notion]({notion_url})",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    except Exception as exc:
        # Generate appropriate error message and notify user
        error_msg = get_error_message(exc)
        logging.info(f"[Pipeline] Sending error message to user {user}: {error_msg}")

        await bot.send_message(
            chat_id=chat_id,
            text=error_msg,
        )


def is_user_authorized(update: Update) -> bool:
    return ALLOWED_USERNAME is None or get_user_identifier(update) == ALLOWED_USERNAME


def get_user_identifier(update: Update) -> str:
    """Get a string identifier for the user (username or ID)."""
    return update.effective_user.username or str(update.effective_user.id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command with bot introduction and usage instructions."""
    user = get_user_identifier(update)
    logging.info(f"User {user} started the bot")
    
    # Check authorization first
    if not is_user_authorized(update):
        await update.message.reply_text(
            "🚫 Sorry, this bot is restricted to authorized users only."
        )
        return
    
    welcome_message = """🎙️ **Welcome to your Audio Journal Bot!**

To get started, just send me a voice message.

I will transcribe it, polish the text using AI, and save it directly to your Notion database.

For more details and a list of commands, type /help.
"""

    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command with detailed usage information."""
    user = get_user_identifier(update)
    logging.info(f"User {user} requested help")
    
    if not is_user_authorized(update):
        return
    
    help_message = """📚 **Help & Commands**

**How It Works**
1. 🎤 Send me a voice message.
2. 🤖 I transcribe it using OpenAI Whisper.
3. ✨ I polish the text to improve clarity while keeping your original voice.
4. 📝 The entry is saved to your Notion database, automatically dated (with a 4 AM cutoff).
5. 📁 All artifacts (raw transcript, polished version, metadata) are archived locally for backup.

**Available Commands**
• `/start` - Shows the welcome message.
• `/help` - Shows this detailed help guide.

**Tips**
• Speak clearly for the best transcription results.
• Each voice message becomes a single journal entry.
• Check your Notion database to see your saved entries.

Ready? Just send a voice message! 🚀"""

    await update.message.reply_text(
        help_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice and audio messages by downloading and processing them."""

    if not is_user_authorized(update):
        logging.warning(f"Received message from unauthorized user — ignored.")
        return
    
    user = get_user_identifier(update)
    file = update.message.voice or update.message.audio
    file_id = file.file_id
    file_unique_id = file.file_unique_id
    file_ext = "ogg" if update.message.voice else "mp3"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{VOICE_DIR}/{user}_{file_unique_id}_{timestamp}.{file_ext}"

    # Download the audio file
    tg_file = await context.bot.get_file(file_id)
    await tg_file.download_to_drive(filename)
    logging.info(f"Saved audio message from {user} → {filename}")

    # Inform user that processing has started
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="⏳ Processing your journal entry…"
    )

    # Freeing up the event loop to handle other messages (telegam lib requirement)
    asyncio.create_task(
        run_pipeline(
            filename,
            update.message.date,
            user,
            chat_id=update.effective_chat.id,
            bot=context.bot,
        )
    )


def main() -> None:
    """Initialize and start the Telegram bot (blocking call)."""

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    audio_or_voice = filters.AUDIO | filters.VOICE
    application.add_handler(MessageHandler(audio_or_voice, handle_audio_message))

    print("Bot is polling for messages…")
    # run_polling() sets up and runs the asyncio loop internally and blocks until shutdown.
    application.run_polling()


if __name__ == "__main__":
    main()
