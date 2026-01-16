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


API_ID_1 = int(os.environ.get("API_ID_1", ""))
API_HASH_1 = os.environ.get("API_HASH_1", "")
SESSION_1 = os.environ.get("SESSION_1", "")

API_ID_2 = int(os.environ.get("API_ID_2", ""))
API_HASH_2 = os.environ.get("API_HASH_2", "")
SESSION_2 = os.environ.get("SESSION_2", "")

API_ID_3 = int(os.environ.get("API_ID_3", ""))
API_HASH_3 = os.environ.get("API_HASH_3", "")
SESSION_3 = os.environ.get("SESSION_3", "")

API_ID_4 = int(os.environ.get("API_ID_4", ""))
API_HASH_4 = os.environ.get("API_HASH_4", "")
SESSION_4 = os.environ.get("SESSION_4", "")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", ""))

DB_FILE = "user_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "stats": {}}

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            # পুরোনো ডাটা কম্প্যাটিবিলিটির জন্য
            if "stats" in data:
                for uid, stats in data["stats"].items():
                    if "total_checked" not in stats:
                        stats["total_checked"] = stats.get("total", 0)
                    if "total_fresh" not in stats:
                        stats["total_fresh"] = 0
                    if "total_fresh_used" not in stats:
                        stats["total_fresh_used"] = 0
                    if "fresh_daily" not in stats:
                        stats["fresh_daily"] = {}
                    if "fresh_used_daily" not in stats:
                        stats["fresh_used_daily"] = {}
            return data
    return {"users": {}, "stats": {}}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(DB, f, indent=4)

DB = load_db()

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

