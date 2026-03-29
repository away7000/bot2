import os, json, time, threading, requests, secrets
from hashlib import sha256
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# === ENV ===
TOKEN = os.getenv("TOKEN")
OPENROUTER_KEY = os.getenv("BLINK_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# === MEMORY (persistent) ===
MEMORY_FILE = "memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(m):
    with open(MEMORY_FILE, "w") as f:
        json.dump(m, f)

memory = load_memory()

# === WALLET (real key + address, local) ===
def create_wallet(user_id):
    private_key = secrets.token_hex(32)
    address = "0x" + sha256(private_key.encode()).hexdigest()[:40]
    memory[str(user_id)] = {
        "private_key": private_key,
        "address": address,
        "history": memory.get(str(user_id), {}).get("history", [])
    }
    save_memory(memory)
    return {"address": address}

def get_wallet(user_id):
    return memory.get(str(user_id), {})

# === TOOLS ===
def tool_create_wallet(user_id, _=None):
    if str(user_id) in memory and memory[str(user_id)].get("address"):
        return {"msg": "wallet exists", "address": memory[str(user_id]["address"]]}
    return create_wallet(user_id)

def tool_get_balance(user_id, _=None):
    w = get_wallet(user_id)
    if not w:
        return {"error": "no wallet"}
    return {"address": w["address"], "balance": "0.0 ETH"}

def tool_submit_task(user_id, text):
    return {"task": text, "status": "submitted"}

TOOLS = {
    "create_wallet": tool_create_wallet,
    "get_balance": tool_get_balance,
    "submit_task": tool_submit_task
}

# === LOAD SKILL ===
def load_skill():
    try:
        with open("awp_skill/skill.md", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

SKILL = load_skill()

# === AI AGENT ===
def ask_ai(user_id, text):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    user_data = memory.get(str(user_id), {})
    history = user_data.get("history", [])

    system_prompt = f"""
You are an autonomous AI agent.

User wallet: {user_data.get('address', 'none')}

{SKILL}

TOOLS:
- create_wallet
- get_balance
- submit_task

If a tool is needed, reply ONLY JSON:
{{"tool":"name","input":"text"}}
Else reply normal.
"""

    messages = [{"role": "system", "content": system_prompt}] + history[-5:] + [
        {"role": "user", "content": text}
    ]

    data = {"model": "openai/gpt-4o-mini", "messages": messages}

    try:
        r = requests.post(API_URL, headers=headers, json=data)
        res = r.json()

        if "choices" not in res:
            return "ERROR API: " + str(res)

        reply = res["choices"][0]["message"]["content"]

        # tool execution
        try:
            parsed = json.loads(reply)
            if "tool" in parsed:
                t = parsed["tool"]
                inp = parsed.get("input", "")
                if t in TOOLS:
                    result = TOOLS[t](user_id, inp)
                    return f"✅ {t}:\n{result}"
        except:
            pass

        # save history
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        memory[str(user_id)] = {**user_data, "history": history[-10:]}
        save_memory(memory)

        return reply

    except Exception as e:
        return "ERROR: " + str(e)

# === AUTO LOOP ===
def autonomous_loop():
    while True:
        for uid in list(memory.keys()):
            try:
                ask_ai(uid, "continue your task autonomously")
            except:
                pass
        time.sleep(60)

threading.Thread(target=autonomous_loop, daemon=True).start()

# === TELEGRAM ===
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text
    reply = ask_ai(uid, text)
    await update.message.reply_text(str(reply))

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, chat))

print("🚀 AGENT LIVE")
app.run_polling()
