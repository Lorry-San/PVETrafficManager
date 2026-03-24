# -*- coding: utf-8 -*-
import subprocess, sqlite3, asyncio, re, os
from datetime import datetime
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler

# --- 核心配置 ---
TOKEN = ""
ADMIN_ID =  
DB = "/var/lib/pve/vms_traffic_v3.db"

# --- 流量采集逻辑 ---
def get_traffic(vmid):
    rx, tx = 0.0, 0.0
    try:
        res = subprocess.check_output(f"grep 'tap{vmid}i' /proc/net/dev", shell=True).decode()
        for line in res.strip().split('\n'):
            p = line.split()
            rx += float(p[1]); tx += float(p[9])
    except: pass
    return rx, tx

def set_net(vmid, action):
    try:
        conf = subprocess.check_output(f"qm config {vmid}", shell=True).decode()
        nets = re.findall(r'^(net\d+): (.*)', conf, re.MULTILINE)
        for nid, ncfg in nets:
            clean = ncfg.replace(',link_down=1','').replace(',link_down=0','')
            subprocess.run(f"qm set {vmid} --{nid} {clean},link_down={action}", shell=True)
    except: pass

# --- Telegram 指令处理器 ---
async def set_bot_menu(app):
    commands = [
        BotCommand("status", "📊 View usage"),
        BotCommand("uid", "🆔 Get your ID"),
        BotCommand("help", "❓ Show help"),
        BotCommand("add", "➕ [Admin] Add VM: [id] [gb] [user_id]"),
        BotCommand("setowner", "👤 [Admin] Change Owner: [id] [user_id]"),
        BotCommand("setday", "📅 [Admin] Set Reset Day: [id] [1-28]"),
        BotCommand("reset", "♻️ [Admin] Reset & Unblock: [id]"),
        BotCommand("del", "🗑️ [Admin] Remove VM: [id]")
    ]
    await app.bot.set_my_commands(commands)

async def help_cmd(u, c):
    uid = u.effective_user.id
    if uid == ADMIN_ID:
        h = ("👑 *Admin Console*\n/status - View all usage\n/add [id] [gb] [user_id] - Add VM\n/setowner [id] [uid] - Change Owner\n/setday [id] [1-28] - Set Reset Day\n/reset [id] - Reset & Unblock\n/del [id] - Stop monitor\n/uid - Get your ID")
    else:
        h = ("📱 *User Terminal*\n/status - View MY VM usage\n/uid - Get your ID")
    await u.message.reply_text(h, parse_mode='Markdown')

async def get_uid(u, c):
    await u.message.reply_text(f"Your ID: `{u.effective_user.id}`", parse_mode='Markdown')

async def status(u, c):
    uid = u.effective_user.id
    with sqlite3.connect(DB) as conn:
        if uid == ADMIN_ID:
            rows = conn.execute("SELECT * FROM vms").fetchall()
        else:
            rows = conn.execute("SELECT * FROM vms WHERE owner=?", (uid,)).fetchall()
    if not rows: return await u.message.reply_text("No records found.")
    m = "📊 *Traffic Report*\n" + "—"*12 + "\n"
    for v, g, d, rx, tx, lrx, ltx, st, owner in rows:
        use_gb = (rx + tx) / 1e9
        stat = "🚫 OFF" if st else "✅ ON"
        m += f"VM: `{v}` | `{use_gb:.2f}/{g}G` | Day:`{d}` | {stat}"
        if uid == ADMIN_ID: m += f"\n└ Owner: `{owner}`"
        m += "\n" + "—"*12 + "\n"
    await u.message.reply_text(m, parse_mode='Markdown')

async def add(u, c):
    if u.effective_user.id != ADMIN_ID: return
    try:
        v, g = c.args[0], float(c.args[1])
        owner = int(c.args[2]) if len(c.args) > 2 else ADMIN_ID
        today = datetime.now().day
        cr, ct = get_traffic(v)
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT OR REPLACE INTO vms VALUES(?,?,?,?,?,?,?,?,?)", (v, g, today, 0.0, 0.0, cr, ct, 0, owner))
        await u.message.reply_text(f"✅ Added VM `{v}` @ `{g}G`. Owner: `{owner}`", parse_mode='Markdown')
    except: await u.message.reply_text("Usage: `/add [vmid] [gb] [user_id]`")

