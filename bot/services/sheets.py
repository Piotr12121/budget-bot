"""Google Sheets read/write operations."""

import logging
from datetime import datetime
from bot.config import gc, SPREADSHEET_NAME, SHEET_TAB_NAME, MONTHS_MAPPING

logger = logging.getLogger(__name__)


def save_expenses_to_sheet(expenses: list[dict], original_text: str) -> list[int]:
    """Append expenses to Google Sheets. Returns list of row indices."""
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.worksheet(SHEET_TAB_NAME)
    saved_row_indices: list[int] = []

    for data in expenses:
        expense_date_obj = datetime.strptime(data["date"], "%Y-%m-%d")
        expense_month_name = MONTHS_MAPPING[expense_date_obj.month]
        expense_day_number = expense_date_obj.day
        amount_str = str(data["amount"]).replace(".", ",")

        row_to_append = [
            data["date"],
            amount_str,
            data["category"],
            data["subcategory"],
            data["description"],
            original_text,
            expense_month_name,
            expense_day_number,
        ]
        worksheet.append_row(row_to_append, value_input_option="USER_ENTERED")
        saved_row_indices.append(len(worksheet.get_all_values()))

    return saved_row_indices


def delete_rows(row_indices: list[int]) -> None:
    """Delete rows by indices (in reverse order to preserve indices)."""
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.worksheet(SHEET_TAB_NAME)
    for row_idx in sorted(row_indices, reverse=True):
        worksheet.delete_rows(row_idx)


def get_all_rows() -> list[list[str]]:
    """Fetch all rows from the sheet."""
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.worksheet(SHEET_TAB_NAME)
    return worksheet.get_all_values()
