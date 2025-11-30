# Budzet Bot

Bot Telegram do szybkiego zapisywania wydatków w Google Sheets z automatycznym rozpoznawaniem kategorii przez AI (OpenAI).

## Wymagania

- Python 3.12+
- Konto Telegram z botem (token od @BotFather)
- Klucz API OpenAI
- Plik `credentials.json` z Google Cloud Service Account

## Instalacja

1. Sklonuj repozytorium i wejdz do folderu projektu

2. Stworz wirtualne srodowisko i zainstaluj zaleznosci:
```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

3. Skonfiguruj plik `credentials.json` z Google Cloud (Service Account z dostepem do Google Sheets API i Google Drive API)

4. Skopiuj `.env.example` do `.env` i uzupelnij dane:
```bash
cp .env.example .env
```

Uzupelnij w pliku `.env`:
- `TELEGRAM_TOKEN` - token bota z @BotFather
- `OPENAI_API_KEY` - klucz API OpenAI
- `SPREADSHEET_NAME` - nazwa arkusza Google
- `SHEET_TAB_NAME` - nazwa zakladki w arkuszu
- `ALLOWED_USER_ID` - Twoje ID uzytkownika Telegram

## Uruchomienie

```bash
venv/bin/python bot.py
```

## Uzycie

1. Napisz `/start` do bota, aby poznac swoje ID uzytkownika
2. Wpisz ID do `ALLOWED_USER_ID` w kodzie
3. Wysylaj wiadomosci z wydatkami, np.:
   - "50 zl biedronka zakupy do domu"
   - "Tankowanie orlen 250"
   - "Wczoraj netflix 45"

Bot automatycznie rozpozna kwote, date, kategorie i zapisze w arkuszu Google.
