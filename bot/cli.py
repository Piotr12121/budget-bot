"""CLI interface for budzet-bot — full command parity with the Telegram bot."""

import argparse
import csv
import re
import sys
from datetime import datetime, date, timedelta
from io import StringIO

from bot.config import ALLOWED_USER_ID, MONTHS_MAPPING, MONTH_NAME_TO_NUM
from bot.categories import CATEGORIES_DISPLAY, CATEGORY_EMOJIS
from bot.i18n import t, set_lang


# ── helpers ──────────────────────────────────────────────────────────


def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting characters for terminal output."""
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = text.replace("`", "")
    return text


def _get_user_id() -> int:
    """Get DB user ID for the CLI user."""
    from bot.services import database

    return database.get_or_create_user(ALLOWED_USER_ID)


def _resolve_month(month_arg: str | None) -> str:
    """Resolve a month name/number to a canonical Polish month name."""
    if not month_arg:
        return MONTHS_MAPPING[datetime.now().month]

    query = month_arg.strip().lower()
    for name, num in MONTH_NAME_TO_NUM.items():
        if name.startswith(query):
            return MONTHS_MAPPING[num]

    try:
        num = int(query)
        if 1 <= num <= 12:
            return MONTHS_MAPPING[num]
    except ValueError:
        pass

    print(f"Error: unrecognized month '{month_arg}'")
    sys.exit(1)


def _require_db():
    """Exit with error if PostgreSQL is not available."""
    from bot.services import database

    if not database.is_available():
        print(_strip_markdown(t("db_required")))
        sys.exit(1)


def _build_progress_bar(pct: float, width: int = 20) -> str:
    """Build a text progress bar."""
    filled = min(int(pct / 100 * width), width)
    empty = width - filled
    return "[" + "\u2588" * filled + "\u2591" * empty + "]"


def _calculate_next_due(frequency: str, day_of_month: int | None = None) -> date:
    """Calculate the next due date for a recurring expense."""
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


def _format_expense_list(expenses: list[dict]) -> str:
    """Format a list of expense dicts for terminal output."""
    lines = []
    for i, e in enumerate(expenses, 1):
        amount = float(e["amount"])
        lines.append(
            f"{i}. {e['date']}  {amount:.2f} PLN\n"
            f"   {e['category']} > {e['subcategory']}\n"
            f"   {e['description']}"
        )
    return "\n".join(lines)


def _check_budgets(user_db_id: int, expenses: list[dict]) -> list[str]:
    """Check budget limits after saving expenses. Returns warning strings."""
    from bot.services import database

    warnings = []
    try:
        budgets = database.get_budgets(user_db_id)
        if not budgets:
            return warnings

        expense_date = datetime.strptime(expenses[0]["date"], "%Y-%m-%d")
        month_name = MONTHS_MAPPING[expense_date.month]

        for budget in budgets:
            cat = budget["category"]
            limit_val = float(budget["monthly_limit"])
            usage = database.get_budget_usage(user_db_id, cat, month_name)
            pct = (usage / limit_val * 100) if limit_val > 0 else 0

            display_cat = cat if cat else _strip_markdown(t("budget_total_label"))
            if pct >= 100:
                warnings.append(
                    _strip_markdown(
                        t(
                            "budget_exceeded",
                            category=display_cat,
                            used=f"{usage:.0f}",
                            limit=f"{limit_val:.0f}",
                        )
                    )
                )
            elif pct >= 80:
                warnings.append(
                    _strip_markdown(
                        t(
                            "budget_warning",
                            category=display_cat,
                            pct=f"{pct:.0f}",
                            used=f"{usage:.0f}",
                            limit=f"{limit_val:.0f}",
                        )
                    )
                )
    except Exception:
        pass

    return warnings


# ── command handlers ─────────────────────────────────────────────────


def cmd_add(args):
    """Parse and save expense(s) via AI."""
    from bot.services import ai_parser, database, sheets, storage

    text = " ".join(args.text)
    print(f"Parsing: {text}")

    try:
        expenses = ai_parser.parse_expenses(text)
    except Exception as e:
        print(f"Error parsing expense: {e}")
        return 1

    if not expenses:
        print(_strip_markdown(t("no_expense_found")))
        return 1

    # Preview
    print()
    for i, e in enumerate(expenses, 1):
        prefix = f"{i}. " if len(expenses) > 1 else ""
        indent = "   " if prefix else ""
        print(f"{prefix}Date: {e['date']}")
        print(f"{indent}Amount: {e['amount']} PLN")
        print(f"{indent}Category: {e['category']} > {e['subcategory']}")
        print(f"{indent}Description: {e['description']}")
        if i < len(expenses):
            print()

    # Confirmation
    auto_confirm = args.yes or not sys.stdin.isatty()
    if not auto_confirm:
        try:
            answer = input("\nSave? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 1
        if answer and answer not in ("y", "yes", "t", "tak"):
            print("Cancelled.")
            return 1

    # Save
    try:
        if database.is_available():
            user_db_id = _get_user_id()
            expense_ids = database.save_expenses(user_db_id, expenses, text)
            storage.save_last_saved(
                ALLOWED_USER_ID,
                {"expense_ids": expense_ids, "expenses": expenses},
            )

            try:
                row_indices = sheets.save_expenses_to_sheet(expenses, text)
                for eid, ridx in zip(expense_ids, row_indices):
                    database.mark_synced(eid, ridx)
            except Exception:
                print("(Sheets sync deferred)")

            warnings = _check_budgets(user_db_id, expenses)
            n = len(expenses)
            print(f"\nSaved {n} expense{'s' if n > 1 else ''}!")
            for w in warnings:
                print(w)
        else:
            row_indices = sheets.save_expenses_to_sheet(expenses, text)
            storage.save_last_saved(
                ALLOWED_USER_ID,
                {"row_indices": row_indices, "expenses": expenses},
            )
            n = len(expenses)
            print(f"\nSaved {n} expense{'s' if n > 1 else ''}!")
    except Exception as e:
        print(f"Error saving: {e}")
        return 1

    return 0


def cmd_income(args):
    """Add income entry."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    today = datetime.now().strftime("%Y-%m-%d")
    source = " ".join(args.source)

    try:
        database.save_income(user_db_id, args.amount, source, today, source)
        print(
            _strip_markdown(
                t("income_saved", amount=f"{args.amount:.0f}", source=source)
            )
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


def cmd_summary(args):
    """Show monthly summary by category with subcategory breakdown."""
    from bot.services import database, sheets

    target_month = _resolve_month(args.month)

    totals: dict[str, float] = {}
    sub_totals: dict[str, dict[str, float]] = {}
    count = 0

    try:
        if database.is_available():
            user_db_id = _get_user_id()
            rows = database.get_expenses_by_month(user_db_id, target_month)
            for row in rows:
                amount = float(row["amount"])
                category = row["category"]
                totals[category] = totals.get(category, 0) + amount
                subcategory = row["subcategory"]
                if subcategory:
                    sub_totals.setdefault(category, {})
                    sub_totals[category][subcategory] = (
                        sub_totals[category].get(subcategory, 0) + amount
                    )
                count += 1
        else:
            all_rows = sheets.get_all_rows()
            for row in all_rows:
                if len(row) < 7 or row[6].strip() != target_month:
                    continue
                try:
                    amount = float(row[1].replace(",", "."))
                    category = row[2]
                    totals[category] = totals.get(category, 0) + amount
                    subcategory = row[3] if len(row) > 3 else ""
                    if subcategory:
                        sub_totals.setdefault(category, {})
                        sub_totals[category][subcategory] = (
                            sub_totals[category].get(subcategory, 0) + amount
                        )
                    count += 1
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        print(f"Error: {e}")
        return 1

    if not totals:
        print(f"No expenses for: {target_month}.")
        return 0

    grand_total = sum(totals.values())
    print(f"Summary: {target_month}\n")
    for cat in sorted(totals, key=lambda c: totals[c], reverse=True):
        emoji = CATEGORY_EMOJIS.get(cat, "")
        print(f"  {emoji} {cat}: {totals[cat]:.2f} PLN")
        if cat in sub_totals:
            for sub in sorted(
                sub_totals[cat], key=lambda s: sub_totals[cat][s], reverse=True
            ):
                print(f"      {sub}: {sub_totals[cat][sub]:.2f} PLN")
    print(f"\nTotal: {grand_total:.2f} PLN ({count} entries)")
    return 0


def cmd_last(args):
    """Show recent expenses."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    limit = min(args.n, 50)
    results = database.get_recent_expenses(user_db_id, limit=limit)

    if not results:
        print("No expenses.")
        return 0

    print(f"Last {len(results)} expenses:\n")
    print(_format_expense_list(results))
    return 0


def cmd_search(args):
    """Search expenses by description, category, or original text."""
    _require_db()
    from bot.services import database

    query = " ".join(args.query)
    user_db_id = _get_user_id()
    results = database.search_expenses(user_db_id, query)

    if not results:
        print(f'No results for: "{query}"')
        return 0

    print(f'Results for "{query}":\n')
    print(_format_expense_list(results[:20]))
    if len(results) > 20:
        print(f"\n... +{len(results) - 20} more")
    return 0


def cmd_expenses(args):
    """Filter expenses by date range."""
    _require_db()
    from bot.services import database

    for d, label in [(args.start, "start"), (args.end, "end")]:
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"Error: {label} date must be in YYYY-MM-DD format.")
            return 1

    user_db_id = _get_user_id()
    results = database.get_expenses_by_date_range(user_db_id, args.start, args.end)

    if not results:
        print("No expenses in the given period.")
        return 0

    total = sum(float(r["amount"]) for r in results)
    print(f"Expenses {args.start} — {args.end}:\n")
    print(_format_expense_list(results))
    print(f"\nTotal: {total:.2f} PLN ({len(results)} entries)")
    return 0


def cmd_export(args):
    """Export expenses as CSV (stdout or file)."""
    _require_db()
    from bot.services import database

    target_month = _resolve_month(args.month)
    user_db_id = _get_user_id()
    expenses = database.get_expenses_by_month(user_db_id, target_month)

    if not expenses:
        print(f"No expenses to export for: {target_month}.")
        return 0

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Data", "Kwota", "Kategoria", "Podkategoria", "Opis"])
    for e in expenses:
        writer.writerow(
            [
                str(e["date"]),
                float(e["amount"]),
                e["category"],
                e["subcategory"],
                e["description"],
            ]
        )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output.getvalue())
        print(f"Exported {len(expenses)} expenses to {args.output}")
    else:
        sys.stdout.write(output.getvalue())
    return 0


def cmd_budget(args):
    """Manage monthly budgets (set/list/remove)."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    action = args.budget_action

    if action == "set":
        category = None if args.category.lower() == "total" else args.category
        display = (
            _strip_markdown(t("budget_total_label")) if category is None else category
        )
        database.set_budget(user_db_id, category, args.amount)
        print(f"Budget set: {display} — {args.amount:.0f} PLN/month")
        return 0

    if action == "list":
        budgets = database.get_budgets(user_db_id)
        if not budgets:
            print("No budgets set.")
            return 0

        month_name = MONTHS_MAPPING[datetime.now().month]
        print(f"Budgets for {month_name}:\n")
        for budget in budgets:
            cat = budget["category"]
            limit_val = float(budget["monthly_limit"])
            usage = database.get_budget_usage(user_db_id, cat, month_name)
            pct = (usage / limit_val * 100) if limit_val > 0 else 0
            bar = _build_progress_bar(pct)

            if cat is None:
                display = _strip_markdown(t("budget_total_label"))
                emoji = ""
            else:
                display = cat
                emoji = CATEGORY_EMOJIS.get(cat, "")
            print(
                f"  {emoji} {display}: {bar} {pct:.0f}% ({usage:.0f}/{limit_val:.0f} PLN)"
            )
        return 0

    if action == "remove":
        category = None if args.category.lower() == "total" else args.category
        display = (
            _strip_markdown(t("budget_total_label")) if category is None else category
        )
        database.delete_budget(user_db_id, category)
        print(f"Budget removed: {display}")
        return 0

    return 0


def cmd_chart(args):
    """Generate expense chart and save as PNG."""
    _require_db()
    from bot.services import database
    from bot.utils.formatting import generate_pie_chart, generate_bar_chart

    user_db_id = _get_user_id()
    chart_type = args.type or "pie"
    output_file = args.output or "chart.png"

    if chart_type == "bar":
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
            print("No data for chart.")
            return 0

        title = _strip_markdown(t("chart_bar_title"))
        buf = generate_bar_chart(months_data, title)
    else:
        target_month = _resolve_month(args.month)
        rows = database.get_expenses_by_month(user_db_id, target_month)
        categories_data = {}
        for row in rows:
            cat = row["category"]
            categories_data[cat] = categories_data.get(cat, 0) + float(row["amount"])

        if not categories_data:
            print(f"No data for chart in: {target_month}.")
            return 0

        title = _strip_markdown(t("chart_pie_title", month=target_month))
        buf = generate_pie_chart(categories_data, title)

    with open(output_file, "wb") as f:
        f.write(buf.read())
    print(f"Chart saved to: {output_file}")
    return 0


FREQ_MAP = {
    "codziennie": "daily",
    "daily": "daily",
    "co tydzień": "weekly",
    "co tydzien": "weekly",
    "tygodniowo": "weekly",
    "weekly": "weekly",
    "co miesiąc": "monthly",
    "co miesiac": "monthly",
    "miesięcznie": "monthly",
    "miesiecznie": "monthly",
    "monthly": "monthly",
}


def cmd_recurring(args):
    """Manage recurring expenses (add/list/remove)."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    action = args.recurring_action

    if action == "add":
        freq_input = args.frequency.lower()
        frequency = FREQ_MAP.get(freq_input)
        if not frequency:
            print(f"Error: unknown frequency '{args.frequency}'")
            print("Valid: daily, weekly, monthly, codziennie, tygodniowo, miesięcznie")
            return 1

        description = " ".join(args.description)
        next_due = _calculate_next_due(frequency)

        database.add_recurring(
            user_db_id,
            {
                "amount": args.amount,
                "category": "Inne wydatki",
                "subcategory": "Inne",
                "description": description,
                "frequency": frequency,
                "day_of_month": date.today().day,
                "next_due": str(next_due),
            },
        )
        freq_display = _strip_markdown(t(f"recurring_freq_{frequency}"))
        print(
            f"Added recurring expense: {description} — {args.amount:.0f} PLN ({freq_display})"
        )
        return 0

    if action == "list":
        items = database.get_recurring(user_db_id)
        if not items:
            print("No recurring expenses.")
            return 0

        print("Recurring expenses:\n")
        for item in items:
            freq_display = _strip_markdown(t(f"recurring_freq_{item['frequency']}"))
            print(
                f"  #{item['id']} — {item['description']} — "
                f"{float(item['amount']):.0f} PLN ({freq_display})"
            )
            print(f"      {item['category']} > {item['subcategory']}")
            print(f"      Next: {item['next_due']}")
        return 0

    if action == "remove":
        database.delete_recurring(args.id)
        print(f"Removed recurring expense #{args.id}")
        return 0

    return 0


def cmd_balance(args):
    """Show income vs expenses balance for current month."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    month_name = MONTHS_MAPPING[datetime.now().month]

    expenses = database.get_expenses_by_month(user_db_id, month_name)
    total_expenses = sum(float(e["amount"]) for e in expenses)

    income_items = database.get_income_by_month(user_db_id, month_name)
    total_income = sum(float(i["amount"]) for i in income_items)

    if total_expenses == 0 and total_income == 0:
        print(f"No data for: {month_name}.")
        return 0

    net = total_income - total_expenses
    print(f"Balance: {month_name}\n")
    print(f"  Income:   {total_income:.2f} PLN")
    print(f"  Expenses: {total_expenses:.2f} PLN")
    print(f"  Net:      {net:.2f} PLN")
    return 0


def cmd_categories(args):
    """Display all expense categories."""
    print(_strip_markdown(CATEGORIES_DISPLAY))
    return 0


def cmd_undo(args):
    """Undo last saved expense(s)."""
    from bot.services import storage, database, sheets

    saved = storage.get_last_saved(ALLOWED_USER_ID)
    if not saved:
        print(_strip_markdown(t("nothing_to_undo")))
        return 0

    try:
        expense_ids = saved.get("expense_ids")
        row_indices = saved.get("row_indices")

        if expense_ids and database.is_available():
            database.delete_expenses(expense_ids)
            n = len(expense_ids)
            if row_indices:
                try:
                    sheets.delete_rows(row_indices)
                except Exception:
                    pass
        elif row_indices:
            sheets.delete_rows(row_indices)
            n = len(row_indices)
        else:
            print("Error: no undo data available.")
            return 1

        storage.delete_last_saved(ALLOWED_USER_ID)
        print(f"Undone {n} expense{'s' if n > 1 else ''}.")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


def cmd_lang(args):
    """Switch display language."""
    from bot.services import database

    lang = args.lang
    set_lang(lang)
    if database.is_available():
        try:
            database.set_user_language(ALLOWED_USER_ID, lang)
        except Exception:
            pass
    print(_strip_markdown(t("lang_switched")))
    return 0


def cmd_sync(args):
    """Manually sync unsynced expenses to Google Sheets."""
    _require_db()
    from bot.services import sync

    count = sync.sync_unsynced_to_sheets()
    if count:
        print(f"Synced {count} expense{'s' if count > 1 else ''} to Google Sheets.")
    else:
        print("Nothing to sync.")
    return 0


# ── argument parser ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budzet",
        description="Budget tracker CLI — manage expenses, income, budgets, and more.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # add
    p = sub.add_parser("add", help="Parse and save an expense")
    p.add_argument(
        "text", nargs="+", help="Expense description (e.g. '50 biedronka zakupy')"
    )
    p.add_argument(
        "-y", "--yes", action="store_true", help="Auto-confirm without prompt"
    )

    # income
    p = sub.add_parser("income", help="Add income")
    p.add_argument("amount", type=float, help="Income amount")
    p.add_argument("source", nargs="+", help="Income source description")

    # summary
    p = sub.add_parser("summary", help="Monthly summary by category")
    p.add_argument(
        "month", nargs="?", default=None, help="Month name or number (default: current)"
    )

    # last
    p = sub.add_parser("last", help="Show recent expenses")
    p.add_argument(
        "n", nargs="?", type=int, default=10, help="Number of expenses (default: 10)"
    )

    # search
    p = sub.add_parser("search", help="Search expenses")
    p.add_argument("query", nargs="+", help="Search query")

    # expenses
    p = sub.add_parser("expenses", help="Filter expenses by date range")
    p.add_argument("start", help="Start date (YYYY-MM-DD)")
    p.add_argument("end", help="End date (YYYY-MM-DD)")

    # export
    p = sub.add_parser("export", help="Export expenses as CSV")
    p.add_argument(
        "month", nargs="?", default=None, help="Month name or number (default: current)"
    )
    p.add_argument("-o", "--output", help="Output file (default: stdout)")

    # budget
    p_budget = sub.add_parser("budget", help="Manage monthly budgets")
    budget_sub = p_budget.add_subparsers(dest="budget_action")

    bs = budget_sub.add_parser("set", help="Set a monthly budget")
    bs.add_argument("category", help="Category name (or 'total' for overall)")
    bs.add_argument("amount", type=float, help="Monthly limit in PLN")

    budget_sub.add_parser("list", help="Show budgets with progress bars")

    br = budget_sub.add_parser("remove", help="Remove a budget")
    br.add_argument("category", help="Category name (or 'total')")

    # chart
    p = sub.add_parser("chart", help="Generate expense chart (PNG)")
    p.add_argument(
        "type",
        nargs="?",
        choices=["pie", "bar"],
        default="pie",
        help="Chart type (default: pie)",
    )
    p.add_argument("month", nargs="?", default=None, help="Month (for pie chart)")
    p.add_argument("-o", "--output", help="Output file (default: chart.png)")

    # recurring
    p_rec = sub.add_parser("recurring", help="Manage recurring expenses")
    rec_sub = p_rec.add_subparsers(dest="recurring_action")

    ra = rec_sub.add_parser("add", help="Add a recurring expense")
    ra.add_argument("amount", type=float, help="Amount in PLN")
    ra.add_argument("description", nargs="+", help="Expense description")
    ra.add_argument(
        "-f", "--frequency", required=True, help="Frequency: daily, weekly, monthly"
    )

    rec_sub.add_parser("list", help="List recurring expenses")

    rr = rec_sub.add_parser("remove", help="Remove a recurring expense")
    rr.add_argument("id", type=int, help="Recurring expense ID")

    # balance
    sub.add_parser("balance", help="Show income vs expenses")

    # categories
    sub.add_parser("categories", help="List all categories")

    # undo
    sub.add_parser("undo", help="Undo last saved expense")

    # lang
    p = sub.add_parser("lang", help="Switch language")
    p.add_argument("lang", choices=["pl", "en"], help="Language code")

    # sync
    sub.add_parser("sync", help="Sync unsynced expenses to Google Sheets")

    return parser


# ── entry point ──────────────────────────────────────────────────────

COMMAND_MAP = {
    "add": cmd_add,
    "income": cmd_income,
    "summary": cmd_summary,
    "last": cmd_last,
    "search": cmd_search,
    "expenses": cmd_expenses,
    "export": cmd_export,
    "budget": cmd_budget,
    "chart": cmd_chart,
    "recurring": cmd_recurring,
    "balance": cmd_balance,
    "categories": cmd_categories,
    "undo": cmd_undo,
    "lang": cmd_lang,
    "sync": cmd_sync,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Load user language from DB if available
    from bot.services import database

    if database.is_available():
        lang = database.get_user_language(ALLOWED_USER_ID)
        if lang:
            set_lang(lang)

    # Show help for subcommands missing their action
    if args.command == "budget" and not getattr(args, "budget_action", None):
        parser.parse_args(["budget", "--help"])
        return
    if args.command == "recurring" and not getattr(args, "recurring_action", None):
        parser.parse_args(["recurring", "--help"])
        return

    handler = COMMAND_MAP.get(args.command)
    if handler:
        exit_code = handler(args)
        sys.exit(exit_code or 0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
