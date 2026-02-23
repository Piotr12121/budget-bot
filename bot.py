import os
import json
import logging
import uuid
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import gspread
from openai import OpenAI

# --- KONFIGURACJA ---
load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SPREADSHEET_NAME = os.environ["SPREADSHEET_NAME"]
SHEET_TAB_NAME = os.environ["SHEET_TAB_NAME"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])

# --- KATEGORIE ---
CATEGORIES_CONTEXT = """
Główne kategorie i podkategorie:
1. Jedzenie (Jedzenie dom, Jedzenie miasto, Jedzenie praca, Alkohol, Woda)
2. Mieszkanie / dom (Czynsz, Prąd, Konserwacja i naprawy, Wyposażenie)
3. Transport (Paliwo do auta, Przeglądy i naprawy auta, Wyposażenie dodatkowe, Bilet komunikacji miejskiej, Bilet PKP/PKS, Taxi)
4. Telekomunikacja (Telefon 1, Internet, Inne)
5. Opieka zdrowotna (Lekarz, Badania, Lekarstwa, Suple)
6. Ubranie (Ubranie zwykłe, Ubranie sportowe, Buty, Dodatki, Inne)
7. Higiena (Kosmetyki, Środki czystości, Fryzjer, Inne)
8. Rozrywka (Siłownia / Basen, Kino / Teatr / Vod, Koncerty, Sprzęt RTV, Książki, Hobby / sprzęt sportowy, Wakacje poza budzetem, Inne)
9. Inne wydatki (Dobroczynność, Prezenty, Oprogramowanie, Edukacja / Szkolenia, Podatki, Zwierzęta)
10. Spłata długów (Kredyt hipoteczny, Kredyt konsumpcyjny, Inne)
11. Budowanie oszczędności (Fundusz awaryjny, Fundusz wydatków nieregularnych, Poduszka finansowa, Konto emerytalne IKE/IKZE, Krypto, Fundusz: wakacje, Fundusz: prezenty świąteczne, Inne)
"""

CATEGORIES_DISPLAY = """
🍔 *1. Jedzenie*
   Jedzenie dom · Jedzenie miasto · Jedzenie praca · Alkohol · Woda

🏠 *2. Mieszkanie / dom*
   Czynsz · Prąd · Konserwacja i naprawy · Wyposażenie

🚗 *3. Transport*
   Paliwo do auta · Przeglądy i naprawy auta · Wyposażenie dodatkowe · Bilet komunikacji miejskiej · Bilet PKP/PKS · Taxi

📱 *4. Telekomunikacja*
   Telefon 1 · Internet · Inne

🏥 *5. Opieka zdrowotna*
   Lekarz · Badania · Lekarstwa · Suple

👕 *6. Ubranie*
   Ubranie zwykłe · Ubranie sportowe · Buty · Dodatki · Inne

🧴 *7. Higiena*
   Kosmetyki · Środki czystości · Fryzjer · Inne

🎮 *8. Rozrywka*
   Siłownia / Basen · Kino / Teatr / Vod · Koncerty · Sprzęt RTV · Książki · Hobby / sprzęt sportowy · Wakacje poza budzetem · Inne

📦 *9. Inne wydatki*
   Dobroczynność · Prezenty · Oprogramowanie · Edukacja / Szkolenia · Podatki · Zwierzęta

💳 *10. Spłata długów*
   Kredyt hipoteczny · Kredyt konsumpcyjny · Inne

💰 *11. Budowanie oszczędności*
   Fundusz awaryjny · Fundusz wydatków nieregularnych · Poduszka finansowa · Konto emerytalne IKE/IKZE · Krypto · Fundusz: wakacje · Fundusz: prezenty świąteczne · Inne
"""

MONTHS_MAPPING = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień",
}

MONTH_NAME_TO_NUM = {v.lower(): k for k, v in MONTHS_MAPPING.items()}

# Inicjalizacja klientów
client_ai = OpenAI(api_key=OPENAI_API_KEY)
gc = gspread.service_account(filename="credentials.json")

# Logowanie
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# --- STAN W PAMIĘCI ---
# pending_expenses[uuid_str] = {"user_id": int, "expenses": [...], "original_text": str}
pending_expenses: dict[str, dict] = {}
# last_saved[user_id] = {"row_indices": [int, ...], "expenses": [...]}
last_saved: dict[int, dict] = {}


# ====================================================================
# HELPERS
# ====================================================================

