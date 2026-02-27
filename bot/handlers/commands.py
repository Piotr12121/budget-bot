"""Bot command handlers."""

import csv
import logging
from datetime import datetime, date, timedelta
from io import StringIO, BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot.config import MONTHS_MAPPING, MONTH_NAME_TO_NUM
from bot.categories import CATEGORIES_DISPLAY, CATEGORY_EMOJIS
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
                        amount = float(row[1].replace("\xa0", "").replace(" ", "").replace(",", "."))
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


# --- Budget commands ---

def _build_progress_bar(pct: float, width: int = 10) -> str:
    filled = int(pct / 100 * width)
    filled = min(filled, width)
    empty = width - filled
    return "[" + "\u2588" * filled + "\u2591" * empty + "]"


@authorized
async def budget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set or remove a monthly budget: /budget <category> <amount> or /budget remove <category>."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    args = context.args
    if not args:
        await update.message.reply_text(t("budget_usage"), parse_mode="Markdown")
        return

    user_db_id = database.get_or_create_user(update.effective_user.id)

    # /budget remove <category>
    if args[0].lower() == "remove":
        if len(args) < 2:
            await update.message.reply_text(t("budget_usage"), parse_mode="Markdown")
            return
        cat = " ".join(args[1:])
        category = None if cat.lower() == "total" else cat
        display = t("budget_total_label") if category is None else category
        database.delete_budget(user_db_id, category)
        await update.message.reply_text(t("budget_removed", category=display), parse_mode="Markdown")
        return

    # /budget <category> <amount> or /budget total <amount>
    if len(args) < 2:
        await update.message.reply_text(t("budget_usage"), parse_mode="Markdown")
        return

    try:
        amount = float(args[-1].replace(",", "."))
    except ValueError:
        await update.message.reply_text(t("budget_usage"), parse_mode="Markdown")
        return

    cat = " ".join(args[:-1])
    category = None if cat.lower() == "total" else cat
    display = t("budget_total_label") if category is None else category

    database.set_budget(user_db_id, category, amount)
    await update.message.reply_text(
        t("budget_set", category=display, limit=f"{amount:.0f}"),
        parse_mode="Markdown",
    )


@authorized
async def budgets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all budgets with progress bars."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    user_db_id = database.get_or_create_user(update.effective_user.id)
    budgets = database.get_budgets(user_db_id)

    if not budgets:
        await update.message.reply_text(t("budget_no_budgets"), parse_mode="Markdown")
        return

    month_name = MONTHS_MAPPING[datetime.now().month]
    lines = [t("budget_list_title", month=month_name)]

    for budget in budgets:
        cat = budget["category"]
        limit_val = float(budget["monthly_limit"])
        usage = database.get_budget_usage(user_db_id, cat, month_name)
        pct = (usage / limit_val * 100) if limit_val > 0 else 0
        bar = _build_progress_bar(pct)

        if cat is None:
            emoji = "\U0001f4b0"
            display = t("budget_total_label")
        else:
            emoji = CATEGORY_EMOJIS.get(cat, "\U0001f4c2")
            display = cat

        lines.append(f"{emoji} {display}: {bar} {pct:.0f}% ({usage:.0f}/{limit_val:.0f} PLN)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# --- Chart commands ---

@authorized
async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate expense charts: /chart, /chart bar, /chart <month>."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    from bot.utils.formatting import generate_pie_chart, generate_bar_chart

    args = context.args
    user_db_id = database.get_or_create_user(update.effective_user.id)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO
    )

    # /chart bar — last 3 months comparison
    if args and args[0].lower() == "bar":
        try:
            months_data = {}
            now = datetime.now()
            for i in range(3):
                m = now.month - i
                y = now.year
                if m <= 0:
                    m += 12
                    y -= 1
                month_name = MONTHS_MAPPING[m]
                rows = database.get_expenses_by_month(user_db_id, month_name)
                totals = {}
                for row in rows:
                    cat = row["category"]
                    totals[cat] = totals.get(cat, 0) + float(row["amount"])
                months_data[month_name] = totals

            if not any(months_data.values()):
                await update.message.reply_text(t("chart_no_data", month=""), parse_mode="Markdown")
                return

            buf = generate_bar_chart(months_data, t("chart_bar_title"))
            await update.message.reply_photo(photo=buf)
        except Exception as e:
            logger.error(f"Chart error: {e}")
            await update.message.reply_text(t("chart_error"))
        return

    # /chart [month] — pie chart
    if args:
        month_query = " ".join(args).strip().lower()
        target_month = None
        for name, num in MONTH_NAME_TO_NUM.items():
            if name.startswith(month_query):
                target_month = MONTHS_MAPPING[num]
                break
        if target_month is None:
            await update.message.reply_text(t("month_not_recognized"), parse_mode="Markdown")
            return
    else:
        target_month = MONTHS_MAPPING[datetime.now().month]

    try:
        rows = database.get_expenses_by_month(user_db_id, target_month)
        categories_data = {}
        for row in rows:
            cat = row["category"]
            categories_data[cat] = categories_data.get(cat, 0) + float(row["amount"])

        if not categories_data:
            await update.message.reply_text(t("chart_no_data", month=target_month), parse_mode="Markdown")
            return

        buf = generate_pie_chart(categories_data, t("chart_pie_title", month=target_month))
        await update.message.reply_photo(photo=buf)
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await update.message.reply_text(t("chart_error"))


