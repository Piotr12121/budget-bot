"""PostgreSQL database service with connection pooling and migrations.

Provides graceful degradation — when DATABASE_URL is not set,
is_available() returns False and the bot falls back to Sheets-only mode.
"""

import os
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

_pool: list = []
_POOL_SIZE = 3


def is_available() -> bool:
    """Check if PostgreSQL is configured and reachable."""
    if not DATABASE_URL:
        return False
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        _release_conn(conn)
        return True
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        return False


def _get_conn():
    """Get a connection from the pool or create a new one."""
    import psycopg2
    import psycopg2.extras

    if _pool:
        conn = _pool.pop()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _release_conn(conn):
    """Return a connection to the pool."""
    if len(_pool) < _POOL_SIZE:
        try:
            conn.rollback()
            _pool.append(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    else:
        try:
            conn.close()
        except Exception:
            pass


def _execute(query, params=None, fetch=False, fetchone=False, returning=False):
    """Execute a query with automatic connection management."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            result = None
            if fetchone or returning:
                result = cur.fetchone()
            elif fetch:
                result = cur.fetchall()
            conn.commit()
            return result
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_conn(conn)


def _execute_dict(query, params=None, fetchone=False):
    """Execute a query and return results as list of dicts."""
    import psycopg2.extras

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetchone:
                row = cur.fetchone()
                return dict(row) if row else None
            rows = cur.fetchall()
            conn.commit()
            return [dict(r) for r in rows]
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_conn(conn)


# --- Migrations ---

def init_db():
    """Initialize database by running pending migrations."""
    if not DATABASE_URL:
        logger.info("DATABASE_URL not set, skipping database initialization")
        return

    try:
        _run_migrations()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def _run_migrations():
    """Run all pending SQL migrations from migrations/ directory."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()

            cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
            current_version = cur.fetchone()[0]

        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            version = int(migration_file.stem.split("_")[0])
            if version <= current_version:
                continue

            logger.info(f"Applying migration {migration_file.name}")
            sql = migration_file.read_text()

            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_version (version) VALUES (%s)",
                    (version,),
                )
            conn.commit()
            logger.info(f"Migration {migration_file.name} applied successfully")

    except Exception:
        conn.rollback()
        raise
    finally:
        _release_conn(conn)


# --- User Management ---

def get_or_create_user(telegram_id: int, display_name: str | None = None) -> int:
    """Get or create a user by telegram_id. Returns user id."""
    row = _execute(
        "SELECT id FROM users WHERE telegram_id = %s",
        (telegram_id,),
        fetchone=True,
    )
    if row:
        return row[0]

    row = _execute(
        "INSERT INTO users (telegram_id, display_name) VALUES (%s, %s) RETURNING id",
        (telegram_id, display_name),
        returning=True,
    )
    return row[0]


def get_user_language(telegram_id: int) -> str | None:
    """Get user's preferred language."""
    row = _execute(
        "SELECT language FROM users WHERE telegram_id = %s",
        (telegram_id,),
        fetchone=True,
    )
    return row[0] if row else None


def set_user_language(telegram_id: int, language: str):
    """Set user's preferred language."""
    _execute(
        "UPDATE users SET language = %s WHERE telegram_id = %s",
        (language, telegram_id),
    )


# --- Expenses ---

