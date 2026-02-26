"""Tests for the CLI interface."""

import sys
from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest

# Pre-import service submodules so they're registered as attributes on bot.services
# (required for unittest.mock.patch to find them)
import bot.services.database
import bot.services.sheets
import bot.services.storage
import bot.services.ai_parser
import bot.services.sync

from bot.cli import (
    build_parser,
    _strip_markdown,
    _resolve_month,
    _build_progress_bar,
    _calculate_next_due,
    _format_expense_list,
    cmd_categories,
    cmd_add,
    cmd_summary,
    cmd_last,
    cmd_search,
    cmd_expenses,
    cmd_export,
    cmd_undo,
    cmd_lang,
    cmd_sync,
    cmd_income,
    cmd_balance,
    main,
)


# ── helper function tests ───────────────────────────────────────────


class TestStripMarkdown:
    def test_removes_bold(self):
        assert _strip_markdown("*bold text*") == "bold text"

    def test_removes_backticks(self):
        assert _strip_markdown("`code`") == "code"

    def test_removes_mixed(self):
        assert _strip_markdown("*bold* and `code`") == "bold and code"

    def test_plain_text_unchanged(self):
        assert _strip_markdown("no formatting") == "no formatting"

    def test_empty_string(self):
        assert _strip_markdown("") == ""


class TestResolveMonth:
    def test_none_returns_current_month(self):
        from bot.config import MONTHS_MAPPING

        expected = MONTHS_MAPPING[datetime.now().month]
        assert _resolve_month(None) == expected

    def test_polish_month_name(self):
        assert _resolve_month("styczeń") == "Styczeń"

    def test_partial_polish_name(self):
        assert _resolve_month("sty") == "Styczeń"

    def test_case_insensitive(self):
        assert _resolve_month("LUTY") == "Luty"

    def test_month_number(self):
        assert _resolve_month("3") == "Marzec"

    def test_month_number_12(self):
        assert _resolve_month("12") == "Grudzień"

    def test_invalid_exits(self):
        with pytest.raises(SystemExit):
            _resolve_month("invalid_month")


class TestBuildProgressBar:
    def test_zero_percent(self):
        bar = _build_progress_bar(0, width=10)
        assert bar == "[" + "\u2591" * 10 + "]"

    def test_hundred_percent(self):
        bar = _build_progress_bar(100, width=10)
        assert bar == "[" + "\u2588" * 10 + "]"

    def test_fifty_percent(self):
        bar = _build_progress_bar(50, width=10)
        assert bar == "[" + "\u2588" * 5 + "\u2591" * 5 + "]"

    def test_over_hundred_capped(self):
        bar = _build_progress_bar(150, width=10)
        assert bar == "[" + "\u2588" * 10 + "]"

    def test_default_width(self):
        bar = _build_progress_bar(50)
        assert len(bar) == 22  # 20 chars + 2 brackets


class TestCalculateNextDue:
    def test_daily(self):
        from datetime import timedelta

        result = _calculate_next_due("daily")
        assert result == date.today() + timedelta(days=1)

    def test_weekly(self):
        from datetime import timedelta

        result = _calculate_next_due("weekly")
        assert result == date.today() + timedelta(weeks=1)

    def test_monthly(self):
        result = _calculate_next_due("monthly")
        assert result > date.today()

    def test_unknown_defaults_to_30_days(self):
        from datetime import timedelta

        result = _calculate_next_due("unknown")
        assert result == date.today() + timedelta(days=30)


class TestFormatExpenseList:
    def test_single_expense(self):
        expenses = [
            {
                "date": "2026-02-15",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            }
        ]
        result = _format_expense_list(expenses)
        assert "50.00 PLN" in result
        assert "biedronka" in result
        assert "Jedzenie > Jedzenie dom" in result

    def test_multiple_expenses(self):
        expenses = [
            {
                "date": "2026-02-15",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            },
            {
                "date": "2026-02-16",
                "amount": 120.0,
                "category": "Rozrywka",
                "subcategory": "Siłownia / Basen",
                "description": "karnet",
            },
        ]
        result = _format_expense_list(expenses)
        assert "1." in result
        assert "2." in result
        assert "biedronka" in result
        assert "karnet" in result


