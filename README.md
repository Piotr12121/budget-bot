# Budzet Bot

Bot do zarządzania budżetem osobistym — dostępny przez Telegram i CLI. Automatyczne rozpoznawanie wydatków przez AI (OpenAI), zapis w PostgreSQL i Google Sheets.

## Wymagania

- Python 3.12+
- Klucz API OpenAI
- Plik `credentials.json` z Google Cloud Service Account (Sheets API + Drive API)
- **Telegram**: token bota od @BotFather
- **Baza danych** (opcjonalnie): PostgreSQL — włącza budżety, wykresy, wyszukiwanie, cykliczne wydatki

## Instalacja

```bash
git clone <repo-url> && cd budzet-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .          # instaluje komendę `budzet`
```

Skopiuj `.env.example` do `.env` i uzupełnij dane:

```bash
cp .env.example .env
```

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `OPENAI_API_KEY` | tak | Klucz API OpenAI |
| `SPREADSHEET_NAME` | tak | Nazwa arkusza Google |
| `SHEET_TAB_NAME` | tak | Nazwa zakładki w arkuszu |
| `ALLOWED_USER_ID` | tak | Twoje ID użytkownika Telegram |
| `TELEGRAM_TOKEN` | dla bota | Token bota z @BotFather |
| `DATABASE_URL` | nie | PostgreSQL connection string (włącza tryb DB) |
| `USER_LANGUAGE` | nie | Język: `pl` (domyślny) lub `en` |

## Uruchomienie

### Bot Telegram

```bash
python -m bot.main
```

### CLI

Po `pip install -e .` dostępna jest komenda `budzet`:

```bash
budzet --help
```

## Komendy

### Dodawanie wydatków

```bash
# Telegram: wyślij tekst z wydatkiem
50 zł biedronka zakupy
tankowanie orlen 250
wczoraj netflix 45
biedronka 80, apteka 35, siłownia 120

# CLI
budzet add "50 biedronka zakupy"
budzet add "biedronka 80, apteka 35" -y     # bez potwierdzenia
```

Bot rozpoznaje kwotę, datę i kategorię przez AI, następnie prosi o potwierdzenie przed zapisem.

### Przychody (wymaga DB)

```bash
# Telegram
+5000 wyplata

# CLI
budzet income 5000 wyplata
```

### Podsumowanie miesiąca

```bash
# Telegram
/summary
/summary luty

# CLI
budzet summary
budzet summary luty
budzet summary 2            # numer miesiąca
```

### Ostatnie wydatki (wymaga DB)

```bash
# Telegram
/last
/last 20

# CLI
budzet last
budzet last 20
```

### Wyszukiwanie (wymaga DB)

```bash
# Telegram
/search biedronka

# CLI
budzet search biedronka
```

### Filtrowanie po dacie (wymaga DB)

```bash
# Telegram
/expenses 2026-02-01 2026-02-28

# CLI
budzet expenses 2026-02-01 2026-02-28
```

### Eksport CSV (wymaga DB)

```bash
# Telegram — wysyła plik CSV
/export
/export luty

# CLI — drukuje na stdout lub zapisuje do pliku
budzet export
budzet export luty -o wydatki.csv
```

### Budżety (wymaga DB)

```bash
# Telegram
/budget Jedzenie 2000        # ustaw limit
/budget total 8000           # limit łączny
/budget remove Jedzenie      # usuń
/budgets                     # pokaż z paskami postępu

# CLI
budzet budget set Jedzenie 2000
budzet budget set total 8000
budzet budget remove Jedzenie
budzet budget list
```

Po przekroczeniu 80% lub 100% budżetu wyświetlane jest ostrzeżenie.

### Wykresy (wymaga DB)

```bash
# Telegram — wysyła PNG
/chart                       # kołowy, bieżący miesiąc
/chart bar                   # słupkowy, porównanie 3 miesięcy
/chart luty                  # kołowy, konkretny miesiąc

# CLI — zapisuje PNG do pliku
budzet chart                         # chart.png
budzet chart pie luty -o luty.png
budzet chart bar -o porownanie.png
```

