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
from bot.services import storage, database, sync


def create_app():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("help", commands.help_cmd))
    application.add_handler(CommandHandler("categories", commands.categories_cmd))
    application.add_handler(CommandHandler("summary", commands.summary_cmd))
    application.add_handler(CommandHandler("undo", commands.undo_cmd))
    application.add_handler(CommandHandler("lang", commands.lang_cmd))
    application.add_handler(CommandHandler("budget", commands.budget_cmd))
    application.add_handler(CommandHandler("budgets", commands.budgets_cmd))
    application.add_handler(CommandHandler("chart", commands.chart_cmd))
    application.add_handler(CommandHandler("recurring", commands.recurring_cmd))
    application.add_handler(CommandHandler("balance", commands.balance_cmd))
    application.add_handler(CommandHandler("search", commands.search_cmd))
    application.add_handler(CommandHandler("last", commands.last_cmd))
    application.add_handler(CommandHandler("expenses", commands.expenses_cmd))
    application.add_handler(CommandHandler("export", commands.export_cmd))
    application.add_handler(CommandHandler("importsheets", commands.import_sheets_cmd))
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), messages.handle_message)
    )
    application.add_handler(CallbackQueryHandler(callbacks.handle_callback))

    return application


async def cleanup_expired_pending(context):
    storage.cleanup_expired()


async def sync_sheets_job(context):
    """Periodic job to sync unsynced expenses to Google Sheets."""
    try:
        sync.sync_unsynced_to_sheets()
    except Exception:
        pass


def main():
    # Initialize PostgreSQL if configured
    if database.is_available():
        database.init_db()
        print("PostgreSQL connected and initialized.")
    else:
        print("PostgreSQL not configured — running in Sheets-only mode.")

    app = create_app()
    # Run cleanup every 30 minutes
    app.job_queue.run_repeating(cleanup_expired_pending, interval=1800, first=60)
    # Sync unsynced expenses to Sheets every 5 minutes (if DB available)
    if database.is_available():
        app.job_queue.run_repeating(sync_sheets_job, interval=300, first=120)
        # Process recurring expenses daily (every 24h, first run after 60s)
        app.job_queue.run_repeating(commands.process_recurring, interval=86400, first=60)
    print("Bot wystartował...")
    app.run_polling()


if __name__ == "__main__":
    main()
