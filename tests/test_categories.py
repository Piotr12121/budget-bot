"""Tests for categories module."""

from bot.categories import (
    CATEGORIES,
    CATEGORY_NAMES,
    CATEGORY_EMOJIS,
    CATEGORIES_CONTEXT,
    CATEGORIES_DISPLAY,
    build_categories_context,
    build_categories_display,
)


class TestCategories:
    def test_has_11_categories(self):
        assert len(CATEGORIES) == 11
        assert len(CATEGORY_NAMES) == 11

    def test_all_categories_have_subcategories(self):
        for cat, subs in CATEGORIES.items():
            assert len(subs) > 0, f"{cat} has no subcategories"

    def test_all_categories_have_emojis(self):
        for cat in CATEGORY_NAMES:
            assert cat in CATEGORY_EMOJIS, f"{cat} missing emoji"

    def test_context_contains_all_categories(self):
        for cat in CATEGORY_NAMES:
            assert cat in CATEGORIES_CONTEXT

    def test_display_contains_all_categories(self):
        for cat in CATEGORY_NAMES:
            assert cat in CATEGORIES_DISPLAY

    def test_context_and_display_stay_in_sync(self):
        """Both generated from the same source, so they must contain the same categories."""
        for cat in CATEGORY_NAMES:
            assert cat in CATEGORIES_CONTEXT
            assert cat in CATEGORIES_DISPLAY
