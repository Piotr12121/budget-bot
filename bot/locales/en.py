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

    # Edit
    "btn_back": "Back",
    "edit_category_prompt": "Choose a category:",
    "edit_subcategory_prompt": "Choose a subcategory:",

    # Language
    "lang_switched": "🇬🇧 Language changed to: *English*",
    "lang_prompt": "🌐 Wybierz język / Choose language:",

    # Budgets
    "budget_total_label": "Total",
    "budget_warning": "⚠️ You've used {pct}% of your *{category}* budget ({used}/{limit} PLN)",
    "budget_exceeded": "🚨 Budget exceeded for *{category}*! ({used}/{limit} PLN)",
    "budget_set": "✅ Budget set: *{category}* — {limit} PLN/month",
    "budget_removed": "🗑️ Budget removed: *{category}*",
    "budget_not_found": "❌ No budget found for: *{category}*",
    "budget_list_title": "📊 *Budgets for {month}:*\n",
    "budget_no_budgets": "📊 No budgets set.\n\nUse `/budget <category> <amount>` to set one.",
    "budget_usage": "Usage: `/budget jedzenie 2000`\n`/budget total 8000` — total budget\n`/budget remove jedzenie` — remove",

    # Charts
    "chart_no_data": "📊 No data for chart in: *{month}*.",
    "chart_pie_title": "Expenses: {month}",
    "chart_bar_title": "Monthly comparison",
    "chart_error": "❌ Chart generation error.",

    # Recurring
    "recurring_added": "🔄 Added recurring expense: *{description}* — {amount} PLN ({frequency})",
    "recurring_removed": "🗑️ Removed recurring expense #{id}",
    "recurring_not_found": "❌ Recurring expense #{id} not found",
    "recurring_list_title": "🔄 *Recurring expenses:*\n",
    "recurring_no_items": "🔄 No recurring expenses.\n\nUse `/recurring add <amount> <description> <frequency>` to add.",
    "recurring_created": "🔄 Auto-created recurring expense: *{description}* — {amount} PLN",
    "recurring_usage": "Usage:\n`/recurring add 120 gym monthly`\n`/recurring list` — show list\n`/recurring remove <id>` — remove",
    "recurring_freq_daily": "daily",
    "recurring_freq_weekly": "weekly",
    "recurring_freq_monthly": "monthly",

    # Income
    "income_saved": "💵 Income saved: *{amount} PLN* — {source}",
    "income_error": "❌ Error saving income.",
    "balance_title": "💰 *Balance: {month}*\n",
    "balance_income": "💵 Income: *{income:.2f} PLN*",
    "balance_expenses": "💸 Expenses: *{expenses:.2f} PLN*",
    "balance_net": "📊 Net: *{net:.2f} PLN*",
    "balance_no_data": "💰 No data for: *{month}*.",

    # Search
    "search_title": "🔍 *Results for \"{query}\":*\n",
    "search_no_results": "🔍 No results for: *{query}*",
    "search_usage": "Usage: `/search <query>`",
    "last_title": "📋 *Last {n} expenses:*\n",
    "last_no_data": "📋 No expenses.",
    "expenses_title": "📋 *Expenses {start} — {end}:*\n",
    "expenses_no_data": "📋 No expenses in the given period.",
    "expenses_usage": "Usage: `/expenses 2026-02-01 2026-02-28`",

    # Export
    "export_no_data": "📋 No expenses to export for: *{month}*.",
    "export_error": "❌ Export error.",

    # DB required
    "db_required": "⚠️ This feature requires a database connection.",
}
