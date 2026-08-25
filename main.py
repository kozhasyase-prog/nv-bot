import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8850800726:AAHIOfK2PYkXoy6AJMs86Ruo_DjJW7KS8yY"

# Storage for warning counts
user_warnings = {}

# Check if user is Admin
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']

# 1. Advanced Welcome with Tag Requirement & Buttons
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
            
        text = (
            f"بەخێربێیت {member.full_name} بۆ گروپی **Night Vibes** 🌙\n\n"
            f"تکایە بۆ ئەوەی ببیتە ئەندامی فەرمی، تاگی `⌞NV⌝` بخەرە تەنیشت ناوەکەت."
        )
        
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=update.chat_member.chat.id, text=text, parse_mode="Markdown")

# 2. Moderation Tools (/warn, /mute, /unmute, /ban)
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("تکایە ریپلایی پەیامی سەرپێچیکار بکە!")
        return

    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    user_id = target.id

    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
    count = user_warnings[user_id]

    if count >= 3:
        await context.bot.ban_chat_member(chat_id, user_id)
        user_warnings[user_id] = 0
        await update.message.reply_text(f"🚨 {target.mention_html()} ٣ هۆشداریی وەرگرت و لە گروپ دەرکرا!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ {target.mention_html()} هۆشداریی وەرگرت ({count}/3)!", parse_mode="HTML")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە!")
        return

    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    await context.bot.restrict_chat_member(chat_id, target.id, permissions=ChatPermissions(can_send_messages=False))
    await update.message.reply_text(f"🔇 {target.mention_html()} بێدەنگ کرا!", parse_mode="HTML")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە!")
        return

    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    await context.bot.restrict_chat_member(
        chat_id, 
        target.id, 
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    await update.message.reply_text(f"🔊 {target.mention_html()} ئازاد کرا و دەتوانێت پەیام بنێرێت!", parse_mode="HTML")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە!")
        return

    target = update.message.reply_to_message.from_user
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"🚫 {target.mention_html()} دەرکرا!", parse_mode="HTML")

# 3. Purge Messages (/purge)
async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("تکایە ریپلایی ئەو پەیامە بکە کە دەتەوێت لەوێوە بسڕدرێتەوە.")
        return

    chat_id = update.effective_chat.id
    start_msg_id = update.message.reply_to_message.message_id
    current_msg_id = update.message.message_id

    for msg_id in range(start_msg_id, current_msg_id + 1):
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

# 4. Message Handler (Anti-link, Auto-reply, Greetings)
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    user = update.message.from_user

    # Anti-link Check (Admins are exempted)
    if not await is_admin(update, context):
        if "http://" in text or "https://" in text or "t.me/" in text:
            await update.message.delete()
            await update.message.reply_text(f"⚠️ {user.mention_html()} ناردنی لینک ڕێگەپێنەدراوە!", parse_mode="HTML")
            return

    # Auto-replies
    if "سڵاو" in text or "slaw" in text:
        await update.message.reply_text(f"سڵاو لە تۆش {user.first_name} گیان! بەخێربێیت 🌹")
    elif "یاساکان" in text or "rules" in text:
        rules_text = (
            "📜 **یاساکانی گروپی Night Vibes:**\n"
            "١. ڕێزی ئەندامان بگرە.\n"
            "٢. ناردنی لینک و ریکلام قەدەغەیە.\n"
            "٣. تاگی `⌞NV⌝` بخەرە تەنیشت ناوەکەت."
        )
        await update.message.reply_text(rules_text, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))

    # Command Handlers
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("purge", purge_messages))

    # General Text Handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("Bot is running...")
    app.run_polling(allowed_updates=["message", "chat_member"])

if __name__ == '__main__':
    main()
