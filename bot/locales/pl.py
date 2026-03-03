"""Polish translations."""

STRINGS = {
    # /start
    "start_greeting": "👋 Cześć! Twoje ID to: `{user_id}`.\n\nWpisz je w pliku `.env` jako `ALLOWED_USER_ID`, aby autoryzować bota.\n\nWpisz /help aby zobaczyć dostępne komendy.",

    # /help
    "help_text": (
        "📖 *Jak używać bota?*\n\n"
        "Wyślij wiadomość z wydatkiem, np.:\n"
        "• `50 zł biedronka zakupy`\n"
        "• `tankowanie orlen 250`\n"
        "• `wczoraj netflix 45`\n"
        "• `biedronka 80, apteka 35, siłownia 120`\n"
        "• `+5000 wyplata` — przychód\n\n"
        "Bot rozpozna kwotę, datę i kategorię, a potem poprosi o potwierdzenie.\n\n"
        "*Komendy:*\n"
        "/help — ta wiadomość\n"
        "/categories — lista kategorii\n"
        "/summary `[miesiąc]` — podsumowanie (domyślnie: bieżący)\n"
        "/undo — cofnij ostatni zapisany wydatek\n"
        "/budget `<kategoria> <kwota>` — ustaw budżet\n"
        "/budget `remove <kategoria>` — usuń budżet\n"
        "/budgets — pokaż budżety z postępem\n"
        "/chart `[miesiąc]` — wykres kołowy (domyślnie: bieżący)\n"
        "/chart `bar` — wykres słupkowy za 3 miesiące\n"
        "/recurring `add <kwota> <opis> <częst.>` — dodaj cykliczny\n"
        "/recurring `list` — pokaż wydatki cykliczne\n"
        "/recurring `remove <id>` — usuń cykliczny\n"
        "/balance — bilans przychody/wydatki (bieżący miesiąc)\n"
        "/incomes — lista przychodów bieżącego miesiąca\n"
        "/search `<fraza>` — szukaj wydatków\n"
        "/last `[N]` — ostatnie N wydatków (domyślnie: 10)\n"
        "/expenses `<start> <koniec>` — wydatki w zakresie dat\n"
        "/export `[miesiąc]` — eksport CSV\n"
        "/lang — zmień język\n"
        "/importsheets — importuj wydatki z arkusza do bazy"
    ),

    # Auth
    "access_denied": "🔒 Brak dostępu.",

    # Expense parsing
    "no_expense_found": (
        "🤔 Nie rozpoznałem wydatku w Twojej wiadomości.\n\n"
        "Spróbuj np.:\n"
        "• `50 zł biedronka zakupy`\n"
        "• `tankowanie orlen 250`\n"
        "• `biedronka 80, apteka 35`\n\n"
        "Wpisz /help aby zobaczyć pomoc."
    ),
    "parse_error": "🤔 Nie udało mi się zrozumieć wydatku.\n\nSpróbuj wpisać kwotę i opis, np.: `50 zł biedronka zakupy`",
    "general_error": "❌ Wystąpił błąd podczas przetwarzania. Spróbuj ponownie.",

    # Preview
    "preview_single": "📋 *Podgląd wydatku:*",
    "preview_multi": "📋 *Podgląd wydatków:*",

    # Buttons
    "btn_save": "✅ Zapisz",
    "btn_cancel": "❌ Anuluj",
    "btn_edit": "✏️ Zmień",

    # Callback
    "expense_expired": "⚠️ Ten wydatek już został przetworzony lub wygasł.",
    "not_your_expense": "🔒 To nie Twój wydatek.",
    "cancelled": "❌ Anulowano — nic nie zostało zapisane.",
    "saved_single": "✅ Zapisano!",
    "saved_multi": "✅ Zapisano {n} wydatków!",
    "save_error": "❌ Błąd podczas zapisywania do arkusza. Spróbuj ponownie.",
    "total": "Razem",

    # Summary
    "summary_title": "📊 *Podsumowanie: {month}*",
    "summary_no_data": "📊 Brak wydatków za: *{month}*.",
    "summary_total": "💰 *Razem: {total:.2f} PLN* ({count} wpisów)",
    "summary_error": "❌ Nie udało się pobrać podsumowania. Spróbuj ponownie później.",
    "month_not_recognized": "❌ Nie rozpoznałem nazwy miesiąca. Spróbuj np. `/summary styczeń`.",

    # Undo
    "nothing_to_undo": "🤷 Nie ma czego cofać — brak ostatniego wpisu w pamięci.",
    "undo_single": "↩️ Cofnięto ostatni wpis.",
    "undo_multi": "↩️ Cofnięto ostatnie {n} wpisy.",
    "undo_error": "❌ Nie udało się cofnąć wpisu. Spróbuj ponownie.",

    # Edit
    "btn_back": "Wróć",
    "edit_category_prompt": "Wybierz kategorię:",
    "edit_subcategory_prompt": "Wybierz podkategorię:",

    # Language
    "lang_switched": "🇵🇱 Język zmieniony na: *Polski*",
    "lang_prompt": "🌐 Wybierz język / Choose language:",

    # Budgets
    "budget_total_label": "Łącznie",
    "budget_warning": "⚠️ Wykorzystano {pct}% budżetu na *{category}* ({used}/{limit} PLN)",
    "budget_exceeded": "🚨 Przekroczono budżet na *{category}*! ({used}/{limit} PLN)",
    "budget_set": "✅ Ustawiono budżet: *{category}* — {limit} PLN/miesiąc",
    "budget_removed": "🗑️ Usunięto budżet: *{category}*",
    "budget_not_found": "❌ Nie znaleziono budżetu dla: *{category}*",
    "budget_list_title": "📊 *Budżety na {month}:*\n",
    "budget_no_budgets": "📊 Nie ustawiono żadnych budżetów.\n\nUżyj `/budget <kategoria> <kwota>` aby ustawić.",
    "budget_usage": "Użycie: `/budget jedzenie 2000`\n`/budget total 8000` — budżet łączny\n`/budget remove jedzenie` — usuń",

    # Charts
    "chart_no_data": "📊 Brak danych do wygenerowania wykresu za: *{month}*.",
    "chart_pie_title": "Wydatki: {month}",
    "chart_bar_title": "Porównanie miesięcy",
    "chart_error": "❌ Błąd generowania wykresu.",

    # Recurring
    "recurring_added": "🔄 Dodano wydatek cykliczny: *{description}* — {amount} PLN ({frequency})",
    "recurring_removed": "🗑️ Usunięto wydatek cykliczny #{id}",
    "recurring_not_found": "❌ Nie znaleziono wydatku cyklicznego #{id}",
    "recurring_list_title": "🔄 *Wydatki cykliczne:*\n",
    "recurring_no_items": "🔄 Brak wydatków cyklicznych.\n\nUżyj `/recurring add <kwota> <opis> <częstotliwość>` aby dodać.",
    "recurring_created": "🔄 Automatycznie dodano wydatek cykliczny: *{description}* — {amount} PLN",
    "recurring_usage": "Użycie:\n`/recurring add 120 siłownia miesięcznie`\n`/recurring list` — pokaż listę\n`/recurring remove <id>` — usuń",
    "recurring_freq_daily": "codziennie",
    "recurring_freq_weekly": "co tydzień",
    "recurring_freq_monthly": "co miesiąc",

    # Income
    "income_saved": "💵 Zapisano przychód: *{amount} PLN* — {source}",
    "income_error": "❌ Błąd zapisywania przychodu.",
    "income_choose_category": "💵 Przychód *{amount} PLN* — {source}\n\nWybierz kategorię:",
    "income_category_selected": "✅ Zapisano przychód: *{amount} PLN*\nKategoria: {category}\nŹródło: {source}",
    "income_cancelled": "❌ Anulowano zapis przychodu.",
    "income_list_title": "💵 *Przychody: {month}*\n",
    "income_list_item": "• {emoji} *{category}*: {amount:.2f} PLN — {source}",
    "income_list_total": "💰 *Razem: {total:.2f} PLN*",
    "income_list_empty": "💵 Brak przychodów za: *{month}*.",
    "balance_title": "💰 *Bilans: {month}*\n",
    "balance_income": "💵 Przychody: *{income:.2f} PLN*",
    "balance_expenses": "💸 Wydatki: *{expenses:.2f} PLN*",
    "balance_net": "📊 Bilans: *{net:.2f} PLN*",
    "balance_no_data": "💰 Brak danych za: *{month}*.",

    # Search
    "search_title": "🔍 *Wyniki dla \"{query}\":*\n",
    "search_no_results": "🔍 Brak wyników dla: *{query}*",
    "search_usage": "Użycie: `/search <fraza>`",
    "last_title": "📋 *Ostatnie {n} wydatków:*\n",
    "last_no_data": "📋 Brak wydatków.",
    "expenses_title": "📋 *Wydatki {start} — {end}:*\n",
    "expenses_no_data": "📋 Brak wydatków w podanym okresie.",
    "expenses_usage": "Użycie: `/expenses 2026-02-01 2026-02-28`",

    # Export
    "export_no_data": "📋 Brak wydatków do eksportu za: *{month}*.",
    "export_error": "❌ Błąd eksportu.",

    # DB required
    "db_required": "⚠️ Ta funkcja wymaga połączenia z bazą danych.",
}
