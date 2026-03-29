import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
BLINK_KEY = os.getenv("BLINK_KEY")

BLINK_API = "https://core.blink.new/api/ai"

# === AI CALL ===
def ask_ai(text):
    headers = {
        "Authorization": f"Bearer {BLINK_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": text}
        ]
    }

    try:
        r = requests.post(BLINK_API, headers=headers, json=data)
        res = r.json()

        if "choices" in res:
            return res["choices"][0]["message"]["content"]
        else:
            return "ERROR API:\n" + str(res)

    except Exception as e:
        return "ERROR: " + str(e)

# === HANDLER ===
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    reply = ask_ai(text)
    
    await update.message.reply_text(reply)

# === RUN ===
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT, chat))

print("BOT ACTIVE 🚀")

app.run_polling()
