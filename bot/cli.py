"""CLI interface for budzet-bot — full command parity with the Telegram bot."""

import argparse
import csv
import json as _json
import logging
import re
import sys
from datetime import datetime, date, timedelta
from io import StringIO

logger = logging.getLogger(__name__)

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import box

from bot.config import ALLOWED_USER_ID, MONTHS_MAPPING, MONTH_NAME_TO_NUM
from bot.categories import CATEGORIES, CATEGORIES_DISPLAY, CATEGORY_EMOJIS, INCOME_CATEGORIES, INCOME_CATEGORY_EMOJIS
from bot.i18n import t, set_lang

console = Console()


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

    console.print(f"[bold red]Error:[/bold red] unrecognized month '{month_arg}'")
    sys.exit(1)


def _require_db():
    """Exit with error if PostgreSQL is not available."""
    from bot.services import database

    if not database.is_available():
        console.print(f"[bold red]Error:[/bold red] {_strip_markdown(t('db_required'))}")
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
    """Format a list of expense dicts for terminal output (plain text)."""
    lines = []
    for i, e in enumerate(expenses, 1):
        amount = float(e["amount"])
        lines.append(
            f"{i}. {e['date']}  {amount:.2f} PLN\n"
            f"   {e['category']} > {e['subcategory']}\n"
            f"   {e['description']}"
        )
    return "\n".join(lines)


def _json_mode(args) -> bool:
    """Return True if --json flag is set, safely handling None args."""
    return bool(getattr(args, "output_json", False))


def _normalize_expense(e: dict) -> dict:
    """Make an expense dict JSON-serializable (date→str, Decimal→float)."""
    result = dict(e)
    for key in ("date", "created_at"):
        if key in result and hasattr(result[key], "isoformat"):
            result[key] = result[key].isoformat()
    if "amount" in result:
        result["amount"] = float(result["amount"])
    return result


