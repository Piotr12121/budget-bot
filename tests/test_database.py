"""Tests for PostgreSQL database service.

Uses a real PostgreSQL database if TEST_DATABASE_URL is set,
otherwise tests are skipped.
"""

import os
import pytest
from datetime import date, datetime

HAS_DB = bool(os.environ.get("TEST_DATABASE_URL"))

pytestmark = pytest.mark.skipif(not HAS_DB, reason="TEST_DATABASE_URL not set")


@pytest.fixture(autouse=True)
def setup_db():
    """Set DATABASE_URL from test env and initialize fresh schema."""
    from bot.services import database

    database.DATABASE_URL = os.environ["TEST_DATABASE_URL"]
    database._pool.clear()

    # Drop all tables and recreate
    conn = database._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DROP TABLE IF EXISTS income CASCADE;
                DROP TABLE IF EXISTS recurring_expenses CASCADE;
                DROP TABLE IF EXISTS budgets CASCADE;
                DROP TABLE IF EXISTS expenses CASCADE;
                DROP TABLE IF EXISTS users CASCADE;
                DROP TABLE IF EXISTS schema_version CASCADE;
            """)
        conn.commit()
    finally:
        database._release_conn(conn)

    database.init_db()
    yield

    database._pool.clear()


@pytest.fixture
def user_id():
    """Create a test user and return user_id."""
    from bot.services import database
    return database.get_or_create_user(12345, "Test User")


class TestUserManagement:
    def test_get_or_create_user(self):
        from bot.services import database
        uid = database.get_or_create_user(12345, "Test")
        assert uid > 0

    def test_get_existing_user(self):
        from bot.services import database
        uid1 = database.get_or_create_user(12345, "Test")
        uid2 = database.get_or_create_user(12345, "Test")
        assert uid1 == uid2

    def test_user_language(self):
        from bot.services import database
        database.get_or_create_user(12345)
        lang = database.get_user_language(12345)
        assert lang == "pl"

        database.set_user_language(12345, "en")
        lang = database.get_user_language(12345)
        assert lang == "en"


class TestExpenses:
    def test_save_expense(self, user_id):
        from bot.services import database
        eid = database.save_expense(user_id, {
            "amount": 50.0,
            "date": "2026-02-15",
            "category": "Jedzenie",
            "subcategory": "Jedzenie dom",
            "description": "biedronka",
        }, "50 biedronka")
        assert eid > 0

    def test_save_multiple_expenses(self, user_id):
        from bot.services import database
        eids = database.save_expenses(user_id, [
            {"amount": 50.0, "date": "2026-02-15", "category": "Jedzenie",
             "subcategory": "Jedzenie dom", "description": "biedronka"},
            {"amount": 120.0, "date": "2026-02-15", "category": "Rozrywka",
             "subcategory": "Siłownia / Basen", "description": "silownia"},
        ], "biedronka 50, silownia 120")
        assert len(eids) == 2

    def test_get_expenses_by_month(self, user_id):
        from bot.services import database
        database.save_expense(user_id, {
            "amount": 50.0, "date": "2026-02-15", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "biedronka",
        }, "test")
        rows = database.get_expenses_by_month(user_id, "Luty")
        assert len(rows) == 1
        assert float(rows[0]["amount"]) == 50.0

    def test_delete_expenses(self, user_id):
        from bot.services import database
        eids = database.save_expenses(user_id, [
            {"amount": 50.0, "date": "2026-02-15", "category": "Jedzenie",
             "subcategory": "Jedzenie dom", "description": "test"},
        ], "test")
        database.delete_expenses(eids)
        rows = database.get_expenses_by_month(user_id, "Luty")
        assert len(rows) == 0

    def test_search_expenses(self, user_id):
        from bot.services import database
        database.save_expense(user_id, {
            "amount": 50.0, "date": "2026-02-15", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "biedronka zakupy",
        }, "test")
        results = database.search_expenses(user_id, "biedronka")
        assert len(results) == 1

    def test_get_recent_expenses(self, user_id):
        from bot.services import database
        for i in range(15):
            database.save_expense(user_id, {
                "amount": 10.0 + i, "date": f"2026-02-{i+1:02d}",
                "category": "Jedzenie", "subcategory": "Jedzenie dom",
                "description": f"expense {i}",
            }, "test")
        recent = database.get_recent_expenses(user_id, limit=10)
        assert len(recent) == 10

    def test_sync_marking(self, user_id):
        from bot.services import database
        eid = database.save_expense(user_id, {
            "amount": 50.0, "date": "2026-02-15", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "test",
        }, "test")
        unsynced = database.get_unsynced_expenses()
        assert any(r["id"] == eid for r in unsynced)

        database.mark_synced(eid, 42)
        unsynced = database.get_unsynced_expenses()
        assert not any(r["id"] == eid for r in unsynced)

    def test_get_expenses_by_date_range(self, user_id):
        from bot.services import database
        database.save_expense(user_id, {
            "amount": 50.0, "date": "2026-02-15", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "test",
        }, "test")
        database.save_expense(user_id, {
            "amount": 30.0, "date": "2026-03-01", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "test2",
        }, "test")
        rows = database.get_expenses_by_date_range(user_id, "2026-02-01", "2026-02-28")
        assert len(rows) == 1


class TestBudgets:
    def test_set_and_get_budget(self, user_id):
        from bot.services import database
        database.set_budget(user_id, "Jedzenie", 2000.0)
        budgets = database.get_budgets(user_id)
        assert len(budgets) == 1
        assert float(budgets[0]["monthly_limit"]) == 2000.0

    def test_update_budget(self, user_id):
        from bot.services import database
        database.set_budget(user_id, "Jedzenie", 2000.0)
        database.set_budget(user_id, "Jedzenie", 2500.0)
        budgets = database.get_budgets(user_id)
        assert len(budgets) == 1
        assert float(budgets[0]["monthly_limit"]) == 2500.0

    def test_total_budget(self, user_id):
        from bot.services import database
        database.set_budget(user_id, None, 8000.0)
        budgets = database.get_budgets(user_id)
        assert any(b["category"] is None for b in budgets)

    def test_budget_usage(self, user_id):
        from bot.services import database
        database.save_expense(user_id, {
            "amount": 100.0, "date": "2026-02-15", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "test",
        }, "test")
        usage = database.get_budget_usage(user_id, "Jedzenie", "Luty")
        assert usage == 100.0

    def test_delete_budget(self, user_id):
        from bot.services import database
        database.set_budget(user_id, "Jedzenie", 2000.0)
        database.delete_budget(user_id, "Jedzenie")
        budgets = database.get_budgets(user_id)
        assert len(budgets) == 0


class TestRecurring:
    def test_add_and_get_recurring(self, user_id):
        from bot.services import database
        rid = database.add_recurring(user_id, {
            "amount": 120.0,
            "category": "Rozrywka",
            "subcategory": "Siłownia / Basen",
            "description": "silownia",
            "frequency": "monthly",
            "day_of_month": 1,
            "next_due": "2026-03-01",
        })
        assert rid > 0
        items = database.get_recurring(user_id)
        assert len(items) == 1

    def test_delete_recurring(self, user_id):
        from bot.services import database
        rid = database.add_recurring(user_id, {
            "amount": 120.0,
            "category": "Rozrywka",
            "subcategory": "Siłownia / Basen",
            "description": "silownia",
            "frequency": "monthly",
            "day_of_month": 1,
            "next_due": "2026-03-01",
        })
        database.delete_recurring(rid)
        items = database.get_recurring(user_id)
        assert len(items) == 0

    def test_get_due_recurring(self, user_id):
        from bot.services import database
        database.add_recurring(user_id, {
            "amount": 120.0,
            "category": "Rozrywka",
            "subcategory": "Siłownia / Basen",
            "description": "silownia",
            "frequency": "monthly",
            "day_of_month": 1,
            "next_due": "2026-02-01",
        })
        due = database.get_due_recurring(date(2026, 2, 26))
        assert len(due) == 1

    def test_update_next_due(self, user_id):
        from bot.services import database
        rid = database.add_recurring(user_id, {
            "amount": 120.0,
            "category": "Rozrywka",
            "subcategory": "Siłownia / Basen",
            "description": "silownia",
            "frequency": "monthly",
            "day_of_month": 1,
            "next_due": "2026-02-01",
        })
        database.update_next_due(rid, date(2026, 3, 1))
        due = database.get_due_recurring(date(2026, 2, 26))
        assert len(due) == 0


class TestIncome:
    def test_save_income(self, user_id):
        from bot.services import database
        iid = database.save_income(user_id, 5000.0, "wyplata", "2026-02-15", "pensja")
        assert iid > 0

    def test_get_income_by_month(self, user_id):
        from bot.services import database
        database.save_income(user_id, 5000.0, "wyplata", "2026-02-15", "pensja")
        income = database.get_income_by_month(user_id, "Luty")
        assert len(income) == 1
        assert float(income[0]["amount"]) == 5000.0

    def test_delete_income(self, user_id):
        from bot.services import database
        iid = database.save_income(user_id, 5000.0, "wyplata", "2026-02-15", "pensja")
        database.delete_income(iid)
        income = database.get_income_by_month(user_id, "Luty")
        assert len(income) == 0
