import os
import asyncio
from datetime import datetime
import logging
from pathlib import Path

# Import pipeline modules
from src.transcription import transcribe_audio_only
from src.llm_polish import process_transcript
from src.notion_integration import push_from_memory

from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Patch event loop for interactive environments (Cursor, Jupyter, etc.)
try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Restrict usage to a single Telegram username (default: zaringleb)
ALLOWED_USERNAME = os.getenv("ALLOWED_USERNAME")

VOICE_DIR = "voice_messages"
os.makedirs(VOICE_DIR, exist_ok=True)

# Create logs directory
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure basic logging
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


# ============================================================================
# Core Pipeline Functions
# ============================================================================


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
        raw_transcript = transcribe_audio_only(audio_path)
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
        notion_url, entry_dir = push_from_memory(
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


# ============================================================================
# User Authorization
# ============================================================================


def is_user_authorized(update: Update) -> bool:
    """Check if the user is authorized to use this bot."""
    if ALLOWED_USERNAME is None:
        return True  # No restriction configured

    user_identifier = update.effective_user.username or update.effective_user.id
    return user_identifier == ALLOWED_USERNAME


def get_user_identifier(update: Update) -> str:
    """Get a string identifier for the user (username or ID)."""
    return update.effective_user.username or str(update.effective_user.id)


# ============================================================================
# Command Handlers
# ============================================================================


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
    
    welcome_message = """🎙️ **Audio Journal Bot**

Welcome! I help you create organized journal entries from voice messages.

**How it works:**
1. 🎤 Send me a voice message
2. 🤖 I'll transcribe it using AI
3. ✨ Clean up the text while keeping your voice
4. 📝 Save it to your Notion database
5. 📁 Archive everything locally for backup

**What you need:**
• Just send voice messages - I handle the rest!
• Your entries are organized by date (4 AM cutoff)
• Both raw and polished versions are saved

**Ready to start journaling?**
Send me your first voice message! 🎯"""

    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command with detailed usage information."""
    user = get_user_identifier(update)
    logging.info(f"User {user} requested help")
    
    if not is_user_authorized(update):
        await update.message.reply_text(
            "🚫 Sorry, this bot is restricted to authorized users only."
        )
        return
    
    help_message = """📚 **Help & Commands**

**Available Commands:**
• `/start` - Welcome message and introduction
• `/help` - This help message

**How to use:**
1. **Voice Messages** 🎤
   - Send any voice message in any language
   - I'll transcribe and organize it automatically
   - No length limits, but shorter messages work better

2. **Processing Steps** ⚙️
   - Transcription via OpenAI Whisper
   - AI polishing to clean up filler words
   - Automatic date assignment (4 AM cutoff)
   - Notion database entry creation
   - Local backup in organized folders

3. **What gets saved** 💾
   - **Notion**: Polished entry with title and date
   - **Local**: Raw transcript, polished version, metadata

**Tips:**
• Speak clearly for best transcription
• Each message becomes one journal entry
• Entries before 4 AM count as previous day
• Check your Notion database to see results

Need more help? Just send a voice message to try it out! 🚀"""

    await update.message.reply_text(
        help_message,
        parse_mode=ParseMode.MARKDOWN
    )


# ============================================================================
# Message Handlers
# ============================================================================


async def handle_audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice and audio messages by downloading and processing them."""
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


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (currently just logs them)."""
    user = get_user_identifier(update)
    logging.info(f"Received text message from {user}: {update.message.text}")
    # TODO: Implement text-based journal entries (future enhancement)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler that dispatches to specific handlers based on message type."""
    # Check user authorization first
    if not is_user_authorized(update):
        logging.warning(f"Received message from unauthorized user — ignored.")
        return

    # Dispatch to appropriate handler based on message type
    if update.message.voice or update.message.audio:
        await handle_audio_message(update, context)
    else:
        await handle_text_message(update, context)


# ============================================================================
# Application Setup
# ============================================================================


async def main():
    """Initialize and start the Telegram bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Add message handler (for voice messages and other content)
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("Bot is polling for messages...")
    await application.run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Fallback for already running event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
