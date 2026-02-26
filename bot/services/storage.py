"""In-memory state storage for pending expenses and undo history.

TODO: Replace with SQLite-backed persistent storage in Phase 1.3.
"""

# pending_expenses[uuid_str] = {"user_id": int, "expenses": [...], "original_text": str}
pending_expenses: dict[str, dict] = {}

# last_saved[user_id] = {"row_indices": [int, ...], "expenses": [...]}
last_saved: dict[int, dict] = {}
