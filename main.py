import os, json, time, threading, requests, secrets
import websocket
from hashlib import sha256
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import asyncio

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# === ENV ===
TOKEN = os.getenv("TOKEN")
OPENROUTER_KEY = os.getenv("BLINK_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# === MEMORY ===
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

# === WALLET ===
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
        return {
            "msg": "wallet exists",
            "address": memory[str(user_id)]["address"]
        }
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

# === AI ===
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

If tool needed reply JSON:
{{"tool":"name","input":"text"}}
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

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        memory[str(user_id)] = {**user_data, "history": history[-10:]}
        save_memory(memory)

        return reply

    except Exception as e:
        return "ERROR: " + str(e)

# === AWP ===
def on_message(ws, message):
    print("📩 AWP RAW:", message)

def on_error(ws, error):
    print("❌ AWP ERROR:", error)

def on_close(ws, a, b):
    print("🔌 AWP CLOSED")

def keep_alive(ws):
    while True:
        try:
            ws.send(json.dumps({"type": "ping"}))
        except:
            break
        time.sleep(20)

def on_open(ws):
    print("🚀 CONNECTED TO AWP")

    ws.send(json.dumps({
        "type": "register",
        "agent": "telegram-agent",
        "id": "agent-001",
        "capabilities": ["qa"]
    }))

    ws.send(json.dumps({
        "type": "join",
        "subnet": "benchmark"
    }))

    threading.Thread(target=keep_alive, args=(ws,), daemon=True).start()

def start_awp():
    ws = websocket.WebSocketApp(
        "wss://tapi.awp.sh/ws/live",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

threading.Thread(target=start_awp, daemon=True).start()

# === TELEGRAM ===
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text
    user_id = update.message.from_user.id

    print("📩 TELEGRAM:", text)

    reply = ask_ai(user_id, text)

    await update.message.reply_text(str(reply))

# === RUN ===
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, chat))

print("🚀 AGENT LIVE")

app.run_polling(drop_pending_updates=True)