def _rich_expense_table(expenses: list[dict], title: str) -> Table:
    """Return a rich Table for a list of expense dicts."""
    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Date", style="white", width=12)
    table.add_column("Amount PLN", justify="right", style="yellow")
    table.add_column("Category", style="cyan", no_wrap=False)
    table.add_column("Description", style="white")
    for i, e in enumerate(expenses, 1):
        table.add_row(
            str(i),
            str(e["date"]),
            f"{float(e['amount']):.2f}",
            f"{e['category']} > {e['subcategory']}",
            e["description"],
        )
    return table


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
    console.print(f"Parsing: {text}")

    try:
        expenses = ai_parser.parse_expenses(text)
    except Exception as e:
        console.print(f"[bold red]Error parsing expense:[/bold red] {e}")
        return 1

    if not expenses:
        console.print(_strip_markdown(t("no_expense_found")))
        return 1

    # Preview
    console.print()
    for i, e in enumerate(expenses, 1):
        prefix = f"{i}. " if len(expenses) > 1 else ""
        indent = "   " if prefix else ""
        console.print(f"{prefix}Date: {e['date']}")
        console.print(f"{indent}Amount: [yellow]{e['amount']} PLN[/yellow]")
        console.print(f"{indent}Category: [cyan]{e['category']} > {e['subcategory']}[/cyan]")
        console.print(f"{indent}Description: {e['description']}")
        if i < len(expenses):
            console.print()

    # --json implies auto-confirm (agents don't want interactive prompts)
    auto_confirm = args.yes or not sys.stdin.isatty() or _json_mode(args)
    if not auto_confirm:
        try:
            answer = input("\nSave? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\nCancelled.")
            return 1
        if answer and answer not in ("y", "yes", "t", "tak"):
            console.print("Cancelled.")
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
                console.print("[dim](Sheets sync deferred)[/dim]")

            warnings = _check_budgets(user_db_id, expenses)
            n = len(expenses)
            msg = f"Saved {n} expense{'s' if n > 1 else ''}!"
            if _json_mode(args):
                print(_json.dumps({"status": "ok", "message": msg, "count": n}, ensure_ascii=False))
            else:
                console.print(f"\n[bold green]{msg}[/bold green]")
                for w in warnings:
                    console.print(w)
        else:
            row_indices = sheets.save_expenses_to_sheet(expenses, text)
            storage.save_last_saved(
                ALLOWED_USER_ID,
                {"row_indices": row_indices, "expenses": expenses},
            )
            n = len(expenses)
            msg = f"Saved {n} expense{'s' if n > 1 else ''}!"
            if _json_mode(args):
                print(_json.dumps({"status": "ok", "message": msg, "count": n}, ensure_ascii=False))
            else:
                console.print(f"\n[bold green]{msg}[/bold green]")
    except Exception as e:
        if _json_mode(args):
            print(_json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[bold red]Error saving:[/bold red] {e}")
        return 1

    return 0


def cmd_income(args):
    """Add income entry."""
    _require_db()
    from bot.services import database, sheets

    user_db_id = _get_user_id()
    today = datetime.now().strftime("%Y-%m-%d")
    source = " ".join(args.source)
    category = args.category

    if not category:
        console.print("\n[bold]Wybierz kategorię przychodu:[/bold]")
        for i, cat in enumerate(INCOME_CATEGORIES, 1):
            emoji = INCOME_CATEGORY_EMOJIS.get(cat, "💰")
            console.print(f"  {i}. {emoji} {cat}")
        try:
            choice = int(console.input("\nNumer kategorii: ").strip()) - 1
            if 0 <= choice < len(INCOME_CATEGORIES):
                category = INCOME_CATEGORIES[choice]
            else:
                console.print("[red]Nieprawidłowy numer kategorii.[/red]")
                return 1
        except (ValueError, KeyboardInterrupt):
            console.print("[red]Anulowano.[/red]")
            return 1

    try:
        database.save_income(user_db_id, args.amount, source, today, source, category)

        # Sync to Sheets (best-effort)
        try:
            sheets.save_income_to_sheet({
                "date": today,
                "amount": args.amount,
                "category": category,
                "source": source,
            })
        except Exception as e:
            logger.warning(f"Income Sheets sync failed: {e}")

        emoji = INCOME_CATEGORY_EMOJIS.get(category, "💰")
        if _json_mode(args):
            print(_json.dumps({
                "status": "ok",
                "amount": args.amount,
                "source": source,
                "category": category,
            }, ensure_ascii=False))
        else:
            console.print(f"[bold green]✅ Zapisano przychód: {args.amount:.0f} PLN — {source}[/bold green]")
            console.print(f"   Kategoria: {emoji} {category}")
    except Exception as e:
        if _json_mode(args):
            print(_json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    return 0


def cmd_incomes(args):
    """Show income list for current (or given) month."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    target_month = _resolve_month(args.month) if hasattr(args, "month") and args.month else MONTHS_MAPPING[datetime.now().month]

    income_items = database.get_income_by_month(user_db_id, target_month)

    if _json_mode(args):
        data = [
            {
                "id": item["id"],
                "amount": float(item["amount"]),
                "source": item["source"],
                "category": item.get("category"),
                "date": str(item["date"]),
            }
            for item in income_items
        ]
        print(_json.dumps({"month": target_month, "income": data}, ensure_ascii=False, indent=2))
        return 0

    if not income_items:
        console.print(f"Brak przychodów za: {target_month}.")
        return 0

    table = Table(title=f"Przychody: {target_month}", border_style="blue")
    table.add_column("Data", style="dim", width=12)
    table.add_column("Kategoria", style="cyan")
    table.add_column("Kwota (PLN)", justify="right", style="green")
    table.add_column("Źródło")

    total = 0.0
    for item in income_items:
        amount = float(item["amount"])
        total += amount
        category = item.get("category") or "—"
        emoji = INCOME_CATEGORY_EMOJIS.get(category, "💰")
        table.add_row(
            str(item["date"]),
            f"{emoji} {category}",
            f"{amount:.2f}",
            item["source"],
        )

    console.print(table)
    console.print(f"\n[bold green]Razem: {total:.2f} PLN[/bold green]")
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
                    amount = float(row[1].replace("\xa0", "").replace(" ", "").replace(",", "."))
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
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1

    if not totals:
        console.print(f"No expenses for: {target_month}.")
        return 0

    grand_total = sum(totals.values())
    sorted_cats = sorted(totals, key=lambda c: totals[c], reverse=True)

    if _json_mode(args):
        data = {
            "month": target_month,
            "total": round(grand_total, 2),
            "count": count,
            "categories": [
                {
                    "name": cat,
                    "amount": round(totals[cat], 2),
                    "pct_of_total": round(totals[cat] / grand_total * 100, 1),
                    "subcategories": [
                        {"name": sub, "amount": round(amt, 2)}
                        for sub, amt in sorted(
                            sub_totals.get(cat, {}).items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )
                    ],
                }
                for cat in sorted_cats
            ],
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("Category", style="white", min_width=24)
    table.add_column("Amount PLN", justify="right", style="yellow")
    table.add_column("% of total", justify="right", style="dim")

    for cat in sorted_cats:
        emoji = CATEGORY_EMOJIS.get(cat, "")
        pct = totals[cat] / grand_total * 100
        table.add_row(f"{emoji} {cat}", f"{totals[cat]:.2f}", f"{pct:.1f}%")
        for sub, amt in sorted(
            sub_totals.get(cat, {}).items(), key=lambda x: x[1], reverse=True
        ):
            sub_pct = amt / grand_total * 100
            table.add_row(f"  └ {sub}", f"{amt:.2f}", f"{sub_pct:.1f}%", style="dim")

    table.add_section()
    table.add_row(
        f"[bold]TOTAL ({count} entries)[/bold]",
        f"[bold yellow]{grand_total:.2f}[/bold yellow]",
        "[bold]100%[/bold]",
    )

    console.print(Panel(table, title=f"[bold]Summary: {target_month}[/bold]", border_style="blue"))
    return 0


def cmd_last(args):
    """Show recent expenses."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    limit = min(args.n, 50)
    results = database.get_recent_expenses(user_db_id, limit=limit)

    if not results:
        console.print("No expenses.")
        return 0

    if _json_mode(args):
        print(_json.dumps({"expenses": [_normalize_expense(e) for e in results]}, ensure_ascii=False, indent=2))
        return 0

    console.print(_rich_expense_table(results, f"Last {len(results)} expenses"))
    return 0


def cmd_search(args):
    """Search expenses by description, category, or original text."""
    _require_db()
    from bot.services import database

    query = " ".join(args.query)
    user_db_id = _get_user_id()
    results = database.search_expenses(user_db_id, query)

    if not results:
        console.print(f'No results for: "{query}"')
        return 0

    display = results[:20]

    if _json_mode(args):
        data = {
            "query": query,
            "count": len(results),
            "expenses": [_normalize_expense(e) for e in display],
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    console.print(_rich_expense_table(display, f'Results for "{query}" ({len(results)} found)'))
    if len(results) > 20:
        console.print(f"[dim]... +{len(results) - 20} more[/dim]")
    return 0


def cmd_expenses(args):
    """Filter expenses by date range."""
    _require_db()
    from bot.services import database

    for d, label in [(args.start, "start"), (args.end, "end")]:
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            console.print(f"[bold red]Error:[/bold red] {label} date must be in YYYY-MM-DD format.")
            return 1

    user_db_id = _get_user_id()
    results = database.get_expenses_by_date_range(user_db_id, args.start, args.end)

    if not results:
        console.print("No expenses in the given period.")
        return 0

    total = sum(float(r["amount"]) for r in results)

    if _json_mode(args):
        data = {
            "start": args.start,
            "end": args.end,
            "total": round(total, 2),
            "count": len(results),
            "expenses": [_normalize_expense(e) for e in results],
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    table = _rich_expense_table(results, f"Expenses {args.start} — {args.end}")
    table.add_section()
    table.add_row("", "", f"[bold yellow]{total:.2f}[/bold yellow]", f"[bold]TOTAL ({len(results)})[/bold]", "")
    console.print(table)
    return 0


def cmd_export(args):
    """Export expenses as CSV (stdout or file)."""
    _require_db()
    from bot.services import database

    target_month = _resolve_month(args.month)
    user_db_id = _get_user_id()
    expenses = database.get_expenses_by_month(user_db_id, target_month)

    if not expenses:
        console.print(f"No expenses to export for: {target_month}.")
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
        console.print(f"Exported {len(expenses)} expenses to {args.output}")
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
        msg = f"Budget set: {display} — {args.amount:.0f} PLN/month"
        if _json_mode(args):
            print(_json.dumps({"status": "ok", "message": msg}, ensure_ascii=False))
        else:
            console.print(f"[bold green]{msg}[/bold green]")
        return 0

    if action == "list":
        budgets = database.get_budgets(user_db_id)
        if not budgets:
            msg = "No budgets set."
            if _json_mode(args):
                print(_json.dumps({"budgets": []}, ensure_ascii=False))
            else:
                console.print(msg)
            return 0

        month_name = MONTHS_MAPPING[datetime.now().month]
        budget_rows = []
        for budget in budgets:
            cat = budget["category"]
            limit_val = float(budget["monthly_limit"])
            usage = database.get_budget_usage(user_db_id, cat, month_name)
            pct = (usage / limit_val * 100) if limit_val > 0 else 0
            budget_rows.append({
                "category": cat or "total",
                "monthly_limit": round(limit_val, 2),
                "used": round(usage, 2),
                "pct": round(pct, 1),
            })

        if _json_mode(args):
            print(_json.dumps({"month": month_name, "budgets": budget_rows}, ensure_ascii=False, indent=2))
            return 0

        table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        table.add_column("Category", style="white", min_width=20)
        table.add_column("Limit PLN", justify="right", style="dim")
        table.add_column("Used PLN", justify="right", style="yellow")
        table.add_column("Progress", min_width=22)
        table.add_column("Used %", justify="right")

        for row, budget in zip(budget_rows, budgets):
            cat = budget["category"]
            pct = row["pct"]
            if pct >= 100:
                bar_style = "bold red"
            elif pct >= 80:
                bar_style = "yellow"
            else:
                bar_style = "green"

            bar = _build_progress_bar(pct, width=15)
            display = _strip_markdown(t("budget_total_label")) if cat is None else cat
            emoji = "" if cat is None else CATEGORY_EMOJIS.get(cat, "")

            table.add_row(
                f"{emoji} {display}",
                f"{row['monthly_limit']:.0f}",
                f"{row['used']:.0f}",
                f"[{bar_style}]{bar}[/{bar_style}]",
                f"[{bar_style}]{pct:.0f}%[/{bar_style}]",
            )

        console.print(Panel(table, title=f"[bold]Budgets: {month_name}[/bold]", border_style="blue"))
        return 0

    if action == "remove":
        category = None if args.category.lower() == "total" else args.category
        display = (
            _strip_markdown(t("budget_total_label")) if category is None else category
        )
        database.delete_budget(user_db_id, category)
        msg = f"Budget removed: {display}"
        if _json_mode(args):
            print(_json.dumps({"status": "ok", "message": msg}, ensure_ascii=False))
        else:
            console.print(f"[bold green]{msg}[/bold green]")
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
            console.print("No data for chart.")
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
            console.print(f"No data for chart in: {target_month}.")
            return 0

        title = _strip_markdown(t("chart_pie_title", month=target_month))
        buf = generate_pie_chart(categories_data, title)

    with open(output_file, "wb") as f:
        f.write(buf.read())
    console.print(f"[bold green]Chart saved to:[/bold green] {output_file}")
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
            console.print(f"[bold red]Error:[/bold red] unknown frequency '{args.frequency}'")
            console.print("Valid: daily, weekly, monthly, codziennie, tygodniowo, miesięcznie")
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
        msg = f"Added recurring expense: {description} — {args.amount:.0f} PLN ({freq_display})"
        if _json_mode(args):
            print(_json.dumps({"status": "ok", "message": msg}, ensure_ascii=False))
        else:
            console.print(f"[bold green]{msg}[/bold green]")
        return 0

    if action == "list":
        items = database.get_recurring(user_db_id)
        if not items:
            if _json_mode(args):
                print(_json.dumps({"items": []}, ensure_ascii=False))
            else:
                console.print("No recurring expenses.")
            return 0

        if _json_mode(args):
            data = {
                "items": [
                    {
                        "id": item["id"],
                        "description": item["description"],
                        "amount": float(item["amount"]),
                        "category": item["category"],
                        "subcategory": item["subcategory"],
                        "frequency": item["frequency"],
                        "next_due": str(item["next_due"]),
                    }
                    for item in items
                ]
            }
            print(_json.dumps(data, ensure_ascii=False, indent=2))
            return 0

        table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        table.add_column("ID", style="dim", width=4)
        table.add_column("Description", style="white")
        table.add_column("Amount PLN", justify="right", style="yellow")
        table.add_column("Frequency", style="cyan")
        table.add_column("Next Due", style="white")

        for item in items:
            freq_display = _strip_markdown(t(f"recurring_freq_{item['frequency']}"))
            table.add_row(
                f"#{item['id']}",
                item["description"],
                f"{float(item['amount']):.0f}",
                freq_display,
                str(item["next_due"]),
            )

        console.print(Panel(table, title="[bold]Recurring Expenses[/bold]", border_style="blue"))
        return 0

    if action == "remove":
        database.delete_recurring(args.id)
        msg = f"Removed recurring expense #{args.id}"
        if _json_mode(args):
            print(_json.dumps({"status": "ok", "message": msg}, ensure_ascii=False))
        else:
            console.print(f"[bold green]{msg}[/bold green]")
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
        console.print(f"No data for: {month_name}.")
        return 0

    net = total_income - total_expenses

    if _json_mode(args):
        data = {
            "month": month_name,
            "income": round(total_income, 2),
            "expenses": round(total_expenses, 2),
            "net": round(net, 2),
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    net_color = "bold green" if net >= 0 else "bold red"
    panel_content = (
        f"[green]Income:[/green]   {total_income:>10.2f} PLN\n"
        f"[red]Expenses:[/red] {total_expenses:>10.2f} PLN\n"
        f"{'─' * 28}\n"
        f"[{net_color}]Net:[/{net_color}]      {net:>10.2f} PLN"
    )
    console.print(Panel(panel_content, title=f"[bold]Balance: {month_name}[/bold]", border_style="blue"))
    return 0


def cmd_categories(args):
    """Display all expense categories."""
    if _json_mode(args):
        data = {
            "categories": [
                {
                    "name": cat,
                    "emoji": CATEGORY_EMOJIS.get(cat, ""),
                    "subcategories": list(subs),
                }
                for cat, subs in CATEGORIES.items()
            ]
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    tree = Tree("[bold cyan]Expense Categories[/bold cyan]")
    for cat, subs in CATEGORIES.items():
        emoji = CATEGORY_EMOJIS.get(cat, "")
        branch = tree.add(f"{emoji} [bold]{cat}[/bold]")
        for sub in subs:
            branch.add(f"[dim]{sub}[/dim]")
    console.print(tree)
    return 0


def cmd_undo(args):
    """Undo last saved expense(s)."""
    from bot.services import storage, database, sheets

    saved = storage.get_last_saved(ALLOWED_USER_ID)
    if not saved:
        msg = _strip_markdown(t("nothing_to_undo"))
        if _json_mode(args):
            print(_json.dumps({"status": "ok", "message": msg}, ensure_ascii=False))
        else:
            console.print(msg)
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
            msg = "Error: no undo data available."
            if _json_mode(args):
                print(_json.dumps({"status": "error", "message": msg}, ensure_ascii=False))
            else:
                console.print(f"[bold red]{msg}[/bold red]")
            return 1

        storage.delete_last_saved(ALLOWED_USER_ID)
        msg = f"Undone {n} expense{'s' if n > 1 else ''}."
        if _json_mode(args):
            print(_json.dumps({"status": "ok", "message": msg, "count": n}, ensure_ascii=False))
        else:
            console.print(f"[bold green]{msg}[/bold green]")
    except Exception as e:
        if _json_mode(args):
            print(_json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[bold red]Error:[/bold red] {e}")
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
    msg = _strip_markdown(t("lang_switched"))
    if _json_mode(args):
        print(_json.dumps({"status": "ok", "message": msg, "lang": lang}, ensure_ascii=False))
    else:
        console.print(msg)
    return 0


def cmd_sync(args):
    """Manually sync unsynced expenses to Google Sheets."""
    _require_db()
    from bot.services import sync

    count = sync.sync_unsynced_to_sheets()
    if count:
        msg = f"Synced {count} expense{'s' if count > 1 else ''} to Google Sheets."
    else:
        msg = "Nothing to sync."

    if _json_mode(args):
        print(_json.dumps({"status": "ok", "message": msg, "count": count}, ensure_ascii=False))
    else:
        console.print(f"[bold green]{msg}[/bold green]" if count else msg)
    return 0


def cmd_import_sheets(args):
    """Import all expenses from Google Sheets into the database."""
    _require_db()
    from bot.services import database, sheets
    from bot.config import ALLOWED_USER_ID

    user_db_id = database.get_or_create_user(ALLOWED_USER_ID)

    console.print("Fetching rows from Google Sheets...")
    all_rows = sheets.get_all_rows()

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

            # Validate date
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
        except (ValueError, IndexError) as e:
            skipped += 1
            if args.verbose:
                console.print(f"  [dim]Skipped row: {row[:3]}... ({e})[/dim]")
            continue

    msg = f"Imported {imported} expenses into database. Skipped {skipped} rows."
    if _json_mode(args):
        print(_json.dumps({"status": "ok", "message": msg, "imported": imported, "skipped": skipped}, ensure_ascii=False))
    else:
        console.print(f"[bold green]{msg}[/bold green]")
    return 0


def cmd_dashboard(args):
    """At-a-glance overview of current month."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    now = datetime.now()
    month_name = MONTHS_MAPPING[now.month]

    # Fetch all data
    expenses = database.get_expenses_by_month(user_db_id, month_name)
    totals: dict[str, float] = {}
    for e in expenses:
        cat = e["category"]
        totals[cat] = totals.get(cat, 0) + float(e["amount"])
    grand_total = sum(totals.values())

    budgets = database.get_budgets(user_db_id)
    budget_map = {b["category"]: float(b["monthly_limit"]) for b in budgets}

    recent = database.get_recent_expenses(user_db_id, limit=5)

    income_items = database.get_income_by_month(user_db_id, month_name)
    total_income = sum(float(i["amount"]) for i in income_items)
    net = total_income - grand_total

    if _json_mode(args):
        data = {
            "month": month_name,
            "year": now.year,
            "summary": {
                "total_expenses": round(grand_total, 2),
                "total_income": round(total_income, 2),
                "net": round(net, 2),
                "expense_count": len(expenses),
            },
            "categories": [
                {
                    "name": cat,
                    "amount": round(totals[cat], 2),
                    "budget_limit": budget_map.get(cat),
                    "budget_pct": (
                        round(totals[cat] / budget_map[cat] * 100, 1)
                        if cat in budget_map and budget_map[cat] > 0
                        else None
                    ),
                }
                for cat in sorted(totals, key=lambda c: totals[c], reverse=True)
            ],
            "recent_expenses": [_normalize_expense(e) for e in recent],
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    console.print(f"\n[bold cyan]Budget Dashboard — {month_name} {now.year}[/bold cyan]\n")

    # Category summary table with budget progress
    cat_table = Table(
        title="Category Summary",
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE_HEAVY,
    )
    cat_table.add_column("Category", style="white", min_width=22)
    cat_table.add_column("Spent PLN", justify="right", style="yellow")
    cat_table.add_column("Limit PLN", justify="right", style="dim")
    cat_table.add_column("Progress", min_width=17)
    cat_table.add_column("Used %", justify="right")

    for cat in sorted(totals, key=lambda c: totals[c], reverse=True):
        emoji = CATEGORY_EMOJIS.get(cat, "")
        spent = totals[cat]
        limit = budget_map.get(cat)
        if limit and limit > 0:
            pct = spent / limit * 100
            bar = _build_progress_bar(pct, width=12)
            if pct >= 100:
                color = "bold red"
            elif pct >= 80:
                color = "yellow"
            else:
                color = "green"
            progress_str = f"[{color}]{bar}[/{color}]"
            pct_str = f"[{color}]{pct:.0f}%[/{color}]"
            limit_str = f"{limit:.0f}"
        else:
            progress_str = "[dim]no budget[/dim]"
            pct_str = "[dim]—[/dim]"
            limit_str = "[dim]—[/dim]"
        cat_table.add_row(
            f"{emoji} {cat}", f"{spent:.2f}", limit_str, progress_str, pct_str
        )

    cat_table.add_section()
    cat_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold yellow]{grand_total:.2f}[/bold yellow]",
        "",
        "",
        "",
    )
    console.print(cat_table)
    console.print()

    # Recent expenses (compact)
    recent_table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
    )
    recent_table.add_column("Date", style="white", width=12)
    recent_table.add_column("Amount", justify="right", style="yellow")
    recent_table.add_column("Category", style="cyan")
    recent_table.add_column("Description", style="white")
    for e in recent:
        recent_table.add_row(
            str(e["date"]),
            f"{float(e['amount']):.2f}",
            e["category"],
            e["description"],
        )

    # Balance panel
    net_color = "bold green" if net >= 0 else "bold red"
    balance_text = (
        f"[green]Income:[/green]   {total_income:>10.2f} PLN\n"
        f"[red]Expenses:[/red] {grand_total:>10.2f} PLN\n"
        f"{'─' * 28}\n"
        f"[{net_color}]Net:[/{net_color}]      {net:>10.2f} PLN"
    )

    console.print(
        Columns([
            Panel(recent_table, title="[bold]Recent Expenses[/bold]", border_style="dim"),
            Panel(balance_text, title="[bold]Balance[/bold]", border_style="blue", width=40),
        ])
    )
    console.print()
    return 0


def cmd_stats(args):
    """Spending analytics: monthly trends and top categories."""
    _require_db()
    from bot.services import database

    user_db_id = _get_user_id()
    now = datetime.now()
    n_months = max(1, min(args.months, 24))

    # Build monthly data (oldest first)
    monthly_data = []
    for i in range(n_months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        month_name = MONTHS_MAPPING[m]
        rows = database.get_expenses_by_month(user_db_id, month_name)
        # Filter by year (get_expenses_by_month matches month name only, not year)
        rows = [r for r in rows if str(r["date"]).startswith(str(y))]
        by_cat: dict[str, float] = {}
        for r in rows:
            by_cat[r["category"]] = by_cat.get(r["category"], 0) + float(r["amount"])
        monthly_data.append({
            "month": month_name,
            "year": y,
            "month_num": m,
            "total": round(sum(by_cat.values()), 2),
            "by_category": by_cat,
        })

    # YTD by category (current calendar year only)
    ytd_by_cat: dict[str, float] = {}
    for entry in monthly_data:
        if entry["year"] == now.year:
            for cat, amt in entry["by_category"].items():
                ytd_by_cat[cat] = ytd_by_cat.get(cat, 0) + amt
    ytd_total = sum(ytd_by_cat.values())
    top5_ytd = sorted(ytd_by_cat.items(), key=lambda x: x[1], reverse=True)[:5]

    # Daily average for current month
    days_elapsed = now.day
    current_total = monthly_data[-1]["total"] if monthly_data else 0
    daily_avg = current_total / days_elapsed if days_elapsed > 0 else 0

    if _json_mode(args):
        data = {
            "months_analyzed": n_months,
            "monthly_trend": [
                {
                    "month": d["month"],
                    "year": d["year"],
                    "total": d["total"],
                    "vs_previous": round(d["total"] - monthly_data[i - 1]["total"], 2) if i > 0 else None,
                }
                for i, d in enumerate(monthly_data)
            ],
            "ytd_top_categories": [
                {
                    "category": cat,
                    "total": round(amt, 2),
                    "pct_of_ytd": round(amt / ytd_total * 100, 1) if ytd_total > 0 else 0,
                }
                for cat, amt in top5_ytd
            ],
            "current_month_daily_avg": round(daily_avg, 2),
        }
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    console.print(f"\n[bold cyan]Spending Stats — last {n_months} months[/bold cyan]\n")

    # Monthly trend table
    trend_table = Table(
        title="Monthly Trend",
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE_HEAVY,
    )
    trend_table.add_column("Month", style="white", min_width=14)
    trend_table.add_column("Year", style="dim", width=6)
    trend_table.add_column("Total PLN", justify="right", style="yellow")
    trend_table.add_column("vs Previous", justify="right")

    for i, d in enumerate(monthly_data):
        if i == 0:
            vs_str = "[dim]—[/dim]"
        else:
            diff = d["total"] - monthly_data[i - 1]["total"]
            sign = "+" if diff >= 0 else ""
            color = "red" if diff > 0 else "green"
            vs_str = f"[{color}]{sign}{diff:.0f}[/{color}]"

        is_current = d["month_num"] == now.month and d["year"] == now.year
        if is_current:
            trend_table.add_row(
                f"[bold]{d['month']}[/bold]",
                f"[bold]{d['year']}[/bold]",
                f"[bold yellow]{d['total']:.2f}[/bold yellow]",
                vs_str,
            )
        else:
            trend_table.add_row(d["month"], str(d["year"]), f"{d['total']:.2f}", vs_str)

    console.print(trend_table)
    console.print()

    # Top 5 YTD categories
    if top5_ytd:
        top_table = Table(
            title=f"Top 5 Categories (YTD {now.year})",
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
        )
        top_table.add_column("#", style="dim", width=3)
        top_table.add_column("Category", style="cyan")
        top_table.add_column("Total PLN", justify="right", style="yellow")
        top_table.add_column("% of YTD", justify="right", style="dim")

        for rank, (cat, amt) in enumerate(top5_ytd, 1):
            emoji = CATEGORY_EMOJIS.get(cat, "")
            pct = amt / ytd_total * 100 if ytd_total > 0 else 0
            top_table.add_row(str(rank), f"{emoji} {cat}", f"{amt:.2f}", f"{pct:.1f}%")

        console.print(top_table)
        console.print()

    # Daily average panel
    console.print(
        Panel(
            f"[yellow]{daily_avg:.2f} PLN[/yellow] / day\n"
            f"[dim]({days_elapsed} days elapsed in {monthly_data[-1]['month'] if monthly_data else '—'})[/dim]",
            title="[bold]Daily Average (This Month)[/bold]",
            border_style="blue",
            width=44,
        )
    )
    console.print()
    return 0


# ── argument parser ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budzet",
        description="Budget tracker CLI — manage expenses, income, budgets, and more.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output data as JSON (for agents/scripting)",
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
    p.add_argument("-c", "--category", choices=INCOME_CATEGORIES, default=None,
                   metavar="CATEGORY", help=f"Income category ({', '.join(INCOME_CATEGORIES)})")

    # incomes
    p = sub.add_parser("incomes", help="Show income list for current month")
    p.add_argument("month", nargs="?", default=None, help="Month name or number (default: current)")

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

    # import-sheets
    p = sub.add_parser("import-sheets", help="Import expenses from Google Sheets into DB")
    p.add_argument("-v", "--verbose", action="store_true", help="Show skipped rows")

    # dashboard
    sub.add_parser("dashboard", help="At-a-glance overview of current month")

    # stats
    p = sub.add_parser("stats", help="Spending analytics: trends and top categories")
    p.add_argument(
        "months",
        nargs="?",
        type=int,
        default=6,
        help="Number of months to analyze (default: 6)",
    )

    return parser


# ── entry point ──────────────────────────────────────────────────────

COMMAND_MAP = {
    "add": cmd_add,
    "income": cmd_income,
    "incomes": cmd_incomes,
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
    "import-sheets": cmd_import_sheets,
    "dashboard": cmd_dashboard,
    "stats": cmd_stats,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        console.print("[bold]budzet[/bold] — budget tracker CLI\n")
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
