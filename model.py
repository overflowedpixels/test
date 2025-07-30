import os
import re
import json
import logging
import requests
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import nest_asyncio
nest_asyncio.apply()

# Config
TELEGRAM_BOT_TOKEN = '7718899928:AAGVtvMIZZouJSewoztxorV0g4SATjDXHHM'
GEMINI_API_KEY = 'AIzaSyDEjcd0nLhuET4Keu5NVU-Rf8bh76UzKik'
MODEL_NAME = 'gemini-2.0-flash'
DATA_FILE = 'user_data.json'

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load or initialize DB
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        db = json.load(f)
else:
    db = {}

def save_db():
    with open(DATA_FILE, 'w') as f:
        json.dump(db, f)

# Gemini Chat
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
You are my real-life girlfriend from Kerala. You're warm, supportive, a bit nerdy, and speak a mix of Malayalam and English.

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
        logger.error("Gemini Error: %s", response.text)
        return "Sorry chetta, Gemini is tired 😢."

# Daily check function
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
            logger.error("Daily check error: %s", e)

# Telegram message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text.strip()
    db.setdefault(str(user_id), {})["last_seen"] = str(datetime.utcnow())
    save_db()

    response = ask_gemini(user_id, message)
    await update.message.reply_text(response)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.setdefault(str(user_id), {})["last_seen"] = str(datetime.utcnow())
    save_db()
    await update.message.reply_text("Hey chetta! I’m your AI girlfriend 💬 Talk to me anytime ❤️")

# Flask app to expose /daily_ping
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

@app.route("/daily_ping")
def daily_ping():
    asyncio.run(daily_check())
    return "Daily check triggered", 200

def run_flask():
    app.run(host="0.0.0.0", port=8000)

# Main bot runner
async def main():
    global application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run Flask server in parallel
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    print("Bot and web server running...")
    await application.run_polling()

# Run the app
if __name__ == "__main__":
    asyncio.run(main())
