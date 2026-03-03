"""Message handler for expense and income parsing via AI."""

import json
import logging
import re
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot.services import ai_parser, storage, database
from bot.utils.auth import authorized
from bot.utils.formatting import build_preview_text
from bot.handlers.callbacks import _build_confirmation_keyboard
from bot.categories import INCOME_CATEGORIES, INCOME_CATEGORY_EMOJIS
from bot.i18n import t

logger = logging.getLogger(__name__)

_INCOME_PATTERN = re.compile(r"^\+(\d+(?:[.,]\d+)?)\s+(.+)$")


def _build_income_category_keyboard(income_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard for income category selection."""
    rows = []
    for i, cat in enumerate(INCOME_CATEGORIES):
        emoji = INCOME_CATEGORY_EMOJIS.get(cat, "💰")
        rows.append([
            InlineKeyboardButton(
                f"{emoji} {cat}",
                callback_data=f"income_cat:{income_id}:{i}",
            )
        ])
    rows.append([
        InlineKeyboardButton("❌ " + t("btn_cancel"), callback_data=f"income_cancel:{income_id}"),
    ])
    return InlineKeyboardMarkup(rows)


@authorized
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # Check for income pattern: +5000 wyplata
    income_match = _INCOME_PATTERN.match(user_text)
    if income_match and database.is_available():
        await _handle_income(update, income_match)
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        data = ai_parser.parse_expenses(user_text)

        if not data:
            await context.bot.send_message(
                chat_id=chat_id,
                text=t("no_expense_found"),
                parse_mode="Markdown",
            )
            return

        expense_id = str(uuid.uuid4())
        storage.save_pending(expense_id, {
            "user_id": update.effective_user.id,
            "expenses": data,
            "original_text": user_text,
        })

        preview = build_preview_text(data)
        keyboard = _build_confirmation_keyboard(expense_id, len(data))

        await context.bot.send_message(
            chat_id=chat_id,
            text=preview,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    except json.JSONDecodeError:
        await context.bot.send_message(
            chat_id=chat_id,
            text=t("parse_error"),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=t("general_error"),
        )


async def _handle_income(update: Update, match: re.Match):
    """Handle income entry like +5000 wyplata — shows category selection keyboard."""
    try:
        amount = float(match.group(1).replace(",", "."))
        source = match.group(2).strip()
        today = datetime.now().strftime("%Y-%m-%d")

        income_id = str(uuid.uuid4())
        storage.save_pending_income(income_id, {
            "user_id": update.effective_user.id,
            "amount": amount,
            "source": source,
            "date": today,
        })

        keyboard = _build_income_category_keyboard(income_id)
        await update.message.reply_text(
            t("income_choose_category", amount=f"{amount:.0f}", source=source),
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error handling income: {e}")
        await update.message.reply_text(t("income_error"))
