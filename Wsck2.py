import asyncio
import re
import json
import os
from typing import List
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CommandHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# ====================== DATABASE ======================
DB_FILE = "user_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "stats": {}}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(DB, f, indent=4)

DB = load_db()

ADMIN_ID = 5624278091

def is_allowed(user_id: int) -> bool:
    return user_id == ADMIN_ID or DB["users"].get(str(user_id), {}).get("allowed", False)

def add_user_request(user_id: int, username: str, first_name: str):
    uid = str(user_id)
    if uid not in DB["users"]:
        DB["users"][uid] = {
            "username": username or "",
            "first_name": first_name or "",
            "allowed": False,
            "requested_at": datetime.now().isoformat()
        }
        save_db()

def set_user_allowed(user_id: int, allowed: bool):
    uid = str(user_id)
    if uid in DB["users"]:
        DB["users"][uid]["allowed"] = allowed
        save_db()

def log_check(user_id: int, count: int = 1):
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if uid not in DB["stats"]:
        DB["stats"][uid] = {"daily": {}, "total": 0}
    
    DB["stats"][uid]["daily"][today] = DB["stats"][uid]["daily"].get(today, 0) + count
    DB["stats"][uid]["total"] = DB["stats"][uid].get("total", 0) + count
    save_db()

# ====================== ULTRA FAST BOT ======================
class UltraFastClient:
    def __init__(self, api_id: int, api_hash: str, session_string: str, name: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.name = name
        self.client = TelegramClient(StringSession(session_string), api_id, api_hash)
        self.active_tasks = 0
        self.max_tasks = 6
    
    async def connect(self):
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                print(f"{self.name} - Not authorized")
                return False
            print(f"{self.name} - Connected & Authorized")
            return True
        except Exception as e:
            print(f"{self.name} - Connection failed:", e)
            return False
    
    def can_accept_task(self):
        return self.active_tasks < self.max_tasks
    
    def start_task(self):
        self.active_tasks += 1
    
    def end_task(self):
        if self.active_tasks > 0:
            self.active_tasks -= 1

class UltraFastBot:
    def __init__(self, bot_token: str):
        self.bot = Bot(bot_token)
        self.clients = [
            UltraFastClient(24742957, "40d421e05a414534910ebc0998f97c10",
                "1BVtsOKwBu8SY0NXUwrafneFgpyXKdXQYZuceqXpABICi8whUhUB_EVnOqFDYSFFcm5d0HKJ3UnuMtSuVNd8V6uv31gi-3sfzKkpe5AipKV6vHVOM6wPMzCBE-feFuJ-f-rul1GpI390_rTB6KJVbWVti9teusIbyxmpoGHY727kwavTrSMcw_fY_1Uxn5D8a-IKnBHAthmsOKjCb0Wzt4xcoJjmMCaWEl5mn5zyJprv2GJL1Tgu1uG3CVoer17NQhZBWKtANrnTuTSftikQLpKdfYonSKUtihfbk-wsKKpkO8mXJ2dTXdDiy3sfIb0dsjJNP27pZ79JCR0RaxLFEoDYVWPVrESg=", "Client-1"),
            
            UltraFastClient(34028019, "fc5342423287695b08996481f2c01b76",
                "1BVtsOKwBu4s8plZhOq40_z-LHs_LpTK2rhfqvjzY5yltX3IPGyryifv3OsPNQvjhKlB4cVezXvyvd7gJIRxZg-HIbys9zAv1TqYeDWpWC4mPqwQ5q5eAUAkmYBMVzvP15AdCVRtVSh6G6eHjvsDZZ7jFQ6CfNM1pgNMI_cJ3DwpeuvMVsZfFIykfL4ig-EtJDhrx_4hubQz-Jt7UWaKgLXRWM-GcVFSIB4VeG5pDb7AHb8LFOY2HI9Nb_o2N7sXCvch-8AdxcdoEhVRLjpkzeli5QAvOw3yYPho8JylMweYXKUnmKArIYTOFfYB7DnAG7p826CbfbyGJKsSwKW4VfUK3oMskETU=", "Client-2"),
            
            UltraFastClient(31262633, "bf9718993cfa858293a1afbbf2e20d3e",
                "1BVtsOKwBu4tf3t5-EsbrQ3mcqegcuxr5HjkVSyjnufLbiwMau4GXx9aaIdaoxedW_sLKapg3mq6W8yQe23sc3hvKVdhxg4cLHCdZus_UUjOCMLx8Ecb_rH9JBaQBg5mCYDa_Y9ZvJUgbzuKYhzDJ8x5g_YyQOnjQW4WrwJ5O48Mu3LhOCwVvvfhxzjVmnv7mDFFNzVGoi4SStvaK3MgVOCkjF_jZF-MjGZlNU633C3ay2VVqoTF9OPO5hvzqB145VKv7IXIWvFaRgfoYO_CHEmRYMv_OMtIpRBFqXmGYCcMqu00fkErhsrRSMvRK2h2KmNUZ2fwSA_797am8eqZHr2B0k1T869g=", "Client-3"),
        ]
        self.message_ids = {}
        self.client_index = 0
    
    async def start_clients(self):
        print("Starting all 3 clients with String Session...")
        for client in self.clients:
            await client.connect()
            await asyncio.sleep(2)

    def extract_all_numbers(self, text: str) -> List[str]:
        clean_text = re.sub(r'[^\d\+\s\(\)\-\.]', '', text)
        numbers = []
        for match in re.findall(r'\+d{10,15}', clean_text):
            d = re.sub(r'\D', '', match)
            if len(d) >= 10: numbers.append(d[-10:])
        for match in re.findall(r'\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}', clean_text):
            d = re.sub(r'\D', '', match)
            if len(d) == 10: numbers.append(d)
            elif len(d) == 11 and d[0]=='1': numbers.append(d[1:])
        for match in re.findall(r'\d{10,11}', clean_text):
            if len(match) == 10: numbers.append(match)
            elif len(match) == 11 and match[0]=='1': numbers.append(match[1:])
        seen = set()
        return [n for n in numbers if len(n)==10 and n not in seen and not seen.add(n)][:50]

    def get_next_client(self):
        for _ in range(len(self.clients)*2):
            c = self.clients[self.client_index]
            if c.can_accept_task():
                self.client_index = (self.client_index + 1) % len(self.clients)
                return c
            self.client_index = (self.client_index + 1) % len(self.clients)
        return None

    async def send_instant(self, client: UltraFastClient, phone: str):
        try:
            await client.client.send_message('@Sellws_bot', f"+1{phone}")
            await asyncio.sleep(1.8)
            msgs = await client.client.get_messages('@Sellws_bot', limit=12)
            for m in msgs:
                if not m.out and (phone in m.message or f"+1{phone}" in m.message):
                    return m.message, m.id
            return None, None
        except Exception as e:
            return str(e), None

    def parse_ultra_fast(self, resp: str):
        if not resp: return "No Response", "Warning"
        t = resp.lower()
        if any(x in t for x in ["already registered", "do not submit it again"]):
            return "Already on WhatsApp", "Warning"
        if any(x in t for x in ["too many attempts", "try again later"]):
            return "Fresh", "Green Circle"
        if any(x in t for x in ["banned", "blocked", "registration blocked"]):
            return "Banned", "Prohibited"
        if any(x in t for x in ["otp verification code has been sent", "please enter the verification code", "6-digit code"]):
            return "OTP Sent", "Exclamation Ws Opened"   
        if any(x in t for x in ["processing", "please wait", "in queue"]):
            return "Processing...", "Blue Circle"
        if "successfully registered" in t or "account created" in t:
            return "Fresh Registered", "Star"
        return "Received", "Inbox"

    async def monitor_ultra_fast(self, client, msg_id, user_id, phone, idx):
        if not msg_id:
            return
        cur = "Sending"
        for _ in range(40):
            await asyncio.sleep(0.5)
            try:
                m = await client.client.get_messages('@Sellws_bot', ids=msg_id)
                if m and m.message:
                    ns, ne = self.parse_ultra_fast(m.message)
                    if ns != cur:
                        cur = ns
                        k = (user_id, phone)
                        if k in self.message_ids:
                            try:
                                await self.bot.edit_message_text(
                                    chat_id=user_id,
                                    message_id=self.message_ids[k],
                                    text=f"{idx}. `{phone}` {ne} {ns}",
                                    parse_mode='Markdown'
                                )
                            except:
                                pass
            except:
                break

    async def process_number_ultra_fast(self, phone: str, idx: int, user_id: int):
        client = self.get_next_client()
        if not client:
            return
        client.start_task()
        try:
            msg = await self.bot.send_message(user_id, f"{idx}. `phone` Sending...", parse_mode='Markdown')
            self.message_ids[(user_id, phone)] = msg.message_id
            resp, rid = await self.send_instant(client, phone)
            status, emoji = self.parse_ultra_fast(resp)
            await self.bot.edit_message_text(
                chat_id=user_id,
                message_id=msg.message_id,
                text=f"{idx}. `phone` {emoji} {status}",
                parse_mode='Markdown'
            )
            if rid and "waiting" not in status.lower():
                asyncio.create_task(self.monitor_ultra_fast(client, rid, user_id, phone, idx))
        except:
            pass
        finally:
            client.end_task()

    async def process_all_ultra_fast(self, nums: List[str], user_id: int):
        if not nums:
            return
        log_check(user_id, len(nums))
        for i, p in enumerate(nums, 1):
            asyncio.create_task(self.process_number_ultra_fast(p, i, user_id))
            await asyncio.sleep(0.001)

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if is_allowed(u.id):
        await update.message.reply_text("Welcome back! Send numbers to check instantly.")
        return
    add_user_request(u.id, u.username, u.first_name)
    kb = [[
        InlineKeyboardButton("Allow", callback_data=f"allow_{u.id}"),
        InlineKeyboardButton("Deny", callback_data=f"deny_{u.id}")
    ]]
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"New Request\nID: <code>{u.id}</code>\nName: {u.full_name}\n@{u.username or 'None'}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='HTML'
        )
    except:
        pass
    await update.message.reply_text("Request sent to admin. Wait for approval.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return
    act, uid = q.data.split("_", 1)
    uid = int(uid)
    set_user_allowed(uid, act == "allow")
    await q.edit_message_text(f"User {uid} → {'ALLOWED' if act=='allow' else 'DENIED'}")
    try:
        await context.bot.send_message(uid, f"You are now {'ALLOWED' if act=='allow' else 'DENIED'}!")
    except:
        pass

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not DB["users"]:
        await update.message.reply_text("No users")
        return
    txt = ["Users List\n\n"]
    btns = []
    for uid, inf in DB["users"].items():
        name = inf.get("first_name","?")
        user = inf.get("username","")
        st = "Allowed" if inf.get("allowed",False) else "Pending"
        txt.append(f"{uid} | {name} @{user or '—'} → {st}\n")
        btns.append([InlineKeyboardButton(f"{st} {uid}", callback_data=f"toggle_{uid}")])
    await update.message.reply_text("".join(txt), reply_markup=InlineKeyboardMarkup(btns))

async def toggle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("Not admin", show_alert=True)
        return
    await q.answer()
    uid = int(q.data.split("_")[1])
    cur = DB["users"].get(str(uid), {}).get("allowed", False)
    set_user_allowed(uid, not cur)
    await q.edit_message_reply_markup(reply_markup=None)
    await q.message.reply_text(f"User {uid} → {'Allowed' if not cur else 'Denied'}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in DB["stats"]:
        await update.message.reply_text("No data yet")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    yest = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"Your Stats\n\n"
        f"Today     → {DB['stats'][uid]['daily'].get(today,0)}\n"
        f"Yesterday → {DB['stats'][uid]['daily'].get(yest,0)}\n"
        f"Total     → {DB['stats'][uid]['total']}"
    )

async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not DB["stats"]:
        await update.message.reply_text("No stats yet")
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    yest = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    lines = ["Admin Full Stats\n\n"]
    
    for uid, data in DB["stats"].items():
        info = DB["users"].get(uid, {})
        name = info.get("first_name", "Unknown")
        user = info.get("username", "")
        t = data["daily"].get(today, 0)
        y = data["daily"].get(yest, 0)
        total = data.get("total", 0)
        lines.append(
            f"{uid} | {name} @{user or '—'}\n"
            f"  Today: {t} | Yest: {y} | Total: {total}\n\n"
        )
    
    text = "".join(lines)
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000])
    else:
        await update.message.reply_text(text)

