"""Tests for Sheets background sync service."""

from unittest.mock import patch, MagicMock
from datetime import date


class TestSyncUnsyncedToSheets:
    @patch("bot.services.sync.database")
    @patch("bot.services.sync.sheets")
    def test_no_unsynced_returns_zero(self, mock_sheets, mock_db):
        from bot.services.sync import sync_unsynced_to_sheets

        mock_db.is_available.return_value = True
        mock_db.get_unsynced_expenses.return_value = []

        result = sync_unsynced_to_sheets()
        assert result == 0
        mock_sheets.save_expenses_to_sheet.assert_not_called()

    @patch("bot.services.sync.database")
    @patch("bot.services.sync.sheets")
    def test_syncs_expenses(self, mock_sheets, mock_db):
        from bot.services.sync import sync_unsynced_to_sheets

        mock_db.is_available.return_value = True
        mock_db.get_unsynced_expenses.return_value = [
            {
                "id": 1,
                "amount": 50.0,
                "date": date(2026, 2, 15),
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
                "original_text": "50 biedronka",
            }
        ]
        mock_sheets.save_expenses_to_sheet.return_value = [42]

        result = sync_unsynced_to_sheets()
        assert result == 1
        mock_db.mark_synced.assert_called_once_with(1, 42)

    @patch("bot.services.sync.database")
    @patch("bot.services.sync.sheets")
    def test_handles_sheets_error_gracefully(self, mock_sheets, mock_db):
        from bot.services.sync import sync_unsynced_to_sheets

        mock_db.is_available.return_value = True
        mock_db.get_unsynced_expenses.return_value = [
            {
                "id": 1,
                "amount": 50.0,
                "date": date(2026, 2, 15),
                "category": "Jedzenie",
                "subcategory": "Jedzenie dom",
                "description": "biedronka",
                "original_text": "test",
            }
        ]
        mock_sheets.save_expenses_to_sheet.side_effect = Exception("Sheets API error")

        result = sync_unsynced_to_sheets()
        assert result == 0
        mock_db.mark_synced.assert_not_called()

    @patch("bot.services.sync.database")
    def test_skips_when_db_unavailable(self, mock_db):
        from bot.services.sync import sync_unsynced_to_sheets

        mock_db.is_available.return_value = False
        result = sync_unsynced_to_sheets()
        assert result == 0


class TestFullReconciliation:
    @patch("bot.services.sync.database")
    def test_skips_when_db_unavailable(self, mock_db):
        from bot.services.sync import full_reconciliation

        mock_db.is_available.return_value = False
        result = full_reconciliation()
        assert result["status"] == "skipped"

    @patch("bot.services.sync.sync_unsynced_to_sheets")
    @patch("bot.services.sync.database")
    def test_reconciles_unsynced(self, mock_db, mock_sync):
        from bot.services.sync import full_reconciliation

        mock_db.is_available.return_value = True
        mock_db.get_unsynced_expenses.side_effect = [
            [{"id": 1}],  # first call: 1 unsynced
            [],  # second call after sync: 0 unsynced
        ]
        mock_sync.return_value = 1

        result = full_reconciliation()
        assert result["status"] == "ok"
        assert result["synced_count"] == 1
        assert result["unsynced_count"] == 0
