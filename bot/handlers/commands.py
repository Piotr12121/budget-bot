"""Bot command handlers: /start, /help, /categories, /summary, /undo."""

import logging
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot.config import MONTHS_MAPPING, MONTH_NAME_TO_NUM
from bot.categories import CATEGORIES_DISPLAY
from bot.services import sheets, storage
from bot.utils.auth import authorized

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"👋 Cześć! Twoje ID to: `{user_id}`.\n\n"
            f"Wpisz je w pliku `.env` jako `ALLOWED_USER_ID`, aby autoryzować bota.\n\n"
            f"Wpisz /help aby zobaczyć dostępne komendy."
        ),
        parse_mode="Markdown",
    )


@authorized
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "📖 *Jak używać bota?*\n\n"
            "Wyślij wiadomość z wydatkiem, np.:\n"
            "• `50 zł biedronka zakupy`\n"
            "• `tankowanie orlen 250`\n"
            "• `wczoraj netflix 45`\n"
            "• `biedronka 80, apteka 35, siłownia 120`\n\n"
            "Bot rozpozna kwotę, datę i kategorię, a potem poprosi o potwierdzenie.\n\n"
            "*Komendy:*\n"
            "/help — ta wiadomość\n"
            "/categories — lista kategorii\n"
            "/summary — podsumowanie bieżącego miesiąca\n"
            "/summary _nazwa miesiąca_ — podsumowanie konkretnego miesiąca\n"
            "/undo — cofnij ostatni zapisany wydatek\n"
        ),
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
                text="❌ Nie rozpoznałem nazwy miesiąca. Spróbuj np. `/summary styczeń`.",
                parse_mode="Markdown",
            )
            return
    else:
        target_month = MONTHS_MAPPING[datetime.now().month]

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        all_rows = sheets.get_all_rows()

        totals: dict[str, float] = {}
        sub_totals: dict[str, dict[str, float]] = {}
        count = 0
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
                text=f"📊 Brak wydatków za: *{target_month}*.",
                parse_mode="Markdown",
            )
            return

        grand_total = sum(totals.values())
        lines = [f"📊 *Podsumowanie: {target_month}*\n"]
        for cat in sorted(totals, key=lambda c: totals[c], reverse=True):
            lines.append(f"  • {cat}: *{totals[cat]:.2f} PLN*")
            if cat in sub_totals:
                for sub in sorted(
                    sub_totals[cat], key=lambda s: sub_totals[cat][s], reverse=True
                ):
                    lines.append(f"      ◦ {sub}: {sub_totals[cat][sub]:.2f} PLN")
        lines.append(f"\n💰 *Razem: {grand_total:.2f} PLN* ({count} wpisów)")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Nie udało się pobrać podsumowania. Spróbuj ponownie później.",
        )


@authorized
async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    saved = storage.last_saved.get(user_id)

    if not saved:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🤷 Nie ma czego cofać — brak ostatniego wpisu w pamięci.",
        )
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        sheets.delete_rows(saved["row_indices"])
        n = len(saved["row_indices"])
        del storage.last_saved[user_id]

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"↩️ Cofnięto {'ostatni wpis' if n == 1 else f'ostatnie {n} wpisy'}.",
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Nie udało się cofnąć wpisu. Spróbuj ponownie.",
        )
