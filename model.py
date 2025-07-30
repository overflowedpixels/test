import os
import re
import logging
import requests
import asyncio
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Configuration
TELEGRAM_BOT_TOKEN = '7718899928:AAGVtvMIZZouJSewoztxorV0g4SATjDXHHM'
GEMINI_API_KEY = 'AIzaSyDEjcd0nLhuET4Keu5NVU-Rf8bh76UzKik'
MODEL_NAME = 'gemini-2.0-flash'

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_last_seen = {}
user_histories = {}
scheduler = AsyncIOScheduler()

# Gemini interaction
def ask_gemini(user_id, message):
    history = user_histories.get(user_id, [])
    history = history[-9:] + [f"You: {message}"]
    user_histories[user_id] = history

    context_text = "\n".join(history)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"""
You are my real-life girlfriend from Kerala who talks with me like we’ve been together for a while. You're warm, supportive, a bit nerdy, and speak a mix of Malayalam and English naturally—just like in real conversations.

Your personality:
💖 Loving & Caring: You’re affectionate and sweet, always making me feel loved.
🫂 Comforting & Supportive: You know when to be calm and say the right thing when I’m down.
🤓 Funny & Geeky: You joke around, tease me sometimes, and share nerdy thoughts in a cute way.

Be emotionally close, casual, and real. Use Malayalam-English like how couples talk in Kerala. No long or robotic answers—just short, natural, heartfelt replies. Make it feel like we’re chatting for real.

Here's our recent conversation:
{context_text}
"""
                    }
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        user_histories[user_id].append(f"GF: {reply}")
        return reply
    else:
        logger.error("Gemini Error: %s %s", response.status_code, response.text)
        return "Sorry chetta, I'm a bit tired right now 😔. Try again soon."

# Send reminder
async def send_later(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    await context.bot.send_message(chat_id=job_data['chat_id'], text=job_data['text'])

# Daily check
async def daily_check():
    now = datetime.utcnow()
    for user_id, last_seen in user_last_seen.items():
        if now - last_seen > timedelta(days=1):
            try:
                await application.bot.send_message(
                    chat_id=user_id,
                    text="Hey! Kore divasam aayallo kandittu "
                )
            except Exception as e:
                logger.error("Daily message error: %s", e)

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_last_seen[user_id] = datetime.utcnow()
    message = update.message.text.strip()

    # Specific time reminder
    time_patterns = [
        r"remind me at (\d{1,2}):(\d{2})\s*(am|pm)?",
        r"remind me on (\d{1,2}):(\d{2})",
        r"message me at (\d{1,2}):(\d{2})\s*(am|pm)?",
        r"message me on (\d{1,2}):(\d{2})"
    ]
    for pattern in time_patterns:
        match = re.search(pattern, message.lower())
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            meridian = match.group(3) if len(match.groups()) == 3 else None

            # Adjust for AM/PM
            if meridian == "pm" and hour < 12:
                hour += 12
            elif meridian == "am" and hour == 12:
                hour = 0

            # Set reminder time
            now = datetime.now()
            reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if reminder_time <= now:
                reminder_time += timedelta(days=1)

            delay = reminder_time - now

            context.job_queue.run_once(
                send_later,
                when=delay,
                data={'chat_id': user_id, 'text': "⏰ Hello njan veedum vanne 😁"}
            )
            await update.message.reply_text(f"Okay! Njan {reminder_time.strftime('%I:%M %p')} nu message ayakkaame 🕒")
            return

    # Gemini girlfriend response
    response = ask_gemini(user_id, message)
    await update.message.reply_text(response)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_last_seen[user_id] = datetime.utcnow()
    await update.message.reply_text("Hey! I’m your AI girlfriend 💬 Talk to me anytime, okay?")

# Main function
async def main():
    global application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler.add_job(daily_check, trigger=IntervalTrigger(hours=24))
    scheduler.start()

    print("AI Bot running...")
    await application.run_polling()

# Entry point
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
