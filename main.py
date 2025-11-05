#!/usr/bin/env python3
# FinalMM Escrow Bot — 18 Command Version (Choreo.dev 24x7 Ready)

import logging, sqlite3, time, random, re, html, requests, os
from functools import wraps
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

# --- CONFIG ---
BOT_TOKEN = "8232044234:AAG0Mm6_4N7PtK-mPsuNUh3sgeDp5A-OjE8"
OWNER_ID = 6847499628
LOGS_CHANNEL = -1003089374759
DB_FILE = "escrow.db"
PW_BY = "<b>POWDERED BY:</b> @LuffyBots"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- DB INIT ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS deals(
        trade_id TEXT PRIMARY KEY,
        chat_id INTEGER,
        buyer TEXT,
        seller TEXT,
        amount REAL,
        escrower_id INTEGER,
        status TEXT,
        created_at INTEGER,
        closed_at INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY)""")
    c.execute("INSERT OR IGNORE INTO admins VALUES(?)", (OWNER_ID,))
    conn.commit(); conn.close()

def db(q, p=(), f=False):
    conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
    cur.execute(q, p); rows = cur.fetchall() if f else None
    conn.commit(); conn.close(); return rows

init_db()

# --- HELPERS ---
def gen_tid(): return f"TID{random.randint(100000,999999)}"
def mention(u): return f"@{u.username}" if u and u.username else u.first_name
def now(): return int(time.time())

def admin_only(fx):
    @wraps(fx)
    def wrap(u, c, *a, **kw):
        uid = u.effective_user.id
        if uid == OWNER_ID or db("SELECT 1 FROM admins WHERE user_id=?", (uid,), f=True):
            return fx(u, c, *a, **kw)
        u.message.reply_text("⚠️ Only admins or owner can use this command.")
    return wrap

def owner_only(fx):
    @wraps(fx)
    def wrap(u, c, *a, **kw):
        if u.effective_user.id != OWNER_ID:
            u.message.reply_text("❌ Only the owner can use this.")
            return
        return fx(u, c, *a, **kw)
    return wrap

# --- FORMAT MESSAGE ---
def deal_message(title, amount, buyer, seller, trade_id, escrower, color="🔵"):
    return (
        f"{color} <b>{title}</b>\n\n"
        f"💰 <b>Amount:</b> ₹{amount}\n"
        f"🤝 <b>Buyer:</b> {buyer}\n"
        f"🏷️ <b>Seller:</b> {seller}\n"
        f"🧾 <b>Trade ID:</b> #{trade_id}\n"
        f"👑 <b>Escrowed By:</b> {escrower}\n\n"
        f"✅ Payment Received\nContinue your deal safely 🔥\n\n"
        f"🧭 {PW_BY}"
    )

# --- COMMANDS ---
def start(update, ctx):
    update.message.reply_text("🔵 <b>LBMM Escrow Bot Ready!</b>\nUse /command to see all commands.", parse_mode=ParseMode.HTML)

@admin_only
def add(update, ctx):
    if len(ctx.args) < 3:
        update.message.reply_text("Usage: /add <amount> <@buyer> <@seller>"); return
    amount, buyer, seller = ctx.args[0], ctx.args[1], ctx.args[2]
    tid = gen_tid()
    esc = mention(update.effective_user)
    msg = deal_message("💼 NEW DEAL CREATED", amount, buyer, seller, tid, esc)
    db("INSERT INTO deals VALUES(?,?,?,?,?,?,?,?,?)",
       (tid, update.effective_chat.id, buyer, seller, amount, update.effective_user.id, "OPEN", now(), 0))
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    ctx.bot.send_message(LOGS_CHANNEL, f"🧾 New deal logged: {tid} ({amount}) by {esc}")

@admin_only
def close(update, ctx):
    if len(ctx.args) < 1: update.message.reply_text("Usage: /close <TradeID>"); return
    tid = ctx.args[0].upper()
    row = db("SELECT * FROM deals WHERE trade_id=?", (tid,), True)
    if not row: update.message.reply_text("❌ Deal not found."); return
    db("UPDATE deals SET status=?, closed_at=? WHERE trade_id=?", ("CLOSED", now(), tid))
    d = row[0]
    msg = deal_message("✅ DEAL CLOSED", d[4], d[2], d[3], d[0], mention(update.effective_user))
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
def refund(update, ctx):
    if len(ctx.args) < 1: update.message.reply_text("Usage: /refund <TradeID>"); return
    tid = ctx.args[0].upper()
    row = db("SELECT * FROM deals WHERE trade_id=?", (tid,), True)
    if not row: update.message.reply_text("❌ Deal not found."); return
    db("UPDATE deals SET status=?, closed_at=? WHERE trade_id=?", ("REFUNDED", now(), tid))
    d = row[0]
    msg = deal_message("💸 DEAL REFUNDED", d[4], d[2], d[3], d[0], mention(update.effective_user))
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)

@admin_only
def cancel(update, ctx):
    if len(ctx.args) < 1: update.message.reply_text("Usage: /cancel <TradeID>"); return
    tid = ctx.args[0].upper()
    row = db("SELECT * FROM deals WHERE trade_id=?", (tid,), True)
    if not row: update.message.reply_text("❌ Deal not found."); return
    db("UPDATE deals SET status=?, closed_at=? WHERE trade_id=?", ("CANCELLED", now(), tid))
    d = row[0]
    msg = deal_message("❌ DEAL CANCELLED", d[4], d[2], d[3], d[0], mention(update.effective_user))
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)

def status(update, ctx):
    if len(ctx.args) < 1: update.message.reply_text("Usage: /status <TradeID>"); return
    tid = ctx.args[0].upper()
    r = db("SELECT trade_id,status,amount,buyer,seller FROM deals WHERE trade_id=?", (tid,), True)
    if not r: update.message.reply_text("No such deal."); return
    d = r[0]
    update.message.reply_text(f"🔍 #{d[0]} | {d[1]} | ₹{d[2]} | Buyer: {d[3]} | Seller: {d[4]}")

@admin_only
def broadcast(update, ctx):
    msg = " ".join(ctx.args)
    if not msg: update.message.reply_text("Usage: /broadcast <message>"); return
    users = db("SELECT DISTINCT buyer FROM deals", f=True)
    for u in users:
        try: ctx.bot.send_message(u[0], msg)
        except: pass
    update.message.reply_text("✅ Broadcast sent.")

@owner_only
def addadmin(update, ctx):
    if not ctx.args: update.message.reply_text("Usage: /addadmin <user_id>"); return
    db("INSERT OR IGNORE INTO admins VALUES(?)", (int(ctx.args[0]),))
    update.message.reply_text("✅ Admin added.")

@owner_only
def removeadmin(update, ctx):
    if not ctx.args: update.message.reply_text("Usage: /removeadmin <user_id>"); return
    db("DELETE FROM admins WHERE user_id=?", (int(ctx.args[0]),))
    update.message.reply_text("✅ Admin removed.")

@admin_only
def adminlist(update, ctx):
    rows = db("SELECT user_id FROM admins", f=True)
    update.message.reply_text("👑 Admins:\n" + "\n".join(str(r[0]) for r in rows))

@admin_only
def command(update, ctx):
    update.message.reply_text(
        "🧭 <b>All Available Commands</b>\n\n"
        "💼 /add — Create new deal\n"
        "✅ /close — Close deal\n"
        "💸 /refund — Refund deal\n"
        "❌ /cancel — Cancel deal\n"
        "📜 /status — Check deal\n"
        "📊 /stats — Bot stats\n"
        "👑 /addadmin, /removeadmin, /adminlist\n"
        "📢 /broadcast — Owner only\n"
        "📋 /command — Show all commands", parse_mode=ParseMode.HTML)

# --- KEEP ALIVE (PING CHOREO) ---
def keepalive():
    url = os.getenv("PING_URL", "https://choreo.dev/")
    try: requests.get(url, timeout=5)
    except: pass

# --- MAIN ---
def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add))
    dp.add_handler(CommandHandler("close", close))
    dp.add_handler(CommandHandler("refund", refund))
    dp.add_handler(CommandHandler("cancel", cancel))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("addadmin", addadmin))
    dp.add_handler(CommandHandler("removeadmin", removeadmin))
    dp.add_handler(CommandHandler("adminlist", adminlist))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CommandHandler("command", command))

    logger.info("Bot started successfully.")
    updater.start_polling()
    while True:
        time.sleep(7200)
        keepalive()
    updater.idle()

if __name__ == "__main__":
    main()
