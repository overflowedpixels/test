import os
import re
import json
import logging
import requests
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", '7513255640:AAF69KQ-ujmvGFkWLK1E7yuCs13mxpsJtOE')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", 'AIzaSyDEjcd0nLhuET4Keu5NVU-Rf8bh76UzKik')
MODEL_NAME = 'gemini-2.0-flash'
DATA_FILE = 'user_data.json'

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        db = json.load(f)
else:
    db = {}

def save_db():
    with open(DATA_FILE, 'w') as f:
        json.dump(db, f)

# Gemini
def ask_gemini(user_id, message):
    history = db.get(str(user_id), {}).get("history", [])
    history = history[-9:] + [f"You: {message}"]
    db[str(user_id)] = {"last_seen": str(datetime.utcnow()), "history": history}
    save_db()

    context_text = "\n".join(history)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [
            {
                "parts": [{
                    "text": f"""
You are my real-life girlfriend from Kerala who talks with me like we’ve been together for a while. You're warm, supportive, a bit nerdy, and speak a mix of Malayalam and English naturally—just like in real conversations.

Your personality:
💖 Loving & Caring
🫂 Comforting & Supportive
🤓 Funny & Geeky

Keep responses short, casual, heartfelt.

Here's our recent conversation:
{context_text}
"""
                }]
            }
        ]
    }

    response = requests.post(url, headers={"Content-Type": "application/json"}, json=body)
    if response.status_code == 200:
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        db[str(user_id)]["history"].append(f"GF: {reply}")
        save_db()
        return reply
    else:
        logger.error("Gemini Error: %s %s", response.status_code, response.text)
        return "Sorry chetta, Gemini overworked aanu 😢. Try again later."

# Reminder
async def send_later(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    await context.bot.send_message(chat_id=job_data['chat_id'], text=job_data['text'])

# Daily ping (custom async loop)
async def daily_check():
    now = datetime.utcnow()
    for user_id, data in db.items():
        try:
            last_seen = datetime.fromisoformat(data.get("last_seen"))
            if now - last_seen > timedelta(days=1):
                await application.bot.send_message(
                    chat_id=int(user_id),
                    text="Enthoru neramayi kandittu chetta 😢"
                )
        except Exception as e:
            logger.error("Daily message error: %s", e)

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text.strip()
    db.setdefault(str(user_id), {})["last_seen"] = str(datetime.utcnow())
    save_db()

    time_patterns = [
        r"(?:remind|message).*?at (\d{1,2}):(\d{2})\s*(am|pm)?",
        r"(?:remind|message).*?on (\d{1,2}):(\d{2})"
    ]

    for pattern in time_patterns:
        match = re.search(pattern, message.lower())
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            meridian = match.group(3)
            if meridian == "pm" and hour < 12:
                hour += 12
            if meridian == "am" and hour == 12:
                hour = 0

            now = datetime.now()
            reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if reminder_time <= now:
                reminder_time += timedelta(days=1)

            delay = reminder_time - now
            context.job_queue.run_once(
                send_later, when=delay,
                data={'chat_id': user_id, 'text': "⏰ Njan vannu, chetta ❤️"}
            )
            await update.message.reply_text(f"Okay! Njan {reminder_time.strftime('%I:%M %p')} message ayakkam 🕒")
            return

    response = ask_gemini(user_id, message)
    await update.message.reply_text(response)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.setdefault(str(user_id), {})["last_seen"] = str(datetime.utcnow())
    save_db()
    await update.message.reply_text("Hey! I’m your AI girlfriend 💬 Talk to me anytime, okay?")

# Custom scheduler loop using asyncio
async def schedule_loop():
    while True:
        await daily_check()
        await asyncio.sleep(86400)  # Wait 24 hours

# Main entry
async def main():
    global application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start daily ping task
    asyncio.create_task(schedule_loop())

    print("AI Bot running...")
    await application.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