def log_check(user_id: int, total_checked: int = 1, fresh_found: int = 0, fresh_used: int = 0):
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if uid not in DB["stats"]:
        DB["stats"][uid] = {
            "daily": {},
            "total": 0,
            "total_checked": 0,
            "total_fresh": 0,
            "total_fresh_used": 0,
            "fresh_daily": {},
            "fresh_used_daily": {}
        }
    
    # মোট চেক সংখ্যা আপডেট
    DB["stats"][uid]["daily"][today] = DB["stats"][uid]["daily"].get(today, 0) + total_checked
    DB["stats"][uid]["total"] = DB["stats"][uid].get("total", 0) + total_checked
    DB["stats"][uid]["total_checked"] = DB["stats"][uid].get("total_checked", 0) + total_checked
    
    # ফ্রেশ সংখ্যা আপডেট
    DB["stats"][uid]["fresh_daily"][today] = DB["stats"][uid]["fresh_daily"].get(today, 0) + fresh_found
    DB["stats"][uid]["total_fresh"] = DB["stats"][uid].get("total_fresh", 0) + fresh_found
    
    # ব্যবহৃত ফ্রেশ সংখ্যা আপডেট
    DB["stats"][uid]["fresh_used_daily"][today] = DB["stats"][uid]["fresh_used_daily"].get(today, 0) + fresh_used
    DB["stats"][uid]["total_fresh_used"] = DB["stats"][uid].get("total_fresh_used", 0) + fresh_used
    
    save_db()

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
        self.clients = []
        self.message_ids = {}
        self.client_index = 0
        
        
        sessions = [
            (API_ID_1, API_HASH_1, SESSION_1, "Client-1"),
            (API_ID_2, API_HASH_2, SESSION_2, "Client-2"),
            (API_ID_3, API_HASH_3, SESSION_3, "Client-3"),
            (API_ID_4, API_HASH_4, SESSION_4, "Client-4")
        ]
        
        for idx, (api_id, api_hash, session_str, name) in enumerate(sessions, 1):
            if session_str and session_str.strip():  # শুধুমাত্র যদি session string থাকে
                self.clients.append(UltraFastClient(api_id, api_hash, session_str, name))
                print(f"Loaded {name}")
            else:
                print(f"Warning: {name} session string not found in environment variables")
    
    async def start_clients(self):
        if not self.clients:
            print("No clients available. Please set SESSION environment variables.")
            return
        
        print(f"Starting {len(self.clients)} clients with String Session...")
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
        if not self.clients:
            return None
            
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
            await asyncio.sleep(3.5)
            msgs = await client.client.get_messages('@Sellws_bot', limit=30)
            for m in msgs:
                if not m.out and (phone in m.message or f"+1{phone}" in m.message):
                    return m.message, m.id
            return None, None
        except Exception as e:
            return str(e), None

    def parse_ultra_fast(self, resp: str):
        if not resp:
            return "No Response", "⚠️"
        
        resp_lower = resp.lower()
        
        if "too many attempts for this number" in resp_lower:
            return "Fresh Num", "🟢"
        
        if "already registered" in resp_lower or "do not submit it again" in resp_lower:
            return "Already Checked", "⚠️"
        
        if "banned" in resp_lower or "blocked" in resp_lower:
            return "Banned", "🚫"
        
        if "otp" in resp_lower or "verification code" in resp_lower or "6-digit" in resp_lower:
            return "Ws Opened", "💩"
        
        if "processing" in resp_lower or "please wait" in resp_lower:
            return "Processing", "🔵"
        
        if "successfully" in resp_lower or "account created" in resp_lower:
            return "Registered", "⭐"
        
        if "try again later" in resp_lower:
            return "Try Later", "🟡"
        
        return "Unknown", "📥"

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
            await self.bot.send_message(user_id, "No active clients available.")
            return
        client.start_task()
        try:
            msg = await self.bot.send_message(user_id, f"{idx}. `{phone}` Sending...", parse_mode='Markdown')
            self.message_ids[(user_id, phone)] = msg.message_id
            resp, rid = await self.send_instant(client, phone)
            status, emoji = self.parse_ultra_fast(resp)
            await self.bot.edit_message_text(
                chat_id=user_id,
                message_id=msg.message_id,
                text=f"{idx}. `{phone}` {emoji} {status}",
                parse_mode='Markdown'
            )
            if rid and "waiting" not in status.lower():
                asyncio.create_task(self.monitor_ultra_fast(client, rid, user_id, phone, idx))
        except Exception as e:
            print(f"Error processing {phone}: {e}")
        finally:
            client.end_task()

    async def process_all_ultra_fast(self, nums: List[str], user_id: int):
        if not nums:
            return
        if not self.clients:
            await self.bot.send_message(user_id, "No Telegram clients available. Please check session strings.")
            return
            
        log_check(user_id, len(nums))
        for i, p in enumerate(nums, 1):
            asyncio.create_task(self.process_number_ultra_fast(p, i, user_id))
            await asyncio.sleep(0.001)

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
    await update.message.reply_text("Request sent to admin @Notfound_errorx")

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
    
    if not DB["users"]:
        await update.message.reply_text("No users in database")
        return
    
    # সিস্টেম সামারি হিসাব
    total_users = len(DB["users"])
    total_checked_all = 0
    total_fresh_all = 0
    total_fresh_used_all = 0
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # প্রতিটি ইউজারের জন্য ডিটেইল্ড রিপোর্ট তৈরি
    reports = []
    
    for uid, user_info in DB["users"].items():
        # ইউজার ইনফো
        user_id = uid
        username = user_info.get("username", "")
        first_name = user_info.get("first_name", "Unknown")
        status = "✅ Allowed" if user_info.get("allowed", False) else "⏳ Pending"
        registered = user_info.get("requested_at", "").split("T")[0] if user_info.get("requested_at") else "N/A"
        
        # স্ট্যাটস ইনফো
        user_stats = DB["stats"].get(uid, {})
        total_checked = user_stats.get("total", 0)
        total_fresh = user_stats.get("total_fresh", 0)
        total_fresh_used = user_stats.get("total_fresh_used", 0)
        fresh_skipped = max(0, total_fresh - total_fresh_used)
        
        # ডেইলি অ্যাক্টিভিটি
        daily_stats = user_stats.get("daily", {})
        fresh_daily = user_stats.get("fresh_daily", {})
        fresh_used_daily = user_stats.get("fresh_used_daily", {})
        
        # সামারি যোগ
        total_checked_all += total_checked
        total_fresh_all += total_fresh
        total_fresh_used_all += total_fresh_used
        
        # ডেইলি ব্রেকডাউন (শেষ ৩ দিন)
        daily_breakdown = []
        for i in range(3):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            checked = daily_stats.get(date, 0)
            fresh = fresh_daily.get(date, 0)
            fresh_used = fresh_used_daily.get(date, 0)
            
            if checked > 0 or fresh > 0:
                daily_breakdown.append(f"{date}: ✓{checked} | 🟢{fresh} | ✅{fresh_used}")
        
        # ইউজার রিপোর্ট তৈরি
        user_report = f"""
👤 **User:** {first_name} (@{username if username else 'no_username'})
🆔 **ID:** {user_id}
📅 **Registered:** {registered}
✅ **Status:** {status}

📞 **Number Statistics:**
├── Total Checked: {total_checked}
├── Fresh Found: {total_fresh}
├── Fresh Used: {total_fresh_used}
└── Fresh Skipped: {fresh_skipped}

"""
        
        # ডেইলি অ্যাক্টিভিটি যোগ
        if daily_breakdown:
            user_report += "📅 **Recent Activity:**\n"
            for day in daily_breakdown:
                user_report += f"├── {day}\n"
            user_report += "└──\n"
        
        user_report += "─" * 40
        reports.append(user_report)
    
    # সিস্টেম সামারি
    utilization_rate = (total_fresh_used_all / total_fresh_all * 100) if total_fresh_all > 0 else 0
    avg_fresh_per_user = total_fresh_all / total_users if total_users > 0 else 0
    
    system_summary = f"""
📈 **SYSTEM SUMMARY:**
• Total Users: {total_users}
• Total Numbers Checked: {total_checked_all}
• Total Fresh Found: {total_fresh_all}
• Total Fresh Used: {total_fresh_used_all}
• Fresh Utilization Rate: {utilization_rate:.1f}%
• Avg Fresh per User: {avg_fresh_per_user:.1f}
"""
    
    # সব রিপোর্ট একত্রিত করা
    final_report = "📊 **ADMIN STATS - Detailed Report**\n"
    final_report += "─" * 40 + "\n\n"
    
    for report in reports:
        final_report += report + "\n"
    
    final_report += "\n" + system_summary
    
    # টেলিগ্রাম মেসেজ লিমিট (4096 characters)
    if len(final_report) > 4000:
        # প্রথম অংশ
        await update.message.reply_text(final_report[:4000], parse_mode='Markdown')
        # দ্বিতীয় অংশ (যদি থাকে)
        if len(final_report) > 4000:
            await update.message.reply_text(final_report[4000:], parse_mode='Markdown')
    else:
        await update.message.reply_text(final_report, parse_mode='Markdown')

async def handle_message_ultra_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("Access denied. Send /start or contact Admin @Notfound_errorx")
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

async def main():
    bot = UltraFastBot(BOT_TOKEN)
    await bot.start_clients()
    
    app = Application.builder().token(BOT_TOKEN).build()
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
