import logging
import sqlite3
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8850800726:AAHIOfK2PYkXoy6AJMs86Ruo_DjJW7KS8yY"

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
    # 1. Reply
    if update.message and update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        save_user(target.id, target.username, target.first_name)
        return target.id, target.first_name

    # 2. Text Mention Entity
    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention" and entity.user:
                save_user(entity.user.id, entity.user.username, entity.user.first_name)
                return entity.user.id, entity.user.first_name

    # 3. Text Argument (@username yanyan ID)
    if context.args:
        arg = context.args[0]
        if arg.isdigit():
            return int(arg), f"User {arg}"
        elif arg.startswith('@'):
            user_id, first_name = get_user_id_by_username(arg)
            if user_id:
                return user_id, first_name or arg

    return None, None

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
            await update.message.reply_text(text, parse_mode="Markdown")
        elif update.chat_member:
            await context.bot.send_message(chat_id=update.chat_member.chat.id, text=text, parse_mode="Markdown")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە دەستنەکەوت! تکایە تاگەکە بە دروستی بنووسە یان ریپلایی بکە.")
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

    chat_id = update.effective_chat.id
    await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
    await update.message.reply_text(f"🔇 **{name}** بێدەنگ کرا!", parse_mode="Markdown")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    user_id, name = await get_target_user(update, context)
    if not user_id:
        await update.message.reply_text("کەسەکە لە داتابەیج نەدۆزرایەوە! (دەبێت لانیکەم یەک پەیامی ناردبێت یان نوێ هاتبیێتە گروپەکە).")
        return

    chat_id = update.effective_chat.id
    await context.bot.restrict_chat_member(
        chat_id, 
        user_id, 
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    await update.message.reply_text(f"🔊 **{name}** ئازاد کرا و دەتوانێت پەیام بنێرێت!", parse_mode="Markdown")

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

    if "سڵاو" in text or "slaw" in text:
        await update.message.reply_text(f"سڵاو لە تۆش {user.first_name} گیان! بەخێربێیت 🌹")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))

    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("unwarn", unwarn_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("Bot with Database is running...")
    app.run_polling(allowed_updates=["message", "chat_member"])

if __name__ == '__main__':
    main()