async def handle_message_ultra_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("Access denied. Send /start")
        return
    text = update.message.text or ""
    bot = context.application.bot_data.get('bot')
    if not bot or not text:
        return
    nums = bot.extract_all_numbers(text)
    if not nums:
        return
    await update.message.reply_text(f"Found {len(nums)} numbers\nStarting Ultra Fast Check...")
    await bot.process_all_ultra_fast(nums, uid)

# ====================== MAIN ======================
async def main():
    TOKEN = "8224615707:AAGXnhaP2JMzf5JAVVW-NMedCZTym2_KuRE"
    bot = UltraFastBot(TOKEN)
    await bot.start_clients()
    
    app = Application.builder().token(TOKEN).build()
    app.bot_data['bot'] = bot

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("adminstats", adminstats))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(allow|deny)_"))
    app.add_handler(CallbackQueryHandler(toggle_user, pattern="^toggle_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_ultra_fast))

    print("ULTRA FAST SELLWS CHECKER 2025 - NO LOGIN - RUNNING")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    while True:
        await asyncio.sleep(3600)

# ====================== Flask for Render ======================
from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "<h1>ULTRA FAST SELLWS BOT 2025 - 100% ALIVE</h1>"

if __name__ == "__main__":
    import threading
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=port), daemon=True).start()
    asyncio.run(main())
