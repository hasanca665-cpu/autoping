# universal_project_manager.py
import asyncio
import aiohttp
import logging
import json
import os
import socket
from datetime import datetime
from urllib.parse import urlparse
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# ====================== FORCE IPv4 & DNS FIX ======================
original_getaddrinfo = socket.getaddrinfo
def force_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = force_ipv4_getaddrinfo
# =================================================================

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8174798097:AAG38ZYHaAflW6z83h2KXqhHVrhJ3rnbnS0"
ADMIN_ID = 5624278091

PROJECTS_FILE = "projects.json"
STATS_FILE = "project_stats.json"

class ProjectManager:
    def __init__(self):
        self.projects = self.load_projects()
        self.stats = self.load_stats()
        self.is_running = False

    def load_projects(self):
        try:
            if os.path.exists(PROJECTS_FILE):
                with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            return []
        except Exception as e:
            logger.error(f"Load error: {e}")
            return []

    def save_projects(self):
        try:
            with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Save error: {e}")

    def load_stats(self):
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            return {}
        except Exception as e:
            logger.error(f"Stats load error: {e}")
            return {}

    def save_stats(self):
        try:
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Stats save error: {e}")

    def add_project(self, name, url, category="General"):
        try:
            ids = [int(p["id"]) for p in self.projects if p["id"].isdigit()]
            pid = str(max(ids) + 1) if ids else "1"
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            project = {
                "id": pid, "name": name, "url": url, "category": category,
                "active": True, "created_at": datetime.now().isoformat(),
                "last_ping": None, "status": "Checking..."
            }
            self.projects.append(project)
            self.stats[pid] = {
                "total_pings": 0, "successful_pings": 0, "failed_pings": 0,
                "uptime_percentage": 0, "last_status": "Checking..."
            }
            self.save_projects()
            self.save_stats()
            return pid
        except Exception as e:
            logger.error(f"Add error: {e}")
            return None

    def remove_project(self, pid):
        self.projects = [p for p in self.projects if p["id"] != pid]
        self.stats.pop(pid, None)
        self.save_projects()
        self.save_stats()

    def toggle_project(self, pid):
        for p in self.projects:
            if p["id"] == pid:
                p["active"] = not p["active"]
                self.save_projects()
                return p["active"]
        return None

    def activate_all(self):
        for p in self.projects: p["active"] = True
        self.save_projects()
        return len(self.projects)

    def deactivate_all(self):
        for p in self.projects: p["active"] = False
        self.save_projects()
        return len(self.projects)

    def get_project(self, pid):
        for p in self.projects:
            if p["id"] == pid: return p
        return None

    def update_project_status(self, pid, status, success=True):
        for p in self.projects:
            if p["id"] == pid:
                p["status"] = status
                p["last_ping"] = datetime.now().isoformat()
                break
        s = self.stats.get(pid, {})
        s["total_pings"] = s.get("total_pings", 0) + 1
        if success: s["successful_pings"] = s.get("successful_pings", 0) + 1
        else: s["failed_pings"] = s.get("failed_pings", 0) + 1
        total = s["total_pings"]
        s["uptime_percentage"] = round((s.get("successful_pings", 0) / total) * 100, 2) if total else 0
        s["last_status"] = status
        self.stats[pid] = s
        self.save_projects()
        self.save_stats()

    async def check_dns(self, host):
        try:
            loop = asyncio.get_running_loop()
            res = await loop.getaddrinfo(host, 80, family=socket.AF_INET)
            if res:
                logger.info(f"DNS OK: {host} -> {res[0][-1][0]}")
                return True
        except Exception as e:
            logger.error(f"DNS Failed: {host} | {e}")
        return False

    async def ping_single_project(self, project):
        if not project["active"]: return
        pid, url, name = project["id"], project["url"], project["name"]
        logger.info(f"Pinging: {name}")

        try:
            parsed = urlparse(url if url.startswith('http') else 'https://' + url)
            host = parsed.hostname
            if not host:
                self.update_project_status(pid, "Bad URL", False)
                return

            if not await self.check_dns(host):
                self.update_project_status(pid, "DNS Error", False)
                return

            connector = aiohttp.TCPConnector(
                family=socket.AF_INET,
                ssl=False,
                force_close=True,
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            timeout = aiohttp.ClientTimeout(total=20, connect=15)

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        if resp.status < 500:
                            self.update_project_status(pid, "Running", True)
                            logger.info(f"UP: {name} | {resp.status}")
                        else:
                            self.update_project_status(pid, f"HTTP {resp.status}", False)
                except asyncio.TimeoutError:
                    self.update_project_status(pid, "Timeout", False)
                except Exception as e:
                    self.update_project_status(pid, "Conn Error", False)
                    logger.warning(f"Conn Failed: {e}")

        except Exception as e:
            self.update_project_status(pid, "Error", False)
            logger.error(f"Critical: {e}")

    async def start_monitoring(self):
        if self.is_running: return
        self.is_running = True
        asyncio.create_task(self.ping_loop())
        logger.info("Monitoring ON")

    async def stop_monitoring(self):
        self.is_running = False
        logger.info("Monitoring OFF")

    async def ping_loop(self):
        while self.is_running:
            active = [p for p in self.projects if p["active"]]
            if active:
                for p in active:
                    await self.ping_single_project(p)
                    await asyncio.sleep(2)
            await asyncio.sleep(300)

pm = ProjectManager()

# ====================== SAFE SEND & EDIT (parse_mode SUPPORT) ======================
async def safe_send(update, text, reply_markup=None, parse_mode='Markdown'):
    try:
        if update.message:
            return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query and update.callback_query.message:
            return await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Send failed: {e}")
    return None

async def safe_edit(query, text, reply_markup=None, parse_mode='Markdown'):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception:
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except:
            return False
# =================================================================================

# ====================== HANDLERS ======================
async def start(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await safe_send(update, "Access Denied!")
        return
    kb = [
        ["Project List", "Add Project"],
        ["Statistics", "Quick Ping"],
        ["Start Monitor", "Stop Monitor"],
        ["Status Update", "Detailed Stats"],
        ["Manage Active", "Remove Projects"]
    ]
    await safe_send(update,
        f"**Universal Project Manager**\n\n"
        f"**100% Working Ping**\n"
        f"**DNS + Connection Fixed**\n\n"
        f"**Active:** {sum(1 for p in pm.projects if p['active'])}/{len(pm.projects)}\n\n"
        "Use buttons below:",
        ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def show_projects(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    if not pm.projects:
        await safe_send(update, "No projects! Use /add")
        return
    msg = "**Your Projects:**\n\n"
    kb = []
    for p in pm.projects:
        act = "Active" if p["active"] else "Paused"
        status = p.get("status", "Unknown")
        last = f"Last: {int((datetime.now() - datetime.fromisoformat(p['last_ping'])).total_seconds() / 60)}m ago" if p.get("last_ping") else ""
        msg += f"{act} **{p['name']}**\n`{p['url']}`\nStatus: {status}\n{last}\n───\n"
        kb.append([InlineKeyboardButton(f"{act} {p['name']}", callback_data=f"proj_{p['id']}")])
    kb += [
        [InlineKeyboardButton("Activate All", callback_data="act_all"), InlineKeyboardButton("Deactivate All", callback_data="deact_all")],
        [InlineKeyboardButton("Refresh", callback_data="refresh"), InlineKeyboardButton("Remove Menu", callback_data="remove_menu")]
    ]
    await safe_send(update, msg, InlineKeyboardMarkup(kb))

async def add_project(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await safe_send(update, "Usage: `/add Name https://url.com Category`")
        return
    name, url = context.args[0], context.args[1]
    cat = context.args[2] if len(context.args) > 2 else "General"
    pid = pm.add_project(name, url, cat)
    if pid:
        await safe_send(update, f"**Added!**\n**{name}**\n`{url}`\nID: {pid}\nStatus: Active")
    else:
        await safe_send(update, "Failed!")

async def quick_ping(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    msg = await safe_send(update, "Pinging active projects...")
    for p in [x for x in pm.projects if x["active"]]:
        await pm.ping_single_project(p)
        await asyncio.sleep(1)
    running = sum(1 for p in pm.projects if p.get("status") == "Running")
    if msg:
        await safe_edit(msg, f"**Ping Done!**\nRunning: {running}\nUse /projects")

async def status_update(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    active = [p for p in pm.projects if p["active"]]
    msg = f"**Status Update**\n\nActive: {len(active)}/{len(pm.projects)}\n\n"
    for p in active:
        mins = int((datetime.now() - datetime.fromisoformat(p["last_ping"])).total_seconds() / 60) if p.get("last_ping") else "?"
        msg += f"{p.get('status','?')} **{p['name']}** (Last: {mins}m)\n"
    msg += f"\n**Auto Ping:** {'Running' if pm.is_running else 'Stopped'}"
    await safe_send(update, msg)

async def detailed_stats(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    if not pm.projects:
        await safe_send(update, "No projects!")
        return
    msg = "**Detailed Stats**\n\n"
    for p in pm.projects:
        s = pm.stats.get(p["id"], {})
        act = "Active" if p["active"] else "Paused"
        msg += f"{act} **{p['name']}**\nStatus: {p.get('status','?')}\nUptime: {s.get('uptime_percentage',0)}%\nPings: {s.get('total_pings',0)}\n───\n"
    await safe_send(update, msg)

async def manage_active(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    msg = "**Manage Active**\n\n"
    kb = [[InlineKeyboardButton(f"{'Active' if p['active'] else 'Paused'} {p['name']}", callback_data=f"tog_{p['id']}")] for p in pm.projects]
    kb += [[InlineKeyboardButton("Activate All", callback_data="act_all"), InlineKeyboardButton("Deactivate All", callback_data="deact_all")]]
    await safe_send(update, msg, InlineKeyboardMarkup(kb))

async def remove_menu(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    if not pm.projects:
        await safe_send(update, "No projects!")
        return
    msg = "**Remove Projects**\n\n"
    kb = [[InlineKeyboardButton(f"Remove {p['name']}", callback_data=f"remc_{p['id']}")] for p in pm.projects]
    kb.append([InlineKeyboardButton("Remove All", callback_data="rem_all_confirm")])
    await safe_send(update, msg, InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    d = q.data

    if d.startswith("proj_"):
        pid = d.split("_")[1]
        p = pm.get_project(pid)
        if not p: 
            await safe_edit(q, "Not found!")
            return
        kb = [
            [InlineKeyboardButton("Toggle", callback_data=f"tog_{pid}"), InlineKeyboardButton("Remove", callback_data=f"remc_{pid}")],
            [InlineKeyboardButton("Ping Now", callback_data=f"ping_{pid}"), InlineKeyboardButton("Stats", callback_data=f"stat_{pid}")],
            [InlineKeyboardButton("Back", callback_data="refresh")]
        ]
        mins = int((datetime.now() - datetime.fromisoformat(p["last_ping"])).total_seconds() / 60) if p.get("last_ping") else "?"
        await safe_edit(q, f"**{p['name']}**\n`{p['url']}`\nStatus: {p.get('status','?')}\nLast: {mins}m", InlineKeyboardMarkup(kb))

    elif d.startswith("tog_"):
        pid = d.split("_")[1]
        pm.toggle_project(pid)
        await safe_edit(q, "Toggled!")
        await show_projects(update, context)

    elif d.startswith("ping_"):
        pid = d.split("_")[1]
        p = pm.get_project(pid)
        if p:
            await safe_edit(q, f"Pinging {p['name']}...")
            await pm.ping_single_project(p)
            await safe_edit(q, f"**{p['name']}**: {p.get('status','?')}")
        await show_projects(update, context)

    elif d.startswith("stat_"):
        pid = d.split("_")[1]
        p = pm.get_project(pid)
        s = pm.stats.get(pid, {})
        msg = f"**Stats: {p['name']}**\nUptime: {s.get('uptime_percentage',0)}%\nTotal: {s.get('total_pings',0)}"
        await safe_edit(q, msg, InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data=f"proj_{pid}")]]))

    elif d.startswith("remc_"):
        pid = d.split("_")[1]
        p = pm.get_project(pid)
        if p:
            pm.remove_project(pid)
            await safe_edit(q, f"Removed: {p['name']}")
        await show_projects(update, context)

    elif d == "rem_all_confirm":
        await safe_edit(q, "**Remove ALL?**\nSure?", InlineKeyboardMarkup([
            [InlineKeyboardButton("YES", callback_data="rem_all_yes"), InlineKeyboardButton("NO", callback_data="refresh")]
        ]))

    elif d == "rem_all_yes":
        count = len(pm.projects)
        pm.projects.clear()
        pm.stats.clear()
        pm.save_projects()
        pm.save_stats()
        await safe_edit(q, f"Removed ALL {count} projects!")
        await start(update, context)

    elif d == "act_all":
        c = pm.activate_all()
        await safe_edit(q, f"Activated {c}!")
        await show_projects(update, context)

    elif d == "deact_all":
        c = pm.deactivate_all()
        await safe_edit(q, f"Deactivated {c}!")
        await show_projects(update, context)

    elif d == "refresh":
        await show_projects(update, context)

    elif d == "remove_menu":
        await remove_menu(update, context)

async def handle_text(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID: return
    t = update.message.text
    if t == "Project List": await show_projects(update, context)
    elif t == "Add Project": await safe_send(update, "Use: `/add Name https://url.com`")
    elif t == "Statistics": await status_update(update, context)
    elif t == "Quick Ping": await quick_ping(update, context)
    elif t == "Start Monitor": await pm.start_monitoring(); await safe_send(update, "Monitoring Started")
    elif t == "Stop Monitor": await pm.stop_monitoring(); await safe_send(update, "Monitoring Stopped")
    elif t == "Status Update": await status_update(update, context)
    elif t == "Detailed Stats": await detailed_stats(update, context)
    elif t == "Manage Active": await manage_active(update, context)
    elif t == "Remove Projects": await remove_menu(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_project))
    app.add_handler(CommandHandler("projects", show_projects))
    app.add_handler(CommandHandler("ping", quick_ping))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("BOT STARTED – 100% STABLE!")
    app.run_polling()

if __name__ == "__main__":
    main()
