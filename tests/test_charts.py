"""Tests for chart generation."""

from io import BytesIO
from bot.utils.formatting import generate_pie_chart, generate_bar_chart


class TestPieChart:
    def test_generates_png_bytes(self):
        data = {"Jedzenie": 1500, "Transport": 500, "Rozrywka": 300}
        buf = generate_pie_chart(data, "Test Pie")
        assert isinstance(buf, BytesIO)
        # Check PNG header
        content = buf.read()
        assert content[:4] == b"\x89PNG"
        assert len(content) > 1000

    def test_single_category(self):
        data = {"Jedzenie": 1500}
        buf = generate_pie_chart(data, "Single")
        content = buf.read()
        assert content[:4] == b"\x89PNG"


class TestBarChart:
    def test_generates_png_bytes(self):
        data = {
            "Luty": {"Jedzenie": 1500, "Transport": 500},
            "Styczeń": {"Jedzenie": 1200, "Transport": 400},
        }
        buf = generate_bar_chart(data, "Test Bar")
        assert isinstance(buf, BytesIO)
        content = buf.read()
        assert content[:4] == b"\x89PNG"
        assert len(content) > 1000

    def test_empty_month(self):
        data = {
            "Luty": {"Jedzenie": 1500},
            "Styczeń": {},
        }
        buf = generate_bar_chart(data, "Partial")
        content = buf.read()
        assert content[:4] == b"\x89PNG"