def save_expense(user_id: int, expense_dict: dict, original_text: str) -> int:
    """Save a single expense. Returns expense ID."""
    from bot.config import MONTHS_MAPPING

    expense_date = datetime.strptime(expense_dict["date"], "%Y-%m-%d")
    month_name = MONTHS_MAPPING[expense_date.month]

    row = _execute(
        """INSERT INTO expenses
           (user_id, amount, date, category, subcategory, description, original_text, month_name)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (
            user_id,
            expense_dict["amount"],
            expense_dict["date"],
            expense_dict["category"],
            expense_dict["subcategory"],
            expense_dict["description"],
            original_text,
            month_name,
        ),
        returning=True,
    )
    return row[0]


def save_expenses(user_id: int, expenses: list[dict], original_text: str) -> list[int]:
    """Save multiple expenses. Returns list of expense IDs."""
    return [save_expense(user_id, e, original_text) for e in expenses]


def delete_expenses(expense_ids: list[int]):
    """Delete expenses by IDs."""
    if not expense_ids:
        return
    placeholders = ",".join(["%s"] * len(expense_ids))
    _execute(f"DELETE FROM expenses WHERE id IN ({placeholders})", tuple(expense_ids))


def get_expenses_by_month(user_id: int, month_name: str) -> list[dict]:
    """Get all expenses for a user in a given month."""
    return _execute_dict(
        """SELECT id, amount, date, category, subcategory, description, original_text, month_name, created_at
           FROM expenses WHERE user_id = %s AND month_name = %s
           ORDER BY date, created_at""",
        (user_id, month_name),
    )


def get_expenses_by_date_range(user_id: int, start_date: str, end_date: str) -> list[dict]:
    """Get expenses between two dates (inclusive)."""
    return _execute_dict(
        """SELECT id, amount, date, category, subcategory, description, original_text, month_name, created_at
           FROM expenses WHERE user_id = %s AND date >= %s AND date <= %s
           ORDER BY date, created_at""",
        (user_id, start_date, end_date),
    )


def search_expenses(user_id: int, query: str) -> list[dict]:
    """Full-text search in expense descriptions."""
    pattern = f"%{query}%"
    return _execute_dict(
        """SELECT id, amount, date, category, subcategory, description, original_text, month_name, created_at
           FROM expenses WHERE user_id = %s AND (
               LOWER(description) LIKE LOWER(%s)
               OR LOWER(category) LIKE LOWER(%s)
               OR LOWER(subcategory) LIKE LOWER(%s)
               OR LOWER(original_text) LIKE LOWER(%s)
           )
           ORDER BY date DESC, created_at DESC""",
        (user_id, pattern, pattern, pattern, pattern),
    )


def get_recent_expenses(user_id: int, limit: int = 10) -> list[dict]:
    """Get the most recent expenses."""
    return _execute_dict(
        """SELECT id, amount, date, category, subcategory, description, original_text, month_name, created_at
           FROM expenses WHERE user_id = %s
           ORDER BY date DESC, created_at DESC
           LIMIT %s""",
        (user_id, limit),
    )


def get_unsynced_expenses() -> list[dict]:
    """Get expenses not yet synced to Google Sheets."""
    return _execute_dict(
        """SELECT e.id, e.amount, e.date, e.category, e.subcategory, e.description,
                  e.original_text, e.month_name, u.telegram_id
           FROM expenses e
           JOIN users u ON e.user_id = u.id
           WHERE e.synced_to_sheets = FALSE
           ORDER BY e.created_at"""
    )


def mark_synced(expense_id: int, sheets_row_index: int):
    """Mark an expense as synced to Sheets."""
    _execute(
        "UPDATE expenses SET synced_to_sheets = TRUE, sheets_row_index = %s WHERE id = %s",
        (sheets_row_index, expense_id),
    )


# --- Budgets ---

def set_budget(user_id: int, category: str | None, monthly_limit: float):
    """Set or update a monthly budget. category=None means total budget."""
    _execute(
        """INSERT INTO budgets (user_id, category, monthly_limit)
           VALUES (%s, %s, %s)
           ON CONFLICT (user_id, category) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit""",
        (user_id, category, monthly_limit),
    )


def get_budgets(user_id: int) -> list[dict]:
    """Get all budgets for a user."""
    return _execute_dict(
        "SELECT id, category, monthly_limit, created_at FROM budgets WHERE user_id = %s ORDER BY category NULLS FIRST",
        (user_id,),
    )


def get_budget_usage(user_id: int, category: str | None, month_name: str) -> float:
    """Get total spending for a category in a given month."""
    if category is None:
        row = _execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = %s AND month_name = %s",
            (user_id, month_name),
            fetchone=True,
        )
    else:
        row = _execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = %s AND month_name = %s AND category = %s",
            (user_id, month_name, category),
            fetchone=True,
        )
    return float(row[0]) if row else 0.0


def delete_budget(user_id: int, category: str | None):
    """Delete a budget."""
    _execute(
        "DELETE FROM budgets WHERE user_id = %s AND category IS NOT DISTINCT FROM %s",
        (user_id, category),
    )


# --- Recurring Expenses ---

def add_recurring(user_id: int, data: dict) -> int:
    """Add a recurring expense. Returns ID."""
    row = _execute(
        """INSERT INTO recurring_expenses
           (user_id, amount, category, subcategory, description, frequency, day_of_month, next_due)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (
            user_id,
            data["amount"],
            data["category"],
            data["subcategory"],
            data["description"],
            data["frequency"],
            data.get("day_of_month"),
            data["next_due"],
        ),
        returning=True,
    )
    return row[0]


def get_recurring(user_id: int) -> list[dict]:
    """Get active recurring expenses for a user."""
    return _execute_dict(
        """SELECT id, amount, category, subcategory, description, frequency,
                  day_of_month, next_due, created_at
           FROM recurring_expenses
           WHERE user_id = %s AND is_active = TRUE
           ORDER BY next_due""",
        (user_id,),
    )


def delete_recurring(recurring_id: int):
    """Deactivate a recurring expense."""
    _execute(
        "UPDATE recurring_expenses SET is_active = FALSE WHERE id = %s",
        (recurring_id,),
    )


def get_due_recurring(today: date) -> list[dict]:
    """Get all recurring expenses due on or before today."""
    return _execute_dict(
        """SELECT r.id, r.user_id, r.amount, r.category, r.subcategory,
                  r.description, r.frequency, r.day_of_month, r.next_due,
                  u.telegram_id
           FROM recurring_expenses r
           JOIN users u ON r.user_id = u.id
           WHERE r.is_active = TRUE AND r.next_due <= %s
           ORDER BY r.next_due""",
        (today,),
    )


def update_next_due(recurring_id: int, next_due: date):
    """Update the next due date for a recurring expense."""
    _execute(
        "UPDATE recurring_expenses SET next_due = %s WHERE id = %s",
        (next_due, recurring_id),
    )


# --- Income ---

def save_income(user_id: int, amount: float, source: str, date_str: str, description: str | None = None) -> int:
    """Save an income entry. Returns income ID."""
    row = _execute(
        """INSERT INTO income (user_id, amount, source, date, description)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id""",
        (user_id, amount, source, date_str, description),
        returning=True,
    )
    return row[0]


def get_income_by_month(user_id: int, month_name: str) -> list[dict]:
    """Get income entries for a user in a given month."""
    from bot.config import MONTH_NAME_TO_NUM, MONTHS_MAPPING

    month_num = MONTH_NAME_TO_NUM.get(month_name.lower())
    if month_num is None:
        # Try exact match
        for num, name in MONTHS_MAPPING.items():
            if name == month_name:
                month_num = num
                break
    if month_num is None:
        return []

    year = datetime.now().year
    start_date = f"{year}-{month_num:02d}-01"
    if month_num == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month_num + 1:02d}-01"

    return _execute_dict(
        """SELECT id, amount, source, date, description, created_at
           FROM income WHERE user_id = %s AND date >= %s AND date < %s
           ORDER BY date, created_at""",
        (user_id, start_date, end_date),
    )


def delete_income(income_id: int):
    """Delete an income entry."""
    _execute("DELETE FROM income WHERE id = %s", (income_id,))
