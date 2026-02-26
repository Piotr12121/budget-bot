"""Message handler for expense parsing via AI."""

import json
import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot.services import ai_parser, storage
from bot.utils.auth import authorized
from bot.utils.formatting import build_preview_text

logger = logging.getLogger(__name__)


@authorized
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        data = ai_parser.parse_expenses(user_text)

        if not data:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "🤔 Nie rozpoznałem wydatku w Twojej wiadomości.\n\n"
                    "Spróbuj np.:\n"
                    "• `50 zł biedronka zakupy`\n"
                    "• `tankowanie orlen 250`\n"
                    "• `biedronka 80, apteka 35`\n\n"
                    "Wpisz /help aby zobaczyć pomoc."
                ),
                parse_mode="Markdown",
            )
            return

        expense_id = str(uuid.uuid4())
        storage.pending_expenses[expense_id] = {
            "user_id": update.effective_user.id,
            "expenses": data,
            "original_text": user_text,
        }

        preview = build_preview_text(data)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Zapisz", callback_data=f"confirm:{expense_id}"),
                InlineKeyboardButton("❌ Anuluj", callback_data=f"cancel:{expense_id}"),
            ]
        ])

        await context.bot.send_message(
            chat_id=chat_id,
            text=preview,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    except json.JSONDecodeError:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🤔 Nie udało mi się zrozumieć wydatku.\n\n"
                "Spróbuj wpisać kwotę i opis, np.: `50 zł biedronka zakupy`"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Wystąpił błąd podczas przetwarzania. Spróbuj ponownie.",
        )
