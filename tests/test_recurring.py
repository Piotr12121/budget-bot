"""Tests for recurring expense logic."""

from datetime import date, timedelta
from bot.handlers.commands import _calculate_next_due, FREQ_MAP


class TestFreqMap:
    def test_polish_monthly(self):
        assert FREQ_MAP["miesiecznie"] == "monthly"
        assert FREQ_MAP["miesięcznie"] == "monthly"

    def test_polish_weekly(self):
        assert FREQ_MAP["tygodniowo"] == "weekly"
        assert FREQ_MAP["co tydzień"] == "weekly"

    def test_polish_daily(self):
        assert FREQ_MAP["codziennie"] == "daily"

    def test_english(self):
        assert FREQ_MAP["daily"] == "daily"
        assert FREQ_MAP["weekly"] == "weekly"
        assert FREQ_MAP["monthly"] == "monthly"


class TestCalculateNextDue:
    def test_daily(self):
        result = _calculate_next_due("daily")
        assert result == date.today() + timedelta(days=1)

    def test_weekly(self):
        result = _calculate_next_due("weekly")
        assert result == date.today() + timedelta(weeks=1)

    def test_monthly(self):
        result = _calculate_next_due("monthly")
        today = date.today()
        # Should be next month
        assert result.month != today.month or result.year != today.year

    def test_monthly_with_day(self):
        result = _calculate_next_due("monthly", day_of_month=15)
        today = date.today()
        if today.day < 15:
            assert result.day == 15
            assert result.month == today.month
        else:
            assert result.day == 15
