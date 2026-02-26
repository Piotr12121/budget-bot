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
        "• `biedronka 80, apteka 35, siłownia 120`\n\n"
        "Bot rozpozna kwotę, datę i kategorię, a potem poprosi o potwierdzenie.\n\n"
        "*Komendy:*\n"
        "/help — ta wiadomość\n"
        "/categories — lista kategorii\n"
        "/summary — podsumowanie bieżącego miesiąca\n"
        "/summary _nazwa miesiąca_ — podsumowanie konkretnego miesiąca\n"
        "/undo — cofnij ostatni zapisany wydatek\n"
        "/lang — zmień język / change language"
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

    # Language
    "lang_switched": "🇵🇱 Język zmieniony na: *Polski*",
    "lang_prompt": "🌐 Wybierz język / Choose language:",
}
