from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ChatMemberHandler, filters, ContextTypes

TOKEN = "8850800726:AAHIOfK2PYkXoy6AJMs86Ruo_DjJW7KS8yY"

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

async def reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        msg_text = update.message.text.lower()
        if "سڵاو" in msg_text or "slaw" in msg_text:
            await update.message.reply_text(f"سڵاو لە تۆش {update.message.from_user.first_name} گیان! بەخێربێیت 🌹")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_text))
    
    print("Bot is running...")
    app.run_polling(allowed_updates=["message", "chat_member"])