# ── argument parsing tests ───────────────────────────────────────────


class TestParser:
    def setup_method(self):
        self.parser = build_parser()

    def test_add_basic(self):
        args = self.parser.parse_args(["add", "50", "biedronka"])
        assert args.command == "add"
        assert args.text == ["50", "biedronka"]
        assert not args.yes

    def test_add_with_yes(self):
        args = self.parser.parse_args(["add", "-y", "50", "biedronka"])
        assert args.yes is True

    def test_income(self):
        args = self.parser.parse_args(["income", "5000", "wyplata"])
        assert args.command == "income"
        assert args.amount == 5000.0
        assert args.source == ["wyplata"]

    def test_summary_no_month(self):
        args = self.parser.parse_args(["summary"])
        assert args.command == "summary"
        assert args.month is None

    def test_summary_with_month(self):
        args = self.parser.parse_args(["summary", "luty"])
        assert args.month == "luty"

    def test_last_default(self):
        args = self.parser.parse_args(["last"])
        assert args.n == 10

    def test_last_custom(self):
        args = self.parser.parse_args(["last", "5"])
        assert args.n == 5

    def test_search(self):
        args = self.parser.parse_args(["search", "biedronka", "zakupy"])
        assert args.query == ["biedronka", "zakupy"]

    def test_expenses(self):
        args = self.parser.parse_args(["expenses", "2026-02-01", "2026-02-28"])
        assert args.start == "2026-02-01"
        assert args.end == "2026-02-28"

    def test_export_no_args(self):
        args = self.parser.parse_args(["export"])
        assert args.month is None
        assert args.output is None

    def test_export_with_output(self):
        args = self.parser.parse_args(["export", "luty", "-o", "out.csv"])
        assert args.month == "luty"
        assert args.output == "out.csv"

    def test_budget_set(self):
        args = self.parser.parse_args(["budget", "set", "Jedzenie", "2000"])
        assert args.budget_action == "set"
        assert args.category == "Jedzenie"
        assert args.amount == 2000.0

    def test_budget_list(self):
        args = self.parser.parse_args(["budget", "list"])
        assert args.budget_action == "list"

    def test_budget_remove(self):
        args = self.parser.parse_args(["budget", "remove", "Jedzenie"])
        assert args.budget_action == "remove"
        assert args.category == "Jedzenie"

    def test_chart_default(self):
        args = self.parser.parse_args(["chart"])
        assert args.type == "pie"
        assert args.output is None

    def test_chart_bar(self):
        args = self.parser.parse_args(["chart", "bar"])
        assert args.type == "bar"

    def test_chart_with_output(self):
        args = self.parser.parse_args(["chart", "pie", "-o", "out.png"])
        assert args.output == "out.png"

    def test_recurring_add(self):
        args = self.parser.parse_args(
            ["recurring", "add", "120", "siłownia", "-f", "monthly"]
        )
        assert args.recurring_action == "add"
        assert args.amount == 120.0
        assert args.description == ["siłownia"]
        assert args.frequency == "monthly"

    def test_recurring_list(self):
        args = self.parser.parse_args(["recurring", "list"])
        assert args.recurring_action == "list"

    def test_recurring_remove(self):
        args = self.parser.parse_args(["recurring", "remove", "5"])
        assert args.recurring_action == "remove"
        assert args.id == 5

    def test_balance(self):
        args = self.parser.parse_args(["balance"])
        assert args.command == "balance"

    def test_categories(self):
        args = self.parser.parse_args(["categories"])
        assert args.command == "categories"

    def test_undo(self):
        args = self.parser.parse_args(["undo"])
        assert args.command == "undo"

    def test_lang(self):
        args = self.parser.parse_args(["lang", "en"])
        assert args.lang == "en"

    def test_sync(self):
        args = self.parser.parse_args(["sync"])
        assert args.command == "sync"

    def test_no_command_shows_help(self):
        args = self.parser.parse_args([])
        assert args.command is None


# ── command output tests ─────────────────────────────────────────────


