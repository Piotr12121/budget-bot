"""Callback query handler for confirm/cancel/edit/lang buttons."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.services import sheets, storage
from bot.utils.formatting import build_preview_text, build_save_confirmation
from bot.categories import CATEGORIES, CATEGORY_NAMES, CATEGORY_EMOJIS
from bot.i18n import t, set_lang

logger = logging.getLogger(__name__)


def _build_confirmation_keyboard(expense_id: str, num_expenses: int) -> InlineKeyboardMarkup:
    """Build the confirmation keyboard with edit/save/cancel buttons."""
    rows = []
    if num_expenses == 1:
        rows.append([
            InlineKeyboardButton(t("btn_edit"), callback_data=f"edit:{expense_id}:0"),
        ])
    else:
        # Per-item edit buttons for batch expenses
        edit_buttons = []
        for i in range(num_expenses):
            edit_buttons.append(
                InlineKeyboardButton(f"✏️ #{i+1}", callback_data=f"edit:{expense_id}:{i}")
            )
            if len(edit_buttons) == 3:
                rows.append(edit_buttons)
                edit_buttons = []
        if edit_buttons:
            rows.append(edit_buttons)

    rows.append([
        InlineKeyboardButton(t("btn_save"), callback_data=f"confirm:{expense_id}"),
        InlineKeyboardButton(t("btn_cancel"), callback_data=f"cancel:{expense_id}"),
    ])
    return InlineKeyboardMarkup(rows)


def _build_category_keyboard(expense_id: str, item_idx: int) -> InlineKeyboardMarkup:
    """Build keyboard with all main categories."""
    rows = []
    for i, cat_name in enumerate(CATEGORY_NAMES):
        emoji = CATEGORY_EMOJIS.get(cat_name, "📂")
        rows.append([
            InlineKeyboardButton(
                f"{emoji} {cat_name}",
                callback_data=f"cat:{expense_id}:{item_idx}:{i}",
            )
        ])
    rows.append([
        InlineKeyboardButton("⬅️ " + t("btn_back"), callback_data=f"back:{expense_id}"),
    ])
    return InlineKeyboardMarkup(rows)


def _build_subcategory_keyboard(
    expense_id: str, item_idx: int, cat_idx: int
) -> InlineKeyboardMarkup:
    """Build keyboard with subcategories for a given category."""
    cat_name = CATEGORY_NAMES[cat_idx]
    subcategories = CATEGORIES[cat_name]
    rows = []
    for j, sub_name in enumerate(subcategories):
        rows.append([
            InlineKeyboardButton(
                sub_name,
                callback_data=f"sub:{expense_id}:{item_idx}:{cat_idx}:{j}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            "⬅️ " + t("btn_back"),
            callback_data=f"edit:{expense_id}:{item_idx}",
        ),
    ])
    return InlineKeyboardMarkup(rows)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    parts = callback_data.split(":")
    action = parts[0]

    # Language switch
    if action == "lang":
        set_lang(parts[1])
        await query.edit_message_text(t("lang_switched"), parse_mode="Markdown")
        return

    # Extract expense_id (always parts[1] for expense actions)
    expense_id = parts[1]

    # For edit/cat/sub/back, we need to peek at the pending expense without removing it
    if action in ("edit", "cat", "sub", "back"):
        pending = storage.get_pending(expense_id)
        if pending is None:
            await query.edit_message_text(t("expense_expired"))
            return
        if query.from_user.id != pending["user_id"]:
            await query.answer(t("not_your_expense"), show_alert=True)
            return

    if action == "edit":
        # Show category selection for the given item
        item_idx = int(parts[2])
        keyboard = _build_category_keyboard(expense_id, item_idx)
        current = pending["expenses"][item_idx]
        text = (
            f"✏️ *{t('edit_category_prompt')}*\n\n"
            f"📝 {current['description']} — *{current['amount']} PLN*\n"
            f"📂 {current['category']} > {current['subcategory']}"
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return

    if action == "cat":
        # Show subcategories for selected category
        item_idx = int(parts[2])
        cat_idx = int(parts[3])
        cat_name = CATEGORY_NAMES[cat_idx]
        keyboard = _build_subcategory_keyboard(expense_id, item_idx, cat_idx)
        emoji = CATEGORY_EMOJIS.get(cat_name, "📂")
        text = f"✏️ {emoji} *{cat_name}*\n\n{t('edit_subcategory_prompt')}"
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return

    if action == "sub":
        # Apply the selected category/subcategory and return to preview
        item_idx = int(parts[2])
        cat_idx = int(parts[3])
        sub_idx = int(parts[4])

        cat_name = CATEGORY_NAMES[cat_idx]
        sub_name = CATEGORIES[cat_name][sub_idx]

        pending["expenses"][item_idx]["category"] = cat_name
        pending["expenses"][item_idx]["subcategory"] = sub_name
        storage.save_pending(expense_id, pending)

        preview = build_preview_text(pending["expenses"])
        keyboard = _build_confirmation_keyboard(expense_id, len(pending["expenses"]))
        await query.edit_message_text(preview, reply_markup=keyboard, parse_mode="Markdown")
        return

    if action == "back":
        # Return to preview
        pending = storage.get_pending(expense_id)
        if pending is None:
            await query.edit_message_text(t("expense_expired"))
            return
        preview = build_preview_text(pending["expenses"])
        keyboard = _build_confirmation_keyboard(expense_id, len(pending["expenses"]))
        await query.edit_message_text(preview, reply_markup=keyboard, parse_mode="Markdown")
        return

    # For confirm/cancel, pop the pending expense
    pending = storage.pop_pending(expense_id)
    if pending is None:
        await query.edit_message_text(t("expense_expired"))
        return

    if query.from_user.id != pending["user_id"]:
        storage.save_pending(expense_id, pending)
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

            storage.save_last_saved(pending["user_id"], {
                "row_indices": row_indices,
                "expenses": pending["expenses"],
            })

            result_text = build_save_confirmation(pending["expenses"])
            await query.edit_message_text(result_text)

        except Exception as e:
            logger.error(f"Error saving expenses: {e}")
            await query.edit_message_text(t("save_error"))
