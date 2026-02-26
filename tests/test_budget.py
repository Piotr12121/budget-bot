"""Tests for budget commands and formatting."""

from bot.handlers.commands import _build_progress_bar


class TestProgressBar:
    def test_zero_percent(self):
        bar = _build_progress_bar(0)
        assert bar == "[\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591]"

    def test_fifty_percent(self):
        bar = _build_progress_bar(50)
        assert bar.count("\u2588") == 5
        assert bar.count("\u2591") == 5

    def test_hundred_percent(self):
        bar = _build_progress_bar(100)
        assert bar == "[\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588]"

    def test_over_hundred_clamped(self):
        bar = _build_progress_bar(150)
        assert bar.count("\u2588") == 10
        assert bar.count("\u2591") == 0

    def test_custom_width(self):
        bar = _build_progress_bar(50, width=20)
        assert bar.count("\u2588") == 10
        assert bar.count("\u2591") == 10

    def test_82_percent(self):
        bar = _build_progress_bar(82)
        assert bar.count("\u2588") == 8
        assert bar.count("\u2591") == 2
