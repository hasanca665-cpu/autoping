import asyncio
import re
import json
import os
from typing import List, Tuple, Dict
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
FRESH_TRACK_FILE = "fresh_track.json"
DAILY_STATS_FILE = "daily_stats.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            if "users" not in data:
                data["users"] = {}
            if "stats" not in data:
                data["stats"] = {}
            
            for uid in data["stats"]:
                stats = data["stats"][uid]
                if "daily" not in stats:
                    stats["daily"] = {}
                if "total" not in stats:
                    stats["total"] = 0
                if "total_fresh_found" not in stats:
                    stats["total_fresh_found"] = 0
                if "total_fresh_used" not in stats:
                    stats["total_fresh_used"] = 0
                if "fresh_found_daily" not in stats:
                    stats["fresh_found_daily"] = {}
                if "fresh_used_daily" not in stats:
                    stats["fresh_used_daily"] = {}
            
            return data
    return {"users": {}, "stats": {}}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(DB, f, indent=4)

def load_fresh_track():
    if os.path.exists(FRESH_TRACK_FILE):
        with open(FRESH_TRACK_FILE, "r") as f:
            return json.load(f)
    return {"fresh_numbers": {}, "message_tracking": {}}

def save_fresh_track():
    with open(FRESH_TRACK_FILE, "w") as f:
        json.dump(FRESH_TRACK, f, indent=4)

