"""Main entry point for the budget bot."""

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from bot.config import TELEGRAM_TOKEN
from bot.handlers import commands, messages, callbacks


def create_app():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("help", commands.help_cmd))
    application.add_handler(CommandHandler("categories", commands.categories_cmd))
    application.add_handler(CommandHandler("summary", commands.summary_cmd))
    application.add_handler(CommandHandler("undo", commands.undo_cmd))
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), messages.handle_message)
    )
    application.add_handler(CallbackQueryHandler(callbacks.handle_callback))

    return application


def main():
    app = create_app()
    print("Bot wystartował...")
    app.run_polling()


if __name__ == "__main__":
    main()