def _build_preview_text(expenses: list[dict]) -> str:
    """Format a list of parsed expenses into a human-readable preview."""
    if len(expenses) == 1:
        e = expenses[0]
        return (
            f"📋 *Podgląd wydatku:*\n"
            f"📅 Data: `{e['date']}`\n"
            f"💰 Kwota: *{e['amount']} PLN*\n"
            f"📂 {e['category']} > {e['subcategory']}\n"
            f"📝 {e['description']}"
        )
    lines = ["📋 *Podgląd wydatków:*\n"]
    for i, e in enumerate(expenses, 1):
        lines.append(
            f"*{i}.* `{e['date']}` — *{e['amount']} PLN*\n"
            f"    📂 {e['category']} > {e['subcategory']}\n"
            f"    📝 {e['description']}\n"
        )
    return "\n".join(lines)


def _save_expenses_to_sheet(expenses: list[dict], original_text: str) -> list[int]:
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
        # The appended row is always the last row
        saved_row_indices.append(len(worksheet.get_all_values()))

    return saved_row_indices


# ====================================================================
# COMMAND HANDLERS
# ====================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"👋 Cześć! Twoje ID to: `{user_id}`.\n\n"
            f"Wpisz je w pliku `.env` jako `ALLOWED_USER_ID`, aby autoryzować bota.\n\n"
            f"Wpisz /help aby zobaczyć dostępne komendy."
        ),
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
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
        ),
        parse_mode="Markdown",
    )


async def categories_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feature #11 — show available categories."""
    if update.effective_user.id != ALLOWED_USER_ID:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🔒 Brak dostępu.")
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=CATEGORIES_DISPLAY,
        parse_mode="Markdown",
    )


async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feature #7 — monthly summary."""
    if update.effective_user.id != ALLOWED_USER_ID:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🔒 Brak dostępu.")
        return

    # Determine which month the user wants
    args = context.args
    if args:
        month_query = " ".join(args).strip().lower()
        target_month = None
        for name, num in MONTH_NAME_TO_NUM.items():
            if name.startswith(month_query):
                target_month = MONTHS_MAPPING[num]
                break
        if target_month is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Nie rozpoznałem nazwy miesiąca. Spróbuj np. `/summary styczeń`.",
                parse_mode="Markdown",
            )
            return
    else:
        target_month = MONTHS_MAPPING[datetime.now().month]

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.worksheet(SHEET_TAB_NAME)
        all_rows = worksheet.get_all_values()

        # Filter by month name (column index 6 = 7th column)
        totals: dict[str, float] = {}
        count = 0
        for row in all_rows:
            if len(row) < 7:
                continue
            if row[6].strip() == target_month:
                try:
                    amount = float(row[1].replace(",", "."))
                    category = row[2]
                    totals[category] = totals.get(category, 0) + amount
                    count += 1
                except (ValueError, IndexError):
                    continue

        if not totals:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📊 Brak wydatków za: *{target_month}*.",
                parse_mode="Markdown",
            )
            return

        grand_total = sum(totals.values())
        lines = [f"📊 *Podsumowanie: {target_month}*\n"]
        for cat in sorted(totals, key=lambda c: totals[c], reverse=True):
            lines.append(f"  • {cat}: *{totals[cat]:.2f} PLN*")
        lines.append(f"\n💰 *Razem: {grand_total:.2f} PLN* ({count} wpisów)")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logging.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Nie udało się pobrać podsumowania. Spróbuj ponownie później.",
        )


async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feature #2 — undo last saved entry/entries."""
    if update.effective_user.id != ALLOWED_USER_ID:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🔒 Brak dostępu.")
        return

    user_id = update.effective_user.id
    saved = last_saved.get(user_id)

    if not saved:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🤷 Nie ma czego cofać — brak ostatniego wpisu w pamięci.",
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.worksheet(SHEET_TAB_NAME)

        # Delete rows in reverse order so indices don't shift
        for row_idx in sorted(saved["row_indices"], reverse=True):
            worksheet.delete_rows(row_idx)

        n = len(saved["row_indices"])
        del last_saved[user_id]

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"↩️ Cofnięto {'ostatni wpis' if n == 1 else f'ostatnie {n} wpisy'}.",
        )
    except Exception as e:
        logging.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Nie udało się cofnąć wpisu. Spróbuj ponownie.",
        )


