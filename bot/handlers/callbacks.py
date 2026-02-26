"""Callback query handler for confirm/cancel buttons."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.services import sheets, storage
from bot.utils.formatting import build_save_confirmation

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    action, expense_id = callback_data.split(":", 1)

    pending = storage.pending_expenses.pop(expense_id, None)
    if pending is None:
        await query.edit_message_text("⚠️ Ten wydatek już został przetworzony lub wygasł.")
        return

    if query.from_user.id != pending["user_id"]:
        storage.pending_expenses[expense_id] = pending
        await query.answer("🔒 To nie Twój wydatek.", show_alert=True)
        return

    if action == "cancel":
        await query.edit_message_text("❌ Anulowano — nic nie zostało zapisane.")
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
            await query.edit_message_text(
                "❌ Błąd podczas zapisywania do arkusza. Spróbuj ponownie."
            )
