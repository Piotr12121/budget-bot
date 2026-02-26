"""Google Sheets background sync service.

Handles reconciliation between PostgreSQL and Google Sheets:
- sync_unsynced_to_sheets: pushes unsynced expenses to Sheets
- full_reconciliation: verifies DB vs Sheets consistency
"""

import logging
from bot.services import database, sheets

logger = logging.getLogger(__name__)


def sync_unsynced_to_sheets() -> int:
    """Find expenses with synced_to_sheets=FALSE, append to Sheets, mark synced.

    Returns the number of expenses synced.
    """
    if not database.is_available():
        return 0

    unsynced = database.get_unsynced_expenses()
    if not unsynced:
        return 0

    synced_count = 0
    for expense in unsynced:
        try:
            expense_dict = {
                "date": str(expense["date"]),
                "amount": float(expense["amount"]),
                "category": expense["category"],
                "subcategory": expense["subcategory"],
                "description": expense["description"],
            }
            row_indices = sheets.save_expenses_to_sheet(
                [expense_dict], expense.get("original_text", "")
            )
            if row_indices:
                database.mark_synced(expense["id"], row_indices[0])
                synced_count += 1
        except Exception as e:
            logger.error(f"Failed to sync expense {expense['id']} to Sheets: {e}")
            continue

    if synced_count:
        logger.info(f"Synced {synced_count} expenses to Google Sheets")
    return synced_count


def full_reconciliation() -> dict:
    """Verify DB vs Sheets consistency. Returns summary of discrepancies."""
    if not database.is_available():
        return {"status": "skipped", "reason": "database not available"}

    result = {
        "status": "ok",
        "unsynced_count": 0,
        "synced_count": 0,
    }

    try:
        unsynced = database.get_unsynced_expenses()
        result["unsynced_count"] = len(unsynced)

        if unsynced:
            result["synced_count"] = sync_unsynced_to_sheets()
            result["unsynced_count"] = len(database.get_unsynced_expenses())
    except Exception as e:
        logger.error(f"Reconciliation error: {e}")
        result["status"] = "error"
        result["error"] = str(e)

    return result
