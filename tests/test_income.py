"""Tests for income parsing pattern."""

import re
from bot.handlers.messages import _INCOME_PATTERN


class TestIncomePattern:
    def test_basic_income(self):
        m = _INCOME_PATTERN.match("+5000 wyplata")
        assert m is not None
        assert m.group(1) == "5000"
        assert m.group(2) == "wyplata"

    def test_income_with_decimal(self):
        m = _INCOME_PATTERN.match("+5000.50 freelance")
        assert m is not None
        assert m.group(1) == "5000.50"
        assert m.group(2) == "freelance"

    def test_income_with_comma(self):
        m = _INCOME_PATTERN.match("+5000,50 wyplata")
        assert m is not None
        assert m.group(1) == "5000,50"

    def test_income_multi_word_source(self):
        m = _INCOME_PATTERN.match("+3000 premia za projekt")
        assert m is not None
        assert m.group(2) == "premia za projekt"

    def test_not_income_without_plus(self):
        m = _INCOME_PATTERN.match("5000 wyplata")
        assert m is None

    def test_not_income_just_plus(self):
        m = _INCOME_PATTERN.match("+")
        assert m is None

    def test_not_income_no_amount(self):
        m = _INCOME_PATTERN.match("+abc wyplata")
        assert m is None