# ====================================================================
# MESSAGE HANDLER (EXPENSE PARSING)
# ====================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Autoryzacja
    if update.effective_user.id != ALLOWED_USER_ID:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🔒 Brak dostępu.")
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id

    # Feature #5/#8 — typing indicator instead of text message
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_year = now.year

    try:
        # Feature #6 — batch expenses: AI returns a JSON array
        # Feature #9 — non-expense handling: AI returns empty array for non-expenses
        system_prompt = (
            f"Jesteś asystentem finansowym. Dzisiejsza data to: {today_str}. "
            f"ZASADA NR 1: Jeśli użytkownik poda datę bez roku (np. '1 listopada', '25.04', 'wczoraj'), "
            f"ZAWSZE przyjmij, że chodzi o rok {current_year}. "
            f"Nie wpisuj roku 2022, 2023 czy 2024, chyba że użytkownik wyraźnie go napisze. "
            f"\n\nPrzeanalizuj tekst użytkownika. Tekst może zawierać JEDEN lub WIELE wydatków. "
            f"Dla KAŻDEGO wydatku wyciągnij:\n"
            f"1. Kwotę (liczba float).\n"
            f"2. Datę wydatku w formacie YYYY-MM-DD (pamiętaj o ZASADZIE NR 1).\n"
            f"3. Kategorię i podkategorię pasującą do listy: {CATEGORIES_CONTEXT}\n"
            f"4. Krótki opis — tylko nazwa wydatku, bez daty/kategorii/ceny.\n"
            f"\nJeśli tekst NIE zawiera żadnego wydatku (np. powitanie, pytanie, rozmowa), "
            f"zwróć pusty JSON array: []\n"
            f"\nZwróć WYŁĄCZNIE JSON array (nawet dla jednego wydatku): "
            f'[{{"amount": 0.0, "date": "YYYY-MM-DD", "category": "String", '
            f'"subcategory": "String", "description": "String"}}]'
        )

        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        data = json.loads(content)

        # Normalize: if AI returned a single object, wrap it
        if isinstance(data, dict):
            data = [data]

        # Feature #9 — non-expense: empty array
        if not data:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "🤔 Nie rozpoznałem wydatku w Twojej wiadomości.\n\n"
                    "Spróbuj np.:\n"
                    "• `50 zł biedronka zakupy`\n"
                    "• `tankowanie orlen 250`\n"
                    "• `biedronka 80, apteka 35`\n\n"
                    "Wpisz /help aby zobaczyć pomoc."
                ),
                parse_mode="Markdown",
            )
            return

        # Feature #1 — confirm before saving
        expense_id = str(uuid.uuid4())
        pending_expenses[expense_id] = {
            "user_id": update.effective_user.id,
            "expenses": data,
            "original_text": user_text,
        }

        preview = _build_preview_text(data)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Zapisz", callback_data=f"confirm:{expense_id}"),
                InlineKeyboardButton("❌ Anuluj", callback_data=f"cancel:{expense_id}"),
            ]
        ])

        await context.bot.send_message(
            chat_id=chat_id,
            text=preview,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    except json.JSONDecodeError:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🤔 Nie udało mi się zrozumieć wydatku.\n\n"
                "Spróbuj wpisać kwotę i opis, np.: `50 zł biedronka zakupy`"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logging.error(f"Error in handle_message: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Wystąpił błąd podczas przetwarzania. Spróbuj ponownie.",
        )


# ====================================================================
# CALLBACK HANDLER (CONFIRM / CANCEL)
# ====================================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    action, expense_id = callback_data.split(":", 1)

    pending = pending_expenses.pop(expense_id, None)
    if pending is None:
        await query.edit_message_text("⚠️ Ten wydatek już został przetworzony lub wygasł.")
        return

    # Verify user
    if query.from_user.id != pending["user_id"]:
        pending_expenses[expense_id] = pending  # put it back
        await query.answer("🔒 To nie Twój wydatek.", show_alert=True)
        return

    if action == "cancel":
        await query.edit_message_text("❌ Anulowano — nic nie zostało zapisane.")
        return

    if action == "confirm":
        try:
            row_indices = _save_expenses_to_sheet(
                pending["expenses"], pending["original_text"]
            )

            # Store for undo
            last_saved[pending["user_id"]] = {
                "row_indices": row_indices,
                "expenses": pending["expenses"],
            }

            n = len(pending["expenses"])
            if n == 1:
                e = pending["expenses"][0]
                result_text = (
                    f"✅ Zapisano!\n"
                    f"📅 {e['date']}\n"
                    f"💰 {e['amount']} PLN\n"
                    f"📂 {e['category']} > {e['subcategory']}\n"
                    f"📝 {e['description']}"
                )
            else:
                lines = [f"✅ Zapisano {n} wydatków!\n"]
                total = 0
                for i, e in enumerate(pending["expenses"], 1):
                    lines.append(f"{i}. {e['description']} — {e['amount']} PLN")
                    total += e["amount"]
                lines.append(f"\n💰 Razem: {total:.2f} PLN")
                result_text = "\n".join(lines)

            await query.edit_message_text(result_text)

        except Exception as e:
            logging.error(f"Error saving expenses: {e}")
            await query.edit_message_text(
                "❌ Błąd podczas zapisywania do arkusza. Spróbuj ponownie."
            )


# ====================================================================
# MAIN
# ====================================================================

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("categories", categories_cmd))
    application.add_handler(CommandHandler("summary", summary_cmd))
    application.add_handler(CommandHandler("undo", undo_cmd))
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot wystartował...")
    application.run_polling()