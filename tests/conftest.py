"""Shared test fixtures."""

import pytest
import os

# Set test environment variables before importing bot modules
os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SPREADSHEET_NAME", "Test_Sheet")
os.environ.setdefault("SHEET_TAB_NAME", "Test_Tab")
os.environ.setdefault("ALLOWED_USER_ID", "12345")
os.environ.setdefault("STATE_DB_PATH", ":memory:")
os.environ.setdefault("USER_LANGUAGE", "pl")
