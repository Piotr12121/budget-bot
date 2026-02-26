"""Tests for Expense Pydantic model."""

import pytest
from bot.models.expense import Expense


class TestExpenseModel:
    def test_valid_expense(self):
        e = Expense(
            amount=50.0,
            date="2026-02-26",
            category="Jedzenie",
            subcategory="Jedzenie dom",
            description="biedronka zakupy",
        )
        assert e.amount == 50.0
        assert e.date == "2026-02-26"
        assert e.category == "Jedzenie"

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            Expense(
                amount=-10.0,
                date="2026-02-26",
                category="Jedzenie",
                subcategory="Jedzenie dom",
                description="test",
            )

    def test_zero_amount_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            Expense(
                amount=0.0,
                date="2026-02-26",
                category="Jedzenie",
                subcategory="Jedzenie dom",
                description="test",
            )

    def test_invalid_date_rejected(self):
        with pytest.raises(ValueError):
            Expense(
                amount=50.0,
                date="not-a-date",
                category="Jedzenie",
                subcategory="Jedzenie dom",
                description="test",
            )

    def test_to_dict(self):
        e = Expense(
            amount=99.99,
            date="2026-01-15",
            category="Transport",
            subcategory="Taxi",
            description="uber",
        )
        d = e.to_dict()
        assert d == {
            "amount": 99.99,
            "date": "2026-01-15",
            "category": "Transport",
            "subcategory": "Taxi",
            "description": "uber",
        }

    def test_float_conversion(self):
        e = Expense(
            amount=50,
            date="2026-02-26",
            category="Jedzenie",
            subcategory="Jedzenie dom",
            description="test",
        )
        assert isinstance(e.amount, float)
