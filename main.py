import requests
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from skill_loader import load_skill
import time

while True:
    try:
        app.run_polling()
    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)


BLINK_API = "https://api.blink.new/v1/chat/completions"
TOKEN = os.getenv("TOKEN")
BLINK_KEY = os.getenv("BLINK_KEY")

skill_context = load_skill()

# === call blink ===
def ask_ai(user_text):
    prompt = f"""
{skill_context}

User: {user_text}
AI:
"""

    headers = {
        "Authorization": f"Bearer {BLINK_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    r = requests.post(BLINK_API, headers=headers, json=data)
    
    if r.status_code != 200:
        return f"❌ Error: {r.text}"
    
    return r.json()["choices"][0]["message"]["content"]


# === handler ===
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    reply = ask_ai(user_text)
    
    await update.message.reply_text(reply)


# === start bot ===
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("✅ BOT RUNNING...")
app.run_polling()
