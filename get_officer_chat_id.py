"""
Run this once to find the chat_id to put in .env as OFFICER_CHAT_ID.

Steps:
1. Set TELEGRAM_BOT_TOKEN in your .env (or export it in your shell).
2. Run: python get_officer_chat_id.py
3. From the phone/account that will play "the officer", send any message
   to your bot on Telegram.
4. This script will print that chat's ID. Copy it into .env.
"""
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

load_dotenv()


async def print_chat_id(update, context):
    print(f"\n>>> chat_id = {update.effective_chat.id}  (from {update.effective_user.first_name})\n")
    await update.message.reply_text(f"Your chat_id is: {update.effective_chat.id}")


def main():
    # Prefer the officer bot, so the officer also presses Start in it (needed before it can message them).
    use_officer_bot = bool(os.environ.get("OFFICER_BOT_TOKEN"))
    token = os.environ["OFFICER_BOT_TOKEN"] if use_officer_bot else os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL, print_chat_id))
    which = "the OFFICER bot" if use_officer_bot else "your bot"
    print(f"Stop bot.py first. Waiting for a message... from the officer's phone, open {which} "
          "in Telegram, press Start, and send anything.")
    app.run_polling()


if __name__ == "__main__":
    main()
