import os
import asyncio
from datetime import datetime
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
        print(f"Saved audio message from {user} as {filename}")
    else:
        print(f"Received message from {user}: {update.message.text}")

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