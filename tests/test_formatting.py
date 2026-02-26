"""Tests for formatting utilities."""

from bot.utils.formatting import build_preview_text, build_save_confirmation


class TestBuildPreviewText:
    def test_single_expense(self):
        expenses = [{
            "amount": 50.0,
            "date": "2026-02-26",
            "category": "Jedzenie",
            "subcategory": "Jedzenie dom",
            "description": "biedronka",
        }]
        result = build_preview_text(expenses)
        assert "50.0 PLN" in result
        assert "2026-02-26" in result
        assert "Jedzenie" in result
        assert "biedronka" in result

    def test_multiple_expenses(self):
        expenses = [
            {
                "amount": 50.0,
                "date": "2026-02-26",
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            },
            {
                "amount": 120.0,
                "date": "2026-02-26",
                "category": "Rozrywka",
                "subcategory": "Siłownia / Basen",
                "description": "silownia",
            },
        ]
        result = build_preview_text(expenses)
        assert "*1.*" in result
        assert "*2.*" in result
        assert "50.0 PLN" in result
        assert "120.0 PLN" in result


class TestBuildSaveConfirmation:
    def test_single_expense(self):
        expenses = [{
            "amount": 50.0,
            "date": "2026-02-26",
            "category": "Jedzenie",
            "subcategory": "Jedzenie dom",
            "description": "biedronka",
        }]
        result = build_save_confirmation(expenses)
        assert "Zapisano" in result or "Saved" in result
        assert "50.0 PLN" in result

    def test_multiple_expenses(self):
        expenses = [
            {
                "amount": 50.0,
                "date": "2026-02-26",
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
            },
            {
                "amount": 30.0,
                "date": "2026-02-26",
                "category": "Higiena",
                "subcategory": "Kosmetyki",
                "description": "rossmann",
            },
        ]
        result = build_save_confirmation(expenses)
        assert "80.00 PLN" in result
        assert "biedronka" in result
        assert "rossmann" in result
