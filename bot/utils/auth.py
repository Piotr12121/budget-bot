from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import ALLOWED_USER_ID
from bot.i18n import t


def authorized(func):
    """Decorator that checks if the user is authorized."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ALLOWED_USER_ID:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("access_denied"),
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
