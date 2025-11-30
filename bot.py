import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import gspread
from openai import OpenAI

# --- KONFIGURACJA ---
load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SPREADSHEET_NAME = os.environ["SPREADSHEET_NAME"]
SHEET_TAB_NAME = os.environ["SHEET_TAB_NAME"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])

# --- LISTA KATEGORII Z TWOJEGO PLIKU ---
# To posłuży jako instrukcja dla AI
CATEGORIES_CONTEXT = """
Główne kategorie i podkategorie:
1. Jedzenie (Jedzenie dom, Jedzenie miasto, Jedzenie praca, Alkohol, Woda)
2. Mieszkanie / dom (Czynsz, Prąd, Konserwacja i naprawy, Wyposażenie)
3. Transport (Paliwo do auta, Przeglądy i naprawy auta, Wyposażenie dodatkowe, Bilet komunikacji miejskiej, Bilet PKP/PKS, Taxi)
4. Telekomunikacja (Telefon 1, Internet, Inne)
5. Opieka zdrowotna (Lekarz, Badania, Lekarstwa, Suple)
6. Ubranie (Ubranie zwykłe, Ubranie sportowe, Buty, Dodatki)
7. Higiena (Kosmetyki, Środki czystości, Fryzjer)
8. Rozrywka (Siłownia/Basen, Kino/Teatr, Koncerty, Sprzęt RTV, Książki, Hobby, Wakacje poza budzetem)
9. Inne wydatki (Dobroczynność, Prezenty, Oprogramowanie, Edukacja, Podatki, Zwierzęta)
10. Spłata długów (Kredyt hipoteczny, Kredyt konsumpcyjny)
11. Budowanie oszczędności (Fundusz awaryjny, IKE/IKZE, Krypto)
"""

# Inicjalizacja klientów
client_ai = OpenAI(api_key=OPENAI_API_KEY)
gc = gspread.service_account(filename='credentials.json')

# Logowanie
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"Cześć! Twoje ID to: {user_id}. Wpisz je w kodzie w polu ALLOWED_USER_ID, aby autoryzować bota."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Autoryzacja
    if update.effective_user.id != ALLOWED_USER_ID:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Brak dostępu.")
        return

    user_text = update.message.text
    
    # Pobieramy aktualny czas, aby przekazać go do AI jako punkt odniesienia
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_year = now.year
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Przetwarzam...")

    try:
        # 2. AI Parsing - Zrozumienie intencji + DATY
        # W prompcie przekazujemy dzisiejszą datę i prosimy o interpretację czasu
        system_prompt = (
            f"Jesteś asystentem finansowym. Dzisiejsza data to: {today_str}. "
            f"ZASADA NR 1: Jeśli użytkownik poda datę bez roku (np. '1 listopada', '25.04', 'wczoraj'), "
            f"ZAWSZE przyjmij, że chodzi o rok {current_year}. Nie wpisuj roku 2022, 2023 czy 2024, chyba że użytkownik wyraźnie go napisze (np. 'styczeń 2022'). "
            f"Przeanalizuj tekst i wyciągnij: "
            f"1. Kwotę (liczba float). "
            f"2. Datę wydatku w formacie YYYY-MM-DD. Pamiętaj o ZASADZIE NR 1. "
            f"3. Kategorię i podkategorię pasującą do listy: {CATEGORIES_CONTEXT}. "
            f"4. Krótki opis nie zawierający daty, kategori, ceny - tylko nazwa wydatku np. 'Przedwczoraj lody tęczowe jedzenie miasto 150zl' - wpisujesz tylko 'lody tęczowe'. "
            f"Zwróć TYLKO JSON: {{\"amount\": 0.0, \"date\": \"YYYY-MM-DD\", \"category\": \"String\", \"subcategory\": \"String\", \"description\": \"String\"}}"
        )

        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "")
        
        data = json.loads(content)

        # 3. Przetwarzanie daty z AI na potrzeby kolumn pomocniczych
        # AI zwraca datę jako string "2025-11-20", musimy to zamienić na obiekt daty, żeby wyciągnąć miesiąc i dzień
        expense_date_obj = datetime.strptime(data['date'], "%Y-%m-%d")
        
        months_mapping = {
            1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
            5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
            9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień"
        }

        # Używamy daty WYDATKU, a nie daty dzisiejszej!
        expense_month_name = months_mapping[expense_date_obj.month]
        expense_day_number = expense_date_obj.day
        
        # Formatowanie kwoty na polski (przecinek)
        amount_str = str(data['amount']).replace('.', ',')

        # 4. Zapis do Google Sheets
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.worksheet(SHEET_TAB_NAME)
        
        row_to_append = [
            data['date'],           # Data wydatku (zwrócona przez AI)
            amount_str,             # Kwota z przecinkiem
            data['category'],       
            data['subcategory'],    
            data['description'],
            user_text,
            expense_month_name,     # Miesiąc wydatku (np. Listopad)
            expense_day_number      # Dzień wydatku (np. 15)
        ]
        
        worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')

        # 5. Feedback
        reply_text = (
            f"✅ Zapisano na dzień: {data['date']}\n"
            f"💰 {data['amount']} PLN\n"
            f"📂 {data['category']} > {data['subcategory']}\n"
            f"📝 {data['description']}"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)

    except Exception as e:
        logging.error(e)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Błąd: {str(e)}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(msg_handler)
    
    print("Bot wystartował...")
    application.run_polling()