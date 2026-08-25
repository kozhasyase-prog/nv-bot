import logging
import sqlite3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# --- Dummy Web Server for Render Port Binding ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()
# ------------------------------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8850800726:AAHIOfK2PYkXoy6AJMs86Ruo_DjJW7KS8yY"

BAD_WORDS = ["کەر", "جندۆکە", "سەگ", "bitch", "fuck"]

# ----------------- Database Setup -----------------
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def save_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    username_clean = username.lower() if username else None
    cursor.execute('''
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    ''', (user_id, username_clean, first_name))
    conn.commit()
    conn.close()

def get_user_id_by_username(username: str):
    username = username.lstrip('@').lower()
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, first_name FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None

init_db()
# --------------------------------------------------

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        save_user(target.id, target.username, target.first_name)
        return target.id, target.first_name

    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention" and entity.user:
                save_user(entity.user.id, entity.user.username, entity.user.first_name)
                return entity.user.id, entity.user.first_name

    if context.args:
        arg = context.args[0]
        if arg.isdigit():
            return int(arg), f"User {arg}"
        elif arg.startswith('@'):
            user_id, first_name = get_user_id_by_username(arg)
            if user_id:
                return user_id, first_name or arg

    return None, None

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return

    help_text = (
        "🛠 **ڕێنمایی بەکارهێنانی فەرمانەکانی ئەدمین (Night Vibes Bot)**\n\n"
        "📌 **فەرمانەکانی بەڕێوەبردن (تەواوی تاگ یان ریپلای):**\n"
        "• `/warn @username` - پێدانی هۆشداریی بە ئەندام (بە ٣ هۆشداری دەردەکرێت).\n"
        "• `/unwarn @username` - سڕینەوەی هۆشدارییەکانی ئەندام.\n"
        "• `/mute @username` - بێدەنگکردنی ئەندام لە پەیام ناردن.\n"
        "• `/unmute @username` - لادانی بێدەنگی و ڕێگەدان بە پەیام ناردن.\n"
        "• `/ban @username` - دەرکردنی ئۆتۆماتیکی ئەندام لە گروپ.\n"
        "• `/unban @username` - لادانی بان و ڕێگەدان بە گەڕانەوەی ئەندام.\n\n"
        "🔒 **کۆنترۆڵی گروپ و چات:**\n"
        "• `/purge <ژمارە>` - سڕینەوەی ژمارەیەکی دیاریکراوی پەیامەکان (بۆ نموونە `/purge 10`).\n"
        "• `/lock` - قوفڵکردنی چاتی گروپ (هیچ ئەندامێک ناتوانێت بنووسێت).\n"
        "• `/unlock` - کردنەوەی چاتی گروپ بۆ ئەندامان.\n\n"
        "📊 **ئامار و زانیاری:**\n"
        "• `/stats` - پیشاندانی ژمارەی ئەندامە سەیڤکراوەکان و هۆشدارییەکان.\n"
        "• `/help` - پیشاندانی ئەم ڕێنماییە (تەنها بە ئەدمین نیشان دەدرێت)."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    members = []
    if update.message and update.message.new_chat_members:
        members = update.message.new_chat_members
    elif update.chat_member:
        new_status = update.chat_member.new_chat_member.status
        old_status = update.chat_member.old_chat_member.status
        if old_status in ["left", "kicked"] and new_status == "member":
            members = [update.chat_member.new_chat_member.user]

    for member in members:
        if member.id == context.bot.id:
            continue
        save_user(member.id, member.username, member.first_name)
        
        text = (
            f"بەخێربێیت {member.full_name} بۆ گروپی **Night Vibes** 🌙\n\n"
            f"تکایە بۆ ئەوەی ببیتە ئەندامی فەرمی، تاگی `⌞NV⌝` بخەرە تەنیشت ناوەکەت."
        )
        if update.message:
            msg = await update.message.reply_text(text, parse_mode="Markdown")
            try:
                await context.bot.pin_chat_message(update.effective_chat.id, msg.message_id)
            except Exception:
                pass

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە دەستنەکەوت! تاگەکەی بنووسە یان ریپلایی بکە.")
        return

    chat_id = update.effective_chat.id
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT count FROM warnings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    count = (row[0] if row else 0) + 1
    cursor.execute('INSERT INTO warnings (user_id, count) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET count = excluded.count', (user_id, count))
    conn.commit()
    conn.close()

    if count >= 3:
        await context.bot.ban_chat_member(chat_id, user_id)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM warnings WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🚨 **{name}** ٣ هۆشداریی وەرگرت و لە گروپ دەرکرا!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ **{name}** هۆشداریی وەرگرت ({count}/3)!", parse_mode="Markdown")

async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە دەستنەکەوت!")
        return

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM warnings WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ هۆشدارییەکان لەسەر **{name}** لابردران.", parse_mode="Markdown")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە دەستنەکەوت!")
        return

    await context.bot.restrict_chat_member(update.effective_chat.id, user_id, permissions=ChatPermissions(can_send_messages=False))
    await update.message.reply_text(f"🔇 **{name}** بێدەنگ کرا!", parse_mode="Markdown")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە لە داتابەیج نەدۆزرایەوە!")
        return

    await context.bot.restrict_chat_member(
        update.effective_chat.id, 
        user_id, 
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    await update.message.reply_text(f"🔊 **{name}** ئازاد کرا!", parse_mode="Markdown")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە دەستنەکەوت!")
        return

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text(f"🚫 **{name}** دەرکرا!", parse_mode="Markdown")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە دەستنەکەوت!")
        return

    await context.bot.unban_chat_member(update.effective_chat.id, user_id, only_if_banned=True)
    await update.message.reply_text(f"🔓 **{name}** لە بان دەرهێنرا!", parse_mode="Markdown")

async def lock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    await context.bot.set_chat_permissions(update.effective_chat.id, ChatPermissions(can_send_messages=False))
    await update.message.reply_text("🔒 **چاتی گروپ قوفڵکرا!** تەنها ئەدمینەکان دەتوانن بنووسن.", parse_mode="Markdown")

async def unlock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    await context.bot.set_chat_permissions(
        update.effective_chat.id, 
        ChatPermissions(
            can_send_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    await update.message.reply_text("🔓 **چاتی گروپ کرایەوە!** هەمووان دەتوانن بنووسن.", parse_mode="Markdown")

async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    
    count = 10
    if context.args and context.args[0].isdigit():
        count = int(context.args[0])

    chat_id = update.effective_chat.id
    current_id = update.message.message_id

    for msg_id in range(current_id, current_id - count - 1, -1):
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

async def get_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM warnings')
    total_warned = cursor.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 **ئاماری گروپی Night Vibes:**\n\n"
        f"👥 ئەندامە تۆمارکراوەکان لە داتابەیج: `{total_users}`\n"
        f"⚠️ ئەو کەسانەی هۆشدارییان لەسەرە: `{total_warned}`",
        parse_mode="Markdown"
    )

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    save_user(user.id, user.username, user.first_name)

    text = update.message.text.lower() if update.message.text else ""

    if not await is_admin(update, context):
        if "http://" in text or "https://" in text or "t.me/" in text:
            await update.message.delete()
            await update.message.reply_text(f"⚠️ **{user.first_name}** ناردنی لینک ڕێگەپێنەدراوە!", parse_mode="Markdown")
            return

        for word in BAD_WORDS:
            if word in text:
                await update.message.delete()
                await update.message.reply_text(f"🛑 **{user.first_name}** بەکارھێنانی وشەی نەشیاو قەدەغەیە!", parse_mode="Markdown")
                return

    if "سڵاو" in text or "slaw" in text:
        await update.message.reply_text(f"سڵاو لە تۆش {user.first_name} گیان! بەخێربێیت 🌹")

def main():
    # دەستپێکردنی سێرڤەری کاتی لە فۆنکشنێکی سەربەخۆ بۆ ئەوەی Render ڕازی بێت بە Port Binding
    threading.Thread(target=run_web_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))

    # Commands
    app.add_handler(CommandHandler("help", admin_help))
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("unwarn", unwarn_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("lock", lock_chat))
    app.add_handler(CommandHandler("unlock", unlock_chat))
    app.add_handler(CommandHandler("purge", purge_messages))
    app.add_handler(CommandHandler("stats", get_stats))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("Full Bot with Admin Tools & Database is running...")
    app.run_polling(allowed_updates=["message", "chat_member"])

if __name__ == '__main__':
    main()
