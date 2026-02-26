"""Persistent state storage using SQLite for pending expenses and undo history.

Survives bot restarts on Railway. Auto-cleans expired pending expenses.
"""

import json
import sqlite3
import time
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("STATE_DB_PATH", "state.db")
PENDING_TTL_SECONDS = 3600  # 1 hour


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pending_expenses (
            expense_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS last_saved (
            user_id INTEGER PRIMARY KEY,
            data_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );
    """)
    conn.close()


_init_db()


# --- Pending Expenses ---

def save_pending(expense_id: str, data: dict) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO pending_expenses (expense_id, user_id, data_json, created_at) VALUES (?, ?, ?, ?)",
        (expense_id, data["user_id"], json.dumps(data), time.time()),
    )
    conn.commit()
    conn.close()


def get_pending(expense_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT data_json FROM pending_expenses WHERE expense_id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row[0])


def delete_pending(expense_id: str) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM pending_expenses WHERE expense_id = ?", (expense_id,))
    conn.commit()
    conn.close()


def pop_pending(expense_id: str) -> dict | None:
    """Get and delete a pending expense atomically."""
    data = get_pending(expense_id)
    if data is not None:
        delete_pending(expense_id)
    return data


# --- Last Saved (for undo) ---

def save_last_saved(user_id: int, data: dict) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO last_saved (user_id, data_json, created_at) VALUES (?, ?, ?)",
        (user_id, json.dumps(data), time.time()),
    )
    conn.commit()
    conn.close()


def get_last_saved(user_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT data_json FROM last_saved WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row[0])


def delete_last_saved(user_id: int) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM last_saved WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- Cleanup ---

def cleanup_expired() -> int:
    """Remove pending expenses older than TTL. Returns count of removed entries."""
    cutoff = time.time() - PENDING_TTL_SECONDS
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM pending_expenses WHERE created_at < ?", (cutoff,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    if count > 0:
        logger.info(f"Cleaned up {count} expired pending expenses")
    return count


# Backward compatibility - dict-like access for transition period
pending_expenses: dict[str, dict] = {}  # unused, kept for import compatibility
last_saved: dict[int, dict] = {}  # unused, kept for import compatibility