class TestCmdCategories:
    def test_prints_categories(self, capsys):
        result = cmd_categories(None)
        assert result == 0
        out = capsys.readouterr().out
        assert "Jedzenie" in out
        assert "Transport" in out
        assert "Rozrywka" in out


class TestCmdAdd:
    @patch("bot.services.ai_parser.parse_expenses")
    @patch("bot.services.database.is_available", return_value=False)
    @patch("bot.services.sheets.save_expenses_to_sheet", return_value=[10])
    @patch("bot.services.storage.save_last_saved")
    def test_add_with_auto_confirm(
        self, mock_save_last, mock_sheets_save, mock_db_avail, mock_parse, capsys
    ):
        mock_parse.return_value = [
            {
                "date": "2026-02-26",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            }
        ]

        parser = build_parser()
        args = parser.parse_args(["add", "-y", "50", "biedronka"])
        result = cmd_add(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Saved 1 expense" in out

    @patch("bot.services.ai_parser.parse_expenses", return_value=[])
    def test_add_no_expense_found(self, mock_parse, capsys):
        parser = build_parser()
        args = parser.parse_args(["add", "-y", "hello"])
        result = cmd_add(args)

        assert result == 1


class TestCmdSummary:
    @patch("bot.services.database.is_available", return_value=False)
    @patch(
        "bot.services.sheets.get_all_rows",
        return_value=[
            [
                "2026-02-15", "50,00", "Jedzenie", "Jedzenie dom",
                "biedronka", "text", "Luty", "15",
            ],
            [
                "2026-02-16", "120,00", "Rozrywka", "Siłownia / Basen",
                "karnet", "text", "Luty", "16",
            ],
        ],
    )
    def test_summary_from_sheets(self, mock_sheets, mock_db, capsys):
        parser = build_parser()
        args = parser.parse_args(["summary", "luty"])
        result = cmd_summary(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Luty" in out
        assert "170.00 PLN" in out

    @patch("bot.services.database.is_available", return_value=False)
    @patch("bot.services.sheets.get_all_rows", return_value=[])
    def test_summary_no_data(self, mock_sheets, mock_db, capsys):
        parser = build_parser()
        args = parser.parse_args(["summary", "luty"])
        result = cmd_summary(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "No expenses" in out


class TestCmdLast:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch(
        "bot.services.database.get_recent_expenses",
        return_value=[
            {
                "date": "2026-02-15",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            }
        ],
    )
    def test_last_shows_expenses(self, mock_recent, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["last", "5"])
        result = cmd_last(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "biedronka" in out

    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch("bot.services.database.get_recent_expenses", return_value=[])
    def test_last_no_data(self, mock_recent, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["last"])
        result = cmd_last(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "No expenses" in out


class TestCmdSearch:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch(
        "bot.services.database.search_expenses",
        return_value=[
            {
                "date": "2026-02-15",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka zakupy",
            }
        ],
    )
    def test_search_finds_results(self, mock_search, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["search", "biedronka"])
        result = cmd_search(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "biedronka" in out

    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch("bot.services.database.search_expenses", return_value=[])
    def test_search_no_results(self, mock_search, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["search", "xyz"])
        result = cmd_search(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "No results" in out


class TestCmdExpenses:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch("bot.services.database.get_expenses_by_date_range", return_value=[])
    def test_expenses_no_data(self, mock_range, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["expenses", "2026-02-01", "2026-02-28"])
        result = cmd_expenses(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "No expenses" in out

    def test_expenses_invalid_date(self, capsys):
        parser = build_parser()
        args = parser.parse_args(["expenses", "bad-date", "2026-02-28"])
        with patch("bot.services.database.is_available", return_value=True):
            result = cmd_expenses(args)

        assert result == 1
        out = capsys.readouterr().out
        assert "YYYY-MM-DD" in out


class TestCmdExport:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch(
        "bot.services.database.get_expenses_by_month",
        return_value=[
            {
                "date": "2026-02-15",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            }
        ],
    )
    def test_export_to_stdout(self, mock_expenses, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["export", "luty"])
        result = cmd_export(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "biedronka" in out
        assert "Data,Kwota" in out

    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch(
        "bot.services.database.get_expenses_by_month",
        return_value=[
            {
                "date": "2026-02-15",
                "amount": 50.0,
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            }
        ],
    )
    def test_export_to_file(self, mock_expenses, mock_user, mock_avail, tmp_path):
        outfile = str(tmp_path / "test.csv")
        parser = build_parser()
        args = parser.parse_args(["export", "luty", "-o", outfile])
        result = cmd_export(args)

        assert result == 0
        with open(outfile) as f:
            content = f.read()
        assert "biedronka" in content

    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch("bot.services.database.get_expenses_by_month", return_value=[])
    def test_export_no_data(self, mock_expenses, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["export", "luty"])
        result = cmd_export(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "No expenses" in out


class TestCmdUndo:
    @patch("bot.services.storage.get_last_saved", return_value=None)
    def test_nothing_to_undo(self, mock_get_last, capsys):
        parser = build_parser()
        args = parser.parse_args(["undo"])
        result = cmd_undo(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "undo" in out.lower() or "cofać" in out.lower()

    @patch("bot.services.storage.get_last_saved")
    @patch("bot.services.storage.delete_last_saved")
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.delete_expenses")
    @patch("bot.services.sheets.delete_rows")
    def test_undo_with_db(
        self, mock_sheet_del, mock_db_del, mock_avail, mock_del_last, mock_get_last, capsys
    ):
        mock_get_last.return_value = {
            "expense_ids": [1, 2],
            "expenses": [{"description": "test"}],
        }

        parser = build_parser()
        args = parser.parse_args(["undo"])
        result = cmd_undo(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "2 expenses" in out
        mock_db_del.assert_called_once_with([1, 2])


class TestCmdLang:
    @patch("bot.services.database.is_available", return_value=False)
    def test_switch_to_english(self, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["lang", "en"])
        result = cmd_lang(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "English" in out

    @patch("bot.services.database.is_available", return_value=False)
    def test_switch_to_polish(self, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["lang", "pl"])
        result = cmd_lang(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Polski" in out


class TestCmdSync:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.sync.sync_unsynced_to_sheets", return_value=3)
    def test_sync_with_data(self, mock_sync, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["sync"])
        result = cmd_sync(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Synced 3 expenses" in out

    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.sync.sync_unsynced_to_sheets", return_value=0)
    def test_sync_nothing(self, mock_sync, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["sync"])
        result = cmd_sync(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "Nothing to sync" in out


class TestCmdIncome:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch("bot.services.database.save_income", return_value=1)
    def test_income_saved(self, mock_save, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["income", "5000", "wyplata"])
        result = cmd_income(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "5000" in out
        assert "wyplata" in out


class TestCmdBalance:
    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch("bot.services.database.get_expenses_by_month", return_value=[])
    @patch("bot.services.database.get_income_by_month", return_value=[])
    def test_balance_no_data(self, mock_inc, mock_exp, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["balance"])
        result = cmd_balance(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "No data" in out

    @patch("bot.services.database.is_available", return_value=True)
    @patch("bot.services.database.get_or_create_user", return_value=1)
    @patch(
        "bot.services.database.get_expenses_by_month",
        return_value=[{"amount": 1000.0}],
    )
    @patch(
        "bot.services.database.get_income_by_month",
        return_value=[{"amount": 5000.0}],
    )
    def test_balance_with_data(self, mock_inc, mock_exp, mock_user, mock_avail, capsys):
        parser = build_parser()
        args = parser.parse_args(["balance"])
        result = cmd_balance(args)

        assert result == 0
        out = capsys.readouterr().out
        assert "5000.00" in out
        assert "1000.00" in out
        assert "4000.00" in out


class TestMain:
    @patch("bot.services.database.is_available", return_value=False)
    def test_no_args_shows_help(self, mock_avail, capsys):
        with patch("sys.argv", ["budzet"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    @patch("bot.services.database.is_available", return_value=False)
    @patch("bot.services.database.get_user_language", return_value=None)
    def test_categories_command(self, mock_lang, mock_avail, capsys):
        with patch("sys.argv", ["budzet", "categories"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "Jedzenie" in out