def load_daily_stats():
    if os.path.exists(DAILY_STATS_FILE):
        with open(DAILY_STATS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_daily_stats():
    with open(DAILY_STATS_FILE, "w") as f:
        json.dump(DAILY_STATS, f, indent=4)

DB = load_db()
FRESH_TRACK = load_fresh_track()
DAILY_STATS = load_daily_stats()

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

def log_check(user_id: int, total_checked: int = 1, fresh_found_in_msg: int = 0, fresh_used_in_msg: int = 0):
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if uid not in DB["stats"]:
        DB["stats"][uid] = {
            "daily": {},
            "total": 0,
            "total_fresh_found": 0,
            "total_fresh_used": 0,
            "fresh_found_daily": {},
            "fresh_used_daily": {}
        }
    
    stats = DB["stats"][uid]
    
    stats["daily"][today] = stats["daily"].get(today, 0) + total_checked
    stats["total"] = stats.get("total", 0) + total_checked
    
    stats["fresh_found_daily"][today] = stats["fresh_found_daily"].get(today, 0) + fresh_found_in_msg
    stats["total_fresh_found"] = stats.get("total_fresh_found", 0) + fresh_found_in_msg
    
    stats["fresh_used_daily"][today] = stats["fresh_used_daily"].get(today, 0) + fresh_used_in_msg
    stats["total_fresh_used"] = stats.get("total_fresh_used", 0) + fresh_used_in_msg
    
    save_db()

def escape_markdown_v2(text: str) -> str:
    """Escape reserved MarkdownV2 characters except inside code blocks"""
    reserved = r'_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + c if c in reserved else c for c in text])

class UltraFastClient:
    def __init__(self, api_id: int, api_hash: str, session_string: str, name: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.name = name
        self.client = TelegramClient(StringSession(session_string), api_id, api_hash)
        self.active_tasks = 0
        self.max_tasks = 10
    
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
        self.number_status_cache = {}
        self.scheduler = AsyncIOScheduler()
        self.processing_messages = {}
        
        sessions = [
            (API_ID_1, API_HASH_1, SESSION_1, "Client-1"),
            (API_ID_2, API_HASH_2, SESSION_2, "Client-2"),
            (API_ID_3, API_HASH_3, SESSION_3, "Client-3"),
            (API_ID_4, API_HASH_4, SESSION_4, "Client-4")
        ]
        
        for idx, (api_id, api_hash, session_str, name) in enumerate(sessions, 1):
            if session_str and session_str.strip():
                self.clients.append(UltraFastClient(api_id, api_hash, session_str, name))
                print(f"Loaded {name}")
            else:
                print(f"Warning: {name} session string not found")
    
    async def start_clients(self):
        if not self.clients:
            print("No clients available. Please set SESSION environment variables.")
            return
        
        print(f"Starting {len(self.clients)} clients with String Session...")
        for client in self.clients:
            await client.connect()
            await asyncio.sleep(0.5)

    def extract_all_numbers(self, text: str) -> List[str]:
        no_space = re.sub(r'\s+', '', text)
        numbers = []
        
        numbers.extend(re.findall(r'\d{10}', no_space))
        
        formatted = re.findall(r'\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}', text)
        for match in formatted:
            digits = re.sub(r'\D', '', match)
            if len(digits) == 10:
                numbers.append(digits)
            elif len(digits) == 11 and digits.startswith('1'):
                numbers.append(digits[1:])
        
        parenthesis = re.findall(r'\(\d{3}\)\s*\d{3}[-\s]?\d{4}', text)
        for match in parenthesis:
            digits = re.sub(r'\D', '', match)
            if len(digits) == 10:
                numbers.append(digits)
        
        us_prefix = re.findall(r'1[-\s(]?\d{3}[-\s)]?\d{3}[-\s]?\d{4}', text)
        for match in us_prefix:
            digits = re.sub(r'\D', '', match)
            if len(digits) == 11 and digits.startswith('1'):
                numbers.append(digits[1:])
            elif len(digits) == 10:
                numbers.append(digits)
        
        seen = set()
        unique = []
        for n in numbers:
            if n not in seen and len(n) == 10:
                seen.add(n)
                unique.append(n)
        
        return unique[:100]

    def get_next_client(self):
        if not self.clients:
            return None
        
        for _ in range(len(self.clients) * 2):
            c = self.clients[self.client_index]
            if c.can_accept_task():
                self.client_index = (self.client_index + 1) % len(self.clients)
                return c
            self.client_index = (self.client_index + 1) % len(self.clients)
        
        return min(self.clients, key=lambda x: x.active_tasks) if self.clients else None

    async def send_instant(self, client: UltraFastClient, phone: str) -> Tuple[str, int]:
        try:
            sent = await client.client.send_message('@Sellws_bot', f"+1{phone}")
            await asyncio.sleep(0.8)
            msgs = await client.client.get_messages('@Sellws_bot', limit=10, min_id=sent.id - 5)
            for m in reversed(msgs):
                if not m.out and (phone in m.message or f"+1{phone}" in m.message):
                    return m.message, m.id
            return None, None
        except FloodWaitError as e:
            print(f"Flood wait for {phone}: {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
            return await self.send_instant(client, phone)
        except Exception as e:
            print(f"Send error {phone}: {e}")
            return str(e), None

    def parse_ultra_fast(self, resp: str) -> Tuple[str, str]:
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

    async def send_status_message(self, chat_id: int, phone: str, idx: int, status: str, emoji: str):
        idx_str = escape_markdown_v2(f"{idx}.")
        status_str = escape_markdown_v2(status)
        message = f"{idx_str} `{phone}` {emoji} {status_str}"
        try:
            msg = await self.bot.send_message(chat_id, message, parse_mode='MarkdownV2')
            return msg.message_id
        except Exception as e:
            print("MarkdownV2 send failed:", e)
            plain = f"{idx}. {phone} {emoji} {status}"
            msg = await self.bot.send_message(chat_id, plain)
            return msg.message_id

    async def edit_status_message(self, chat_id: int, message_id: int, phone: str, idx: int, status: str, emoji: str):
        idx_str = escape_markdown_v2(f"{idx}.")
        status_str = escape_markdown_v2(status)
        message = f"{idx_str} `{phone}` {emoji} {status_str}"
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            print("MarkdownV2 edit failed:", e)
            try:
                plain = f"{idx}. {phone} {emoji} {status}"
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=plain
                )
            except:
                pass

    async def monitor_ultra_fast(self, client: UltraFastClient, msg_id: int, user_id: int, 
                                 phone: str, idx: int, final_statuses: Dict, start_msg_id: int):
        if not msg_id:
            return
        
        cur_status = "Sending"
        
        for _ in range(50):  # reduced loops
            await asyncio.sleep(0.4)  # faster polling
            
            try:
                m = await client.client.get_messages('@Sellws_bot', ids=msg_id)
                if m and m.message:
                    new_status, emoji = self.parse_ultra_fast(m.message)
                    
                    if new_status != cur_status:
                        cur_status = new_status
                        await self.edit_status_message(user_id, start_msg_id, phone, idx, cur_status, emoji)
                        
                        final_statuses[phone] = {
                            "status": cur_status,
                            "emoji": emoji,
                            "is_fresh": (cur_status == "Fresh Num"),
                            "updated_at": datetime.now().isoformat()
                        }
                        
                        if cur_status not in ["Processing", "Sending", "Unknown"]:
                            await asyncio.sleep(2.5)
                            break
            except:
                break
        
        if phone in final_statuses:
            self.number_status_cache[phone] = final_statuses[phone]

    async def process_single_number(self, phone: str, idx: int, user_id: int, 
                                   final_statuses: Dict, semaphore: asyncio.Semaphore) -> Tuple[bool, str]:
        async with semaphore:
            client = self.get_next_client()
            if not client:
                return False, "No Client"
            
            client.start_task()
            try:
                msg_id = await self.send_status_message(user_id, phone, idx, "Sending", "📤")
                if not msg_id:
                    return False, "Send failed"
                
                self.message_ids[(user_id, phone)] = msg_id
                
                resp, resp_id = await self.send_instant(client, phone)
                initial_status, emoji = self.parse_ultra_fast(resp)
                
                await self.edit_status_message(user_id, msg_id, phone, idx, initial_status, emoji)
                
                final_statuses[phone] = {
                    "status": initial_status,
                    "emoji": emoji,
                    "is_fresh": (initial_status == "Fresh Num"),
                    "updated_at": datetime.now().isoformat()
                }
                
                if resp_id:
                    asyncio.create_task(
                        self.monitor_ultra_fast(client, resp_id, user_id, phone, idx, final_statuses, msg_id)
                    )
                
                await asyncio.sleep(12)  # reduced from 20s
                
                if phone in final_statuses:
                    info = final_statuses[phone]
                    await self.edit_status_message(user_id, msg_id, phone, idx, info["status"], info["emoji"])
                    return info["is_fresh"], info["status"]
                
                return (initial_status == "Fresh Num"), initial_status
                
            except FloodWaitError as e:
                print(f"Flood in processing {phone}: waiting {e.seconds}s")
                await asyncio.sleep(e.seconds + 3)
                return False, "Flood Wait"
            except Exception as e:
                print(f"Process error {phone}: {e}")
                try:
                    await self.edit_status_message(user_id, msg_id, phone, idx, "Error", "❌")
                except:
                    pass
                return False, "Error"
            finally:
                client.end_task()

    async def process_all_ultra_fast(self, nums: List[str], user_id: int):
        if not nums:
            return
        
        if not self.clients:
            await self.bot.send_message(user_id, "No Telegram clients available.")
            return
        
        message_track_id = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        final_statuses = {}
        
        initial_msg = await self.bot.send_message(
            user_id,
            f"⚡ Checking `{len(nums)}` numbers...",
            parse_mode='Markdown'
        )
        
        semaphore = asyncio.Semaphore(min(40, len(nums)))  # increased concurrency
        
        tasks = []
        for i, phone in enumerate(nums, 1):
            task = asyncio.create_task(
                self.process_single_number(phone, i, user_id, final_statuses, semaphore)
            )
            tasks.append((phone, task))
            await asyncio.sleep(0.03)  # faster task creation
        
        results = []
        for phone, task in tasks:
            try:
                is_fresh, status = await asyncio.wait_for(task, timeout=18)
                results.append((phone, is_fresh, status))
            except asyncio.TimeoutError:
                if phone in self.number_status_cache:
                    si = self.number_status_cache[phone]
                    results.append((phone, si["is_fresh"], si["status"]))
                else:
                    results.append((phone, False, "Timeout"))
            except:
                results.append((phone, False, "Error"))
        
        try:
            await self.bot.delete_message(user_id, initial_msg.message_id)
        except:
            pass
        
        fresh_found = sum(1 for _, is_fresh, _ in results if is_fresh)
        fresh_used = min(1, fresh_found)
        
        if message_track_id not in FRESH_TRACK["message_tracking"]:
            FRESH_TRACK["message_tracking"][message_track_id] = {
                "user_id": user_id,
                "total_numbers": len(nums),
                "fresh_found": 0,
                "fresh_used": 0,
                "numbers": []
            }
        
        for phone, is_fresh, status in results:
            used = (is_fresh and fresh_used > 0)
            if used:
                fresh_used -= 1
            
            FRESH_TRACK["message_tracking"][message_track_id]["numbers"].append({
                "phone": phone,
                "status": status,
                "is_fresh": is_fresh,
                "used": used
            })
            
            if is_fresh:
                FRESH_TRACK["message_tracking"][message_track_id]["fresh_found"] += 1
                if used:
                    FRESH_TRACK["message_tracking"][message_track_id]["fresh_used"] += 1
                
                FRESH_TRACK["fresh_numbers"][phone] = {
                    "user_id": user_id,
                    "found_at": datetime.now().isoformat(),
                    "message_id": message_track_id,
                    "used": used
                }
        
        log_check(user_id,
                 total_checked=len(nums),
                 fresh_found_in_msg=sum(1 for _, is_fresh, _ in results if is_fresh),
                 fresh_used_in_msg=min(1, sum(1 for _, is_fresh, _ in results if is_fresh)))
        
        save_fresh_track()
        
        status_counts = {}
        for _, _, status in results:
            status_counts[status] = status_counts.get(status, 0) + 1
        
        status_emojis = {
            "Fresh Num": "🟢",
            "Banned": "🚫", 
            "Ws Opened": "💩",
            "Processing": "🔵",
            "Registered": "⭐",
            "Try Later": "🟡",
            "Already Checked": "⚠️",
            "No Response": "📭",
            "Unknown": "❓",
            "Error": "❌",
            "Timeout": "⏱️"
        }
        
        
        
        await self.bot.send_message(user_id, report_msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if is_allowed(u.id):
        await update.message.reply_text(
            "⚡ Welcome back! Send numbers to check.\n\n"
            "Examples that work:\n"
            "3069921959\n"
            "(306) 992-1959\n"
            "(306)9921959\n"
            "1-306-992-1959",
            parse_mode='Markdown'
        )
        return
    
    add_user_request(u.id, u.username, u.first_name)
    kb = [[
        InlineKeyboardButton("✅ Allow", callback_data=f"allow_{u.id}"),
        InlineKeyboardButton("❌ Deny", callback_data=f"deny_{u.id}")
    ]]
    
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"📨 **New Request**\n👤 ID: `{u.id}`\n📛 Name: {u.full_name}\n🔗 @{u.username or 'None'}",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode='Markdown'
        )
    except:
        pass
    
    await update.message.reply_text("📩 Request sent to admin @Notfound_errorx")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return
    
    act, uid = q.data.split("_", 1)
    uid = int(uid)
    set_user_allowed(uid, act == "allow")
    
    await q.edit_message_text(
        f"👤 User `{uid}` → **{'✅ ALLOWED' if act == 'allow' else '❌ DENIED'}**",
        parse_mode='Markdown'
    )
    
    try:
        await context.bot.send_message(
            uid, 
            f"🔓 You are now **{'✅ ALLOWED' if act == 'allow' else '❌ DENIED'}**!"
        )
    except:
        pass

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not DB["users"]:
        await update.message.reply_text("📭 No users")
        return
    
    txt = ["👥 **Users List**\n\n"]
    btns = []
    
    for uid, inf in DB["users"].items():
        name = inf.get("first_name", "?")
        user = inf.get("username", "")
        st = "✅" if inf.get("allowed", False) else "⏳"
        txt.append(f"`{uid}` | {name} @{user or '—'} → {st}\n")
        btns.append([InlineKeyboardButton(f"{st} {uid[:6]}...", callback_data=f"toggle_{uid}")])
    
    await update.message.reply_text(
        "".join(txt),
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode='Markdown'
    )

async def toggle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("❌ Not admin", show_alert=True)
        return
    
    await q.answer()
    uid = int(q.data.split("_")[1])
    cur = DB["users"].get(str(uid), {}).get("allowed", False)
    set_user_allowed(uid, not cur)
    
    await q.edit_message_reply_markup(reply_markup=None)
    await q.message.reply_text(f"👤 User `{uid}` → **{'✅ Allowed' if not cur else '❌ Denied'}**",
                               parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    
    if uid not in DB["stats"]:
        DB["stats"][uid] = {
            "daily": {},
            "total": 0,
            "total_fresh_found": 0,
            "total_fresh_used": 0,
            "fresh_found_daily": {},
            "fresh_used_daily": {}
        }
        save_db()
    
    stats_data = DB["stats"][uid]
    today = datetime.now().strftime("%Y-%m-%d")
    yest = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    response = f"""
📊 **Your Stats**

📅 Today: `{stats_data.get('daily', {}).get(today, 0)}`
📅 Yesterday: `{stats_data.get('daily', {}).get(yest, 0)}`
✅ Total Checked: `{stats_data.get('total', 0)}`
🟢 Fresh Found: `{stats_data.get('total_fresh_found', 0)}`
⭐ Fresh Used: `{stats_data.get('total_fresh_used', 0)}`
"""
    await update.message.reply_text(response, parse_mode='Markdown')

async def send_large_message(chat_id: int, text: str, bot: Bot):
    if len(text) <= 4000:
        await bot.send_message(chat_id, text)
        return
    
    sections = []
    current = ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 < 3900:
            current += line + '\n'
        else:
            sections.append(current)
            current = line + '\n'
    if current:
        sections.append(current)
    
    for i, sec in enumerate(sections, 1):
        header = f"**Part {i}/{len(sections)}**\n\n" if len(sections) > 1 else ""
        await bot.send_message(chat_id, header + sec)
        await asyncio.sleep(0.4)

async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not DB["users"]:
        await update.message.reply_text("📭 No users in database")
        return
    
    total_users = len(DB["users"])
    total_checked_all = 0
    total_fresh_found_all = 0
    total_fresh_used_all = 0
    allowed_users = 0
    active_users = 0
    
    reports = []
    
    for uid, user_info in DB["users"].items():
        user_stats = DB["stats"].get(uid, {})
        
        total_checked = user_stats.get("total", 0)
        if total_checked > 0:
            active_users += 1
        
        if user_info.get("allowed", False):
            allowed_users += 1
        
        username = user_info.get("username", "") or "no_username"
        first_name = user_info.get("first_name", "Unknown")
        status = "✅ ALLOWED" if user_info.get("allowed", False) else "⏳ PENDING"
        registered = user_info.get("requested_at", "").split("T")[0] if user_info.get("requested_at") else "N/A"
        
        total_fresh_found = user_stats.get("total_fresh_found", 0)
        total_fresh_used = user_stats.get("total_fresh_used", 0)
        fresh_skipped = max(0, total_fresh_found - total_fresh_used)
        
        total_checked_all += total_checked
        total_fresh_found_all += total_fresh_found
        total_fresh_used_all += total_fresh_used
        
        if total_checked > 0:
            user_report = f"""
👤 USER: {first_name} (@{username})
🆔 ID: {uid}
📅 Registered: {registered}
🔐 Status: {status}

📊 STATS:
Checked: {total_checked}
Fresh Found: {total_fresh_found}
Fresh Used: {total_fresh_used}
Fresh Skipped: {fresh_skipped}
"""
            
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            daily_stats = user_stats.get("daily", {})
            fresh_found_daily = user_stats.get("fresh_found_daily", {})
            fresh_used_daily = user_stats.get("fresh_used_daily", {})
            
            activity_today = daily_stats.get(today, 0)
            fresh_today = fresh_found_daily.get(today, 0)
            used_today = fresh_used_daily.get(today, 0)
            
            activity_yesterday = daily_stats.get(yesterday, 0)
            fresh_yesterday = fresh_found_daily.get(yesterday, 0)
            used_yesterday = fresh_used_daily.get(yesterday, 0)
            
            if activity_today > 0 or activity_yesterday > 0:
                user_report += f"\n📈 ACTIVITY:\n"
                if activity_today > 0:
                    user_report += f"Today: Checked {activity_today}, Fresh {fresh_today}, Used {used_today}\n"
                if activity_yesterday > 0:
                    user_report += f"Yesterday: Checked {activity_yesterday}, Fresh {fresh_yesterday}, Used {used_yesterday}\n"
            
            user_report += "-" * 50 + "\n"
            reports.append(user_report)
    
    utilization_rate = (total_fresh_used_all / total_fresh_found_all * 100) if total_fresh_found_all > 0 else 0
    
    system_summary = f"""
📊 SYSTEM SUMMARY
{'='*50}
👥 Total Users: {total_users}
⚡ Active Users: {active_users}
✅ Allowed Users: {allowed_users}

🔢 Total Numbers Checked: {total_checked_all}
🟢 Total Fresh Found: {total_fresh_found_all}
⭐ Total Fresh Used: {total_fresh_used_all}
📭 Total Fresh Skipped: {total_fresh_found_all - total_fresh_used_all}
📈 Fresh Utilization Rate: {utilization_rate:.1f}%
"""
    
    if reports:
        final_report = "📊 ADMIN STATS REPORT\n"
        final_report += "=" * 50 + "\n\n"
        final_report += "\n".join(reports)
        final_report += system_summary
    else:
        final_report = "📭 No active users found.\n" + system_summary
    
    bot = context.bot
    await send_large_message(update.effective_chat.id, final_report, bot)

async def handle_message_ultra_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("❌ Access denied. Send /start or contact Admin @Notfound_errorx")
        return
    
    text = update.message.text or ""
    bot = context.application.bot_data.get('bot')
    if not bot or not text:
        return
    
    nums = bot.extract_all_numbers(text)
    if not nums:
        await update.message.reply_text("📭 No valid 10-digit numbers found.\n\nExamples:\n3069921959\n(306) 992-1959\n(306)9921959\n1-306-992-1959")
        return
    
    asyncio.create_task(bot.process_all_ultra_fast(nums, uid))

async def send_daily_stats():
    try:
        now_bd = datetime.utcnow() + timedelta(hours=6)
        
        if now_bd.hour == 16 and now_bd.minute <= 5:
            today = now_bd.strftime("%Y-%m-%d")
            
            daily_checked = 0
            daily_fresh_found = 0
            daily_fresh_used = 0
            
            for uid, user_stats in DB["stats"].items():
                daily_checked += user_stats.get("daily", {}).get(today, 0)
                daily_fresh_found += user_stats.get("fresh_found_daily", {}).get(today, 0)
                daily_fresh_used += user_stats.get("fresh_used_daily", {}).get(today, 0)
            
            stats_msg = f"📊 **Daily Activity Report – {today}** (4:00 PM BD)\n\n"
            stats_msg += f"Numbers Checked  : {daily_checked}\n"
            stats_msg += f"Fresh Found      : {daily_fresh_found}\n"
            stats_msg += f"Fresh Used       : {daily_fresh_used}\n"
            stats_msg += f"Fresh Skipped    : {max(0, daily_fresh_found - daily_fresh_used)}\n"
            
            DAILY_STATS[today] = {
                "checked": daily_checked,
                "fresh_found": daily_fresh_found,
                "fresh_used": daily_fresh_used,
                "timestamp": now_bd.isoformat()
            }
            save_daily_stats()
            
            bot_instance = UltraFastBot(BOT_TOKEN)
            await bot_instance.bot.send_message(ADMIN_ID, stats_msg)
            
            print(f"Daily stats sent at BD time: {now_bd.strftime('%H:%M:%S')}")
    
    except Exception as e:
        print(f"Daily stats error: {e}")

async def main():
    bot = UltraFastBot(BOT_TOKEN)
    await bot.start_clients()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_stats, 'interval', minutes=1)
    scheduler.start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.bot_data['bot'] = bot

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("adminstats", adminstats))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(allow|deny)_"))
    app.add_handler(CallbackQueryHandler(toggle_user, pattern="^toggle_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_ultra_fast))

    print("⚡ ULTRA FAST SELLWS CHECKER 2025 - FIXED VERSION - RUNNING")
    print(f"🇧🇩 BD Time: {(datetime.utcnow() + timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S')}")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    while True:
        await asyncio.sleep(3600)

from flask import Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    bangladesh_time = datetime.utcnow() + timedelta(hours=6)
    return f"""
    <h1>⚡ ULTRA FAST SELLWS BOT 2025 - FIXED</h1>
    <p>🇧🇩 BD Time: {bangladesh_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Status: <span style="color: green; font-weight: bold;">● ONLINE</span></p>
    """

if __name__ == "__main__":
    import threading
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=port), daemon=True).start()
    asyncio.run(main())
