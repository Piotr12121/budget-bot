"""Tests for SQLite storage service."""

import pytest
from bot.services import storage


@pytest.fixture(autouse=True)
def reset_storage():
    """Reinitialize in-memory DB before each test."""
    storage.DB_PATH = ":memory:"
    storage._init_db()
    yield


class TestPendingExpenses:
    def test_save_and_get(self):
        data = {"user_id": 1, "expenses": [{"amount": 50}], "original_text": "test"}
        storage.save_pending("abc-123", data)
        result = storage.get_pending("abc-123")
        assert result == data

    def test_get_nonexistent_returns_none(self):
        assert storage.get_pending("nonexistent") is None

    def test_pop_returns_and_deletes(self):
        data = {"user_id": 1, "expenses": [], "original_text": "test"}
        storage.save_pending("xyz", data)
        result = storage.pop_pending("xyz")
        assert result == data
        assert storage.get_pending("xyz") is None

    def test_pop_nonexistent_returns_none(self):
        assert storage.pop_pending("nonexistent") is None

    def test_delete(self):
        data = {"user_id": 1, "expenses": [], "original_text": "test"}
        storage.save_pending("del-me", data)
        storage.delete_pending("del-me")
        assert storage.get_pending("del-me") is None


class TestLastSaved:
    def test_save_and_get(self):
        data = {"row_indices": [5, 6], "expenses": [{"amount": 50}]}
        storage.save_last_saved(1, data)
        result = storage.get_last_saved(1)
        assert result == data

    def test_get_nonexistent_returns_none(self):
        assert storage.get_last_saved(999) is None

    def test_delete(self):
        storage.save_last_saved(1, {"row_indices": [5], "expenses": []})
        storage.delete_last_saved(1)
        assert storage.get_last_saved(1) is None

    def test_overwrite(self):
        storage.save_last_saved(1, {"row_indices": [5], "expenses": []})
        storage.save_last_saved(1, {"row_indices": [10, 11], "expenses": []})
        result = storage.get_last_saved(1)
        assert result["row_indices"] == [10, 11]
