"""Callback query handler for confirm/cancel/lang buttons."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.services import sheets, storage
from bot.utils.formatting import build_save_confirmation
from bot.i18n import t, set_lang

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    action, value = callback_data.split(":", 1)

    # Language switch
    if action == "lang":
        set_lang(value)
        await query.edit_message_text(t("lang_switched"), parse_mode="Markdown")
        return

    expense_id = value
    pending = storage.pending_expenses.pop(expense_id, None)
    if pending is None:
        await query.edit_message_text(t("expense_expired"))
        return

    if query.from_user.id != pending["user_id"]:
        storage.pending_expenses[expense_id] = pending
        await query.answer(t("not_your_expense"), show_alert=True)
        return

    if action == "cancel":
        await query.edit_message_text(t("cancelled"))
        return

    if action == "confirm":
        try:
            row_indices = sheets.save_expenses_to_sheet(
                pending["expenses"], pending["original_text"]
            )

            storage.last_saved[pending["user_id"]] = {
                "row_indices": row_indices,
                "expenses": pending["expenses"],
            }

            result_text = build_save_confirmation(pending["expenses"])
            await query.edit_message_text(result_text)

        except Exception as e:
            logger.error(f"Error saving expenses: {e}")
            await query.edit_message_text(t("save_error"))