# --- Recurring commands ---

FREQ_MAP = {
    "codziennie": "daily", "daily": "daily",
    "co tydzień": "weekly", "co tydzien": "weekly", "tygodniowo": "weekly", "weekly": "weekly",
    "co miesiąc": "monthly", "co miesiac": "monthly", "miesięcznie": "monthly",
    "miesiecznie": "monthly", "monthly": "monthly",
}


def _calculate_next_due(frequency: str, day_of_month: int | None = None) -> date:
    today = date.today()
    if frequency == "daily":
        return today + timedelta(days=1)
    elif frequency == "weekly":
        return today + timedelta(weeks=1)
    elif frequency == "monthly":
        dom = day_of_month or today.day
        if today.day >= dom:
            m = today.month + 1
            y = today.year
            if m > 12:
                m = 1
                y += 1
            return date(y, m, min(dom, 28))
        return date(today.year, today.month, min(dom, 28))
    return today + timedelta(days=30)


@authorized
async def recurring_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage recurring expenses: /recurring add|list|remove."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    args = context.args
    if not args:
        await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")
        return

    user_db_id = database.get_or_create_user(update.effective_user.id)
    action = args[0].lower()

    if action == "list":
        items = database.get_recurring(user_db_id)
        if not items:
            await update.message.reply_text(t("recurring_no_items"), parse_mode="Markdown")
            return

        lines = [t("recurring_list_title")]
        for item in items:
            freq_key = f"recurring_freq_{item['frequency']}"
            freq_display = t(freq_key)
            lines.append(
                f"#{item['id']} — *{item['description']}* — {float(item['amount']):.0f} PLN "
                f"({freq_display})\n"
                f"    📂 {item['category']} > {item['subcategory']}\n"
                f"    📅 {t('btn_back')}: {item['next_due']}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    if action == "remove":
        if len(args) < 2:
            await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")
            return
        try:
            rid = int(args[1])
        except ValueError:
            await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")
            return
        database.delete_recurring(rid)
        await update.message.reply_text(t("recurring_removed", id=rid), parse_mode="Markdown")
        return

    if action == "add":
        # /recurring add <amount> <description> <frequency>
        if len(args) < 4:
            await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")
            return

        try:
            amount = float(args[1].replace(",", "."))
        except ValueError:
            await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")
            return

        freq_input = args[-1].lower()
        frequency = FREQ_MAP.get(freq_input)
        if not frequency:
            await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")
            return

        description = " ".join(args[2:-1])
        next_due = _calculate_next_due(frequency)
        freq_display = t(f"recurring_freq_{frequency}")

        rid = database.add_recurring(user_db_id, {
            "amount": amount,
            "category": "Inne wydatki",
            "subcategory": "Inne",
            "description": description,
            "frequency": frequency,
            "day_of_month": date.today().day,
            "next_due": str(next_due),
        })
        await update.message.reply_text(
            t("recurring_added", description=description, amount=f"{amount:.0f}", frequency=freq_display),
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(t("recurring_usage"), parse_mode="Markdown")


async def process_recurring(context):
    """Daily job: create expenses for due recurring items, notify user."""
    if not database.is_available():
        return

    today = date.today()
    due = database.get_due_recurring(today)

    for item in due:
        try:
            expense_dict = {
                "amount": float(item["amount"]),
                "date": str(today),
                "category": item["category"],
                "subcategory": item["subcategory"],
                "description": item["description"],
            }
            database.save_expense(item["user_id"], expense_dict, f"recurring: {item['description']}")

            next_due = _calculate_next_due(item["frequency"], item.get("day_of_month"))
            database.update_next_due(item["id"], next_due)

            await context.bot.send_message(
                chat_id=item["telegram_id"],
                text=t("recurring_created",
                       description=item["description"],
                       amount=f"{float(item['amount']):.0f}"),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error processing recurring expense {item['id']}: {e}")


# --- Balance / Income commands ---

@authorized
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show income vs expenses for current month."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    user_db_id = database.get_or_create_user(update.effective_user.id)
    month_name = MONTHS_MAPPING[datetime.now().month]

    expenses = database.get_expenses_by_month(user_db_id, month_name)
    total_expenses = sum(float(e["amount"]) for e in expenses)

    income_items = database.get_income_by_month(user_db_id, month_name)
    total_income = sum(float(i["amount"]) for i in income_items)

    if total_expenses == 0 and total_income == 0:
        await update.message.reply_text(t("balance_no_data", month=month_name), parse_mode="Markdown")
        return

    net = total_income - total_expenses
    lines = [
        t("balance_title", month=month_name),
        t("balance_income", income=total_income),
        t("balance_expenses", expenses=total_expenses),
        "",
        t("balance_net", net=net),
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# --- Search & Filter commands ---

@authorized
async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search expenses: /search <query>."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    args = context.args
    if not args:
        await update.message.reply_text(t("search_usage"), parse_mode="Markdown")
        return

    query = " ".join(args)
    user_db_id = database.get_or_create_user(update.effective_user.id)
    results = database.search_expenses(user_db_id, query)

    if not results:
        await update.message.reply_text(t("search_no_results", query=query), parse_mode="Markdown")
        return

    lines = [t("search_title", query=query)]
    for i, r in enumerate(results[:20], 1):
        lines.append(f"{i}. `{r['date']}` — *{float(r['amount']):.2f} PLN*\n"
                     f"    {r['category']} > {r['subcategory']}\n"
                     f"    {r['description']}")
    if len(results) > 20:
        lines.append(f"\n... +{len(results) - 20}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last N expenses: /last [N]."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    args = context.args
    limit = 10
    if args:
        try:
            limit = int(args[0])
            limit = min(limit, 50)
        except ValueError:
            pass

    user_db_id = database.get_or_create_user(update.effective_user.id)
    results = database.get_recent_expenses(user_db_id, limit=limit)

    if not results:
        await update.message.reply_text(t("last_no_data"), parse_mode="Markdown")
        return

    lines = [t("last_title", n=len(results))]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. `{r['date']}` — *{float(r['amount']):.2f} PLN*\n"
                     f"    {r['category']} > {r['subcategory']}\n"
                     f"    {r['description']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def expenses_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Filter expenses by date range: /expenses <start_date> <end_date>."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(t("expenses_usage"), parse_mode="Markdown")
        return

    start_date = args[0]
    end_date = args[1]

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(t("expenses_usage"), parse_mode="Markdown")
        return

    user_db_id = database.get_or_create_user(update.effective_user.id)
    results = database.get_expenses_by_date_range(user_db_id, start_date, end_date)

    if not results:
        await update.message.reply_text(t("expenses_no_data"), parse_mode="Markdown")
        return

    total = sum(float(r["amount"]) for r in results)
    lines = [t("expenses_title", start=start_date, end=end_date)]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. `{r['date']}` — *{float(r['amount']):.2f} PLN*\n"
                     f"    {r['category']} > {r['subcategory']}\n"
                     f"    {r['description']}")
    lines.append(f"\n\U0001f4b0 {t('total')}: *{total:.2f} PLN* ({len(results)})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# --- Export CSV ---

@authorized
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export expenses as CSV: /export [month]."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    args = context.args
    if args:
        month_query = " ".join(args).strip().lower()
        target_month = None
        for name, num in MONTH_NAME_TO_NUM.items():
            if name.startswith(month_query):
                target_month = MONTHS_MAPPING[num]
                break
        if target_month is None:
            await update.message.reply_text(t("month_not_recognized"), parse_mode="Markdown")
            return
    else:
        target_month = MONTHS_MAPPING[datetime.now().month]

    user_db_id = database.get_or_create_user(update.effective_user.id)
    expenses = database.get_expenses_by_month(user_db_id, target_month)

    if not expenses:
        await update.message.reply_text(t("export_no_data", month=target_month), parse_mode="Markdown")
        return

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Data", "Kwota", "Kategoria", "Podkategoria", "Opis"])
    for e in expenses:
        writer.writerow([str(e["date"]), float(e["amount"]), e["category"], e["subcategory"], e["description"]])

    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode("utf-8"),
        filename=f"wydatki_{target_month}.csv",
    )


# --- Import from Sheets ---

@authorized
async def import_sheets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import all expenses from Google Sheets into the database: /importsheets."""
    if not database.is_available():
        await update.message.reply_text(t("db_required"))
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    user_db_id = database.get_or_create_user(update.effective_user.id)

    try:
        all_rows = sheets.get_all_rows()
    except Exception as e:
        logger.error(f"Import error: {e}")
        await update.message.reply_text(t("general_error"))
        return

    # Skip header row if present
    data_rows = all_rows
    if data_rows and data_rows[0][0].lower() in ("date", "data"):
        data_rows = data_rows[1:]

    imported = 0
    skipped = 0
    for row in data_rows:
        if len(row) < 5:
            skipped += 1
            continue
        try:
            date_str = row[0].strip()
            amount = float(row[1].replace("\xa0", "").replace(" ", "").replace(",", "."))
            category = row[2].strip()
            subcategory = row[3].strip() if len(row) > 3 else ""
            description = row[4].strip() if len(row) > 4 else ""
            original_text = row[5].strip() if len(row) > 5 else ""

            datetime.strptime(date_str, "%Y-%m-%d")

            expense_dict = {
                "amount": amount,
                "date": date_str,
                "category": category,
                "subcategory": subcategory,
                "description": description,
            }
            database.save_expense(user_db_id, expense_dict, original_text)
            imported += 1
        except (ValueError, IndexError):
            skipped += 1
            continue

    await update.message.reply_text(
        f"✅ Zaimportowano *{imported}* wydatków z arkusza.\n"
        f"⏭️ Pominięto: {skipped} wierszy.",
        parse_mode="Markdown",
    )
