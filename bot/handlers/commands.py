"""Bot command handlers: /start, /help, /categories, /summary, /undo, /lang."""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot.config import MONTHS_MAPPING, MONTH_NAME_TO_NUM
from bot.categories import CATEGORIES_DISPLAY
from bot.services import sheets, storage, database
from bot.utils.auth import authorized
from bot.i18n import t, set_lang

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t("start_greeting", user_id=user_id),
        parse_mode="Markdown",
    )


@authorized
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t("help_text"),
        parse_mode="Markdown",
    )


@authorized
async def categories_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=CATEGORIES_DISPLAY,
        parse_mode="Markdown",
    )


@authorized
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        month_query = " ".join(args).strip().lower()
        target_month = None
        for name, num in MONTH_NAME_TO_NUM.items():
            if name.startswith(month_query):
                target_month = MONTHS_MAPPING[num]
                break
        if target_month is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("month_not_recognized"),
                parse_mode="Markdown",
            )
            return
    else:
        target_month = MONTHS_MAPPING[datetime.now().month]

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        totals: dict[str, float] = {}
        sub_totals: dict[str, dict[str, float]] = {}
        count = 0

        if database.is_available():
            user_db_id = database.get_or_create_user(update.effective_user.id)
            rows = database.get_expenses_by_month(user_db_id, target_month)
            for row in rows:
                amount = float(row["amount"])
                category = row["category"]
                totals[category] = totals.get(category, 0) + amount
                subcategory = row["subcategory"]
                if subcategory:
                    if category not in sub_totals:
                        sub_totals[category] = {}
                    sub_totals[category][subcategory] = (
                        sub_totals[category].get(subcategory, 0) + amount
                    )
                count += 1
        else:
            all_rows = sheets.get_all_rows()
            for row in all_rows:
                if len(row) < 7:
                    continue
                if row[6].strip() == target_month:
                    try:
                        amount = float(row[1].replace(",", "."))
                        category = row[2]
                        totals[category] = totals.get(category, 0) + amount
                        subcategory = row[3] if len(row) > 3 else ""
                        if subcategory:
                            if category not in sub_totals:
                                sub_totals[category] = {}
                            sub_totals[category][subcategory] = (
                                sub_totals[category].get(subcategory, 0) + amount
                            )
                        count += 1
                    except (ValueError, IndexError):
                        continue

        if not totals:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("summary_no_data", month=target_month),
                parse_mode="Markdown",
            )
            return

        grand_total = sum(totals.values())
        lines = [t("summary_title", month=target_month) + "\n"]
        for cat in sorted(totals, key=lambda c: totals[c], reverse=True):
            lines.append(f"  • {cat}: *{totals[cat]:.2f} PLN*")
            if cat in sub_totals:
                for sub in sorted(
                    sub_totals[cat], key=lambda s: sub_totals[cat][s], reverse=True
                ):
                    lines.append(f"      ◦ {sub}: {sub_totals[cat][sub]:.2f} PLN")
        lines.append(f"\n{t('summary_total', total=grand_total, count=count)}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("summary_error"),
        )


@authorized
async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    saved = storage.get_last_saved(user_id)

    if not saved:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("nothing_to_undo"),
        )
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        expense_ids = saved.get("expense_ids")
        row_indices = saved.get("row_indices")

        if expense_ids and database.is_available():
            database.delete_expenses(expense_ids)
            n = len(expense_ids)
            # Also try to delete from Sheets if we have row indices
            if row_indices:
                try:
                    sheets.delete_rows(row_indices)
                except Exception:
                    logger.warning("Sheets undo failed, rows may remain in sheet")
        elif row_indices:
            sheets.delete_rows(row_indices)
            n = len(row_indices)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("undo_error"),
            )
            return

        storage.delete_last_saved(user_id)

        if n == 1:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("undo_single"),
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=t("undo_multi", n=n),
            )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=t("undo_error"),
        )


@authorized
async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show language selection keyboard."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇵🇱 Polski", callback_data="lang:pl"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        ]
    ])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t("lang_prompt"),
        reply_markup=keyboard,
    )
