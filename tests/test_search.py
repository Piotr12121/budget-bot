"""Tests for search-related i18n keys and formatting."""

from bot.i18n import t, set_lang


class TestSearchI18nKeys:
    def setup_method(self):
        set_lang("pl")

    def test_search_title_format(self):
        result = t("search_title", query="biedronka")
        assert "biedronka" in result

    def test_search_no_results(self):
        result = t("search_no_results", query="xyz")
        assert "xyz" in result

    def test_last_title(self):
        result = t("last_title", n=10)
        assert "10" in result

    def test_expenses_title(self):
        result = t("expenses_title", start="2026-02-01", end="2026-02-28")
        assert "2026-02-01" in result
        assert "2026-02-28" in result

    def test_english_variants(self):
        set_lang("en")
        assert "Results" in t("search_title", query="test")
        assert "Last" in t("last_title", n=5)
        assert "Expenses" in t("expenses_title", start="a", end="b")


class TestExportI18nKeys:
    def setup_method(self):
        set_lang("pl")

    def test_export_no_data(self):
        result = t("export_no_data", month="Luty")
        assert "Luty" in result

    def test_db_required(self):
        result = t("db_required")
        assert "baz" in result.lower() or "database" in result.lower() or "wymaga" in result.lower()


class TestBudgetI18nKeys:
    def setup_method(self):
        set_lang("pl")

    def test_budget_warning(self):
        result = t("budget_warning", pct="82", category="Jedzenie", used="1640", limit="2000")
        assert "82%" in result
        assert "Jedzenie" in result

    def test_budget_exceeded(self):
        result = t("budget_exceeded", category="Transport", used="600", limit="500")
        assert "Transport" in result
        assert "600" in result

    def test_budget_set(self):
        result = t("budget_set", category="Jedzenie", limit="2000")
        assert "Jedzenie" in result
        assert "2000" in result