async def set_owner(u, c):
    if u.effective_user.id != ADMIN_ID: return
    try:
        v, o = c.args[0], int(c.args[1])
        with sqlite3.connect(DB) as conn:
            conn.execute("UPDATE vms SET owner=? WHERE id=?", (o, v))
        await u.message.reply_text(f"✅ Owner of VM `{v}` changed to `{o}`")
    except: await u.message.reply_text("Usage: `/setowner [vmid] [user_id]`")

async def set_day(u, c):
    if u.effective_user.id != ADMIN_ID: return
    try:
        v, d = c.args[0], int(c.args[1])
        with sqlite3.connect(DB) as conn:
            conn.execute("UPDATE vms SET d=? WHERE id=?", (d, v))
        await u.message.reply_text(f"📅 VM `{v}` reset day set to `{d}`")
    except: await u.message.reply_text("Usage: `/setday [vmid] [1-28]`")

async def reset(u, c):
    if u.effective_user.id != ADMIN_ID: return
    try:
        v = c.args[0]; set_net(v, 0); cr, ct = get_traffic(v)
        with sqlite3.connect(DB) as conn:
            conn.execute("UPDATE vms SET rx=0,tx=0,lrx=?,ltx=?,st=0 WHERE id=?", (cr, ct, v))
        await u.message.reply_text(f"♻️ VM `{v}` reset & reconnected")
    except: await u.message.reply_text("Usage: `/reset [vmid]`")

async def del_vm(u, c):
    if u.effective_user.id != ADMIN_ID: return
    try:
        v = c.args[0]
        with sqlite3.connect(DB) as conn: conn.execute("DELETE FROM vms WHERE id=?", (v,))
        await u.message.reply_text(f"🗑️ Stopped monitoring VM `{v}`")
    except: await u.message.reply_text("Usage: `/del [vmid]`")

# --- 监控循环 ---
async def monitor_loop(ap):
    lr_day = -1
    while True:
        now = datetime.now()
        with sqlite3.connect(DB) as conn:
            vms = conn.execute("SELECT * FROM vms").fetchall()
            for v, g, rd, ar, at, lr, lt, st, owner in vms:
                if now.day == rd and now.hour == 0 and now.minute == 0 and now.day != lr_day:
                    ar, at, st = 0.0, 0.0, 0; set_net(v, 0); lr_day = now.day
                cr, ct = get_traffic(v)
                dr, dt = (cr if cr < lr else cr-lr), (ct if ct < lt else ct-lt)
                nr, nt = ar+dr, at+dt
                if (nr+nt) > (g*1e9) and st == 0:
                    set_net(v, 1); st = 1
                    msg = f"‼️ *LIMIT REACHED*\nVM: `{v}` used `{g} GB`."
                    await ap.bot.send_message(ADMIN_ID, msg, parse_mode='Markdown')
                    if owner != ADMIN_ID:
                        try: await ap.bot.send_message(owner, msg, parse_mode='Markdown')
                        except: pass
                conn.execute("UPDATE vms SET rx=?,tx=?,lrx=?,ltx=?,st=? WHERE id=?", (nr, nt, cr, ct, st, v))
        await asyncio.sleep(5)

if __name__ == '__main__':
    os.makedirs("/var/lib/pve", exist_ok=True)
    with sqlite3.connect(DB) as q:
        q.execute("CREATE TABLE IF NOT EXISTS vms(id TEXT PRIMARY KEY, g REAL, d INT, rx REAL, tx REAL, lrx REAL, ltx REAL, st INT, owner INT)")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", help_cmd)); app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status)); app.add_handler(CommandHandler("uid", get_uid))
    app.add_handler(CommandHandler("add", add)); app.add_handler(CommandHandler("setowner", set_owner))
    app.add_handler(CommandHandler("setday", set_day)); app.add_handler(CommandHandler("reset", reset)); app.add_handler(CommandHandler("del", del_vm))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_bot_menu(app))
    loop.create_task(monitor_loop(app))
    app.run_polling()
