"""English translations."""

STRINGS = {
    # /start
    "start_greeting": "👋 Hi! Your ID is: `{user_id}`.\n\nEnter it in the `.env` file as `ALLOWED_USER_ID` to authorize the bot.\n\nType /help to see available commands.",

    # /help
    "help_text": (
        "📖 *How to use the bot?*\n\n"
        "Send a message with an expense, e.g.:\n"
        "• `50 zł grocery shopping`\n"
        "• `gas station 250`\n"
        "• `yesterday netflix 45`\n"
        "• `groceries 80, pharmacy 35, gym 120`\n\n"
        "The bot will recognize the amount, date and category, then ask for confirmation.\n\n"
        "*Commands:*\n"
        "/help — this message\n"
        "/categories — category list\n"
        "/summary — current month summary\n"
        "/summary _month name_ — specific month summary\n"
        "/undo — undo last saved expense\n"
        "/lang — zmień język / change language"
    ),

    # Auth
    "access_denied": "🔒 Access denied.",

    # Expense parsing
    "no_expense_found": (
        "🤔 I didn't recognize an expense in your message.\n\n"
        "Try e.g.:\n"
        "• `50 zł grocery shopping`\n"
        "• `gas station 250`\n"
        "• `groceries 80, pharmacy 35`\n\n"
        "Type /help to see help."
    ),
    "parse_error": "🤔 I couldn't understand the expense.\n\nTry entering an amount and description, e.g.: `50 zł grocery shopping`",
    "general_error": "❌ An error occurred during processing. Please try again.",

    # Preview
    "preview_single": "📋 *Expense preview:*",
    "preview_multi": "📋 *Expenses preview:*",

    # Buttons
    "btn_save": "✅ Save",
    "btn_cancel": "❌ Cancel",
    "btn_edit": "✏️ Edit",

    # Callback
    "expense_expired": "⚠️ This expense has already been processed or expired.",
    "not_your_expense": "🔒 This is not your expense.",
    "cancelled": "❌ Cancelled — nothing was saved.",
    "saved_single": "✅ Saved!",
    "saved_multi": "✅ Saved {n} expenses!",
    "save_error": "❌ Error saving to spreadsheet. Please try again.",
    "total": "Total",

    # Summary
    "summary_title": "📊 *Summary: {month}*",
    "summary_no_data": "📊 No expenses for: *{month}*.",
    "summary_total": "💰 *Total: {total:.2f} PLN* ({count} entries)",
    "summary_error": "❌ Failed to fetch summary. Please try again later.",
    "month_not_recognized": "❌ Month name not recognized. Try e.g. `/summary styczeń`.",

    # Undo
    "nothing_to_undo": "🤷 Nothing to undo — no recent entry in memory.",
    "undo_single": "↩️ Last entry undone.",
    "undo_multi": "↩️ Last {n} entries undone.",
    "undo_error": "❌ Failed to undo entry. Please try again.",

    # Language
    "lang_switched": "🇬🇧 Language changed to: *English*",
    "lang_prompt": "🌐 Wybierz język / Choose language:",
}