### Wydatki cykliczne (wymaga DB)

```bash
# Telegram
/recurring add 120 siłownia miesięcznie
/recurring list
/recurring remove 5

# CLI
budzet recurring add 120 siłownia -f monthly
budzet recurring list
budzet recurring remove 5
```

Częstotliwość: `daily`/`codziennie`, `weekly`/`tygodniowo`, `monthly`/`miesięcznie`

### Bilans (wymaga DB)

```bash
# Telegram
/balance

# CLI
budzet balance
```

### Inne komendy

```bash
# Kategorie
/categories              # Telegram
budzet categories        # CLI

# Cofnij ostatni wpis
/undo                    # Telegram
budzet undo              # CLI

# Zmień język (pl/en)
/lang                    # Telegram — klawiatura inline
budzet lang en           # CLI

# Ręczna synchronizacja DB → Sheets (tylko CLI)
budzet sync
```

## Kategorie

| # | Kategoria | Podkategorie |
|---|-----------|-------------|
| 1 | Jedzenie | Jedzenie dom, Jedzenie miasto, Jedzenie praca, Alkohol, Woda |
| 2 | Mieszkanie / dom | Czynsz, Prąd, Konserwacja i naprawy, Wyposażenie |
| 3 | Transport | Paliwo do auta, Przeglądy i naprawy auta, Wyposażenie dodatkowe, Bilet komunikacji miejskiej, Bilet PKP/PKS, Taxi |
| 4 | Telekomunikacja | Telefon 1, Internet, Inne |
| 5 | Opieka zdrowotna | Lekarz, Badania, Lekarstwa, Suple |
| 6 | Ubranie | Ubranie zwykłe, Ubranie sportowe, Buty, Dodatki, Inne |
| 7 | Higiena | Kosmetyki, Środki czystości, Fryzjer, Inne |
| 8 | Rozrywka | Siłownia / Basen, Kino / Teatr / Vod, Koncerty, Sprzęt RTV, Książki, Hobby / sprzęt sportowy, Wakacje poza budzetem, Inne |
| 9 | Inne wydatki | Dobroczynność, Prezenty, Oprogramowanie, Edukacja / Szkolenia, Podatki, Zwierzęta |
| 10 | Spłata długów | Kredyt hipoteczny, Kredyt konsumpcyjny, Inne |
| 11 | Budowanie oszczędności | Fundusz awaryjny, Fundusz wydatków nieregularnych, Poduszka finansowa, Konto emerytalne IKE/IKZE, Krypto, Fundusz: wakacje, Fundusz: prezenty świąteczne, Inne |

## Architektura

```
bot/
├── cli.py                 # CLI (argparse, 15 subcommands)
├── main.py                # Telegram bot entry point
├── config.py              # Environment config, API clients
├── categories.py          # Category definitions
├── i18n.py                # Internationalization (pl/en)
├── handlers/
│   ├── commands.py        # Telegram command handlers
│   ├── callbacks.py       # Inline keyboard callbacks
│   └── messages.py        # Message handler (AI parsing)
├── services/
│   ├── ai_parser.py       # OpenAI expense parsing
│   ├── database.py        # PostgreSQL CRUD
│   ├── sheets.py          # Google Sheets read/write
│   ├── storage.py         # SQLite state (pending, undo)
│   └── sync.py            # DB → Sheets sync
├── utils/
│   ├── auth.py            # Authorization decorator
│   └── formatting.py      # Text formatting, charts
├── models/
│   └── expense.py         # Expense validation model
└── locales/
    ├── pl.py              # Polish strings
    └── en.py              # English strings
```

Warstwa usług (`services/`) nie zależy od Telegrama — jest współdzielona przez bota i CLI.

## Tryby pracy

- **Sheets-only** (domyślny) — bez `DATABASE_URL`, dane tylko w Google Sheets. Dostępne: add, summary, categories, undo.
- **DB + Sheets** — z `DATABASE_URL`, pełna funkcjonalność. Dane zapisywane najpierw do DB, potem synchronizowane do Sheets.

## Deploy (Railway)

Szczegóły w [DEPLOY.md](DEPLOY.md).
