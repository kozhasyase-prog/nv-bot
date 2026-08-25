import logging
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

user_warnings = {}

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Check Reply
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user

    # 2. Check Mention Entity (کاتێک بە تاگ ناوەکەی هەڵدەبژێریت)
    for entity in update.message.entities:
        if entity.type == "text_mention":
            return entity.user

    # 3. Check Arguments (ID یان @username)
    if context.args:
        arg = context.args[0]
        if arg.isdigit():
            user_id = int(arg)
            try:
                chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                return chat_member.user
            except Exception:
                pass

    return None

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

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە یان تاگی بکە (ناوی لە لیستی تاگ هەڵبژێرە).")
        return

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
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە یان تاگی بکە.")
        return

    chat_id = update.effective_chat.id
    await context.bot.restrict_chat_member(chat_id, target.id, permissions=ChatPermissions(can_send_messages=False))
    await update.message.reply_text(f"🔇 {target.mention_html()} بێدەنگ کرا!", parse_mode="HTML")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە یان تاگی بکە.")
        return

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
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("تکایە ریپلایی پەیامەکە بکە یان تاگی بکە.")
        return

    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"🚫 {target.mention_html()} دەرکرا!", parse_mode="HTML")

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

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    user = update.message.from_user

    if not await is_admin(update, context):
        if "http://" in text or "https://" in text or "t.me/" in text:
            await update.message.delete()
            await update.message.reply_text(f"⚠️ {user.mention_html()} ناردنی لینک ڕێگەپێنەدراوە!", parse_mode="HTML")
            return

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

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))

    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("purge", purge_messages))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("Bot is running...")
    app.run_polling(allowed_updates=["message", "chat_member"])

if __name__ == '__main__':
    main()
