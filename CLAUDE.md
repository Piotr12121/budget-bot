# Budzet Bot — Developer Guide

## Project Overview

Personal budget tracking Telegram bot with Google Sheets storage and PostgreSQL database. Uses OpenAI (gpt-4o-mini) to parse natural-language expense messages into structured data (amount, date, category, subcategory, description).

## Tech Stack

- **Python 3.12** — runtime (`runtime.txt`)
- **python-telegram-bot[job-queue]** — Telegram Bot API
- **OpenAI API (gpt-4o-mini)** — expense parsing via `bot/services/ai_parser.py`
- **PostgreSQL + psycopg2** — primary database (optional, graceful degradation)
- **Google Sheets (gspread)** — spreadsheet storage (always available)
- **matplotlib** — chart generation
- **pydantic** — data models
- **Deployment**: Railway (Railpack builder)

## Architecture

```
bot/
├── main.py              # Entry point, handler registration, job scheduler
├── config.py            # Env vars, Google Sheets client, OpenAI client, month mappings
├── categories.py        # Category/subcategory definitions (OrderedDict), emojis
├── i18n.py              # Internationalization (pl/en), t() function
├── cli.py               # CLI tool (mirrors all Telegram commands)
├── models/
│   └── expense.py       # Pydantic Expense model
├── handlers/
│   ├── commands.py      # All /command handlers
│   ├── messages.py      # Free-text message handler (AI parsing + income)
│   └── callbacks.py     # Inline button callbacks (save/cancel/edit)
├── services/
│   ├── ai_parser.py     # OpenAI expense parsing
│   ├── database.py      # PostgreSQL: connection pool, migrations, all queries
│   ├── sheets.py        # Google Sheets read/write
│   ├── storage.py       # In-memory pending expense storage (SQLite)
│   └── sync.py          # DB → Sheets sync (unsynced expenses)
├── locales/
│   ├── pl.py            # Polish translations
│   └── en.py            # English translations
└── utils/
    ├── auth.py          # @authorized decorator (checks ALLOWED_USER_ID)
    └── formatting.py    # Preview text builder, chart generation
```

## Key Patterns

### Dual Storage (DB + Sheets)

- **PostgreSQL** is the primary database for queries, charts, search, budgets, recurring, income
- **Google Sheets** is always written to for backward compatibility
- `database.is_available()` controls graceful degradation — if no DB, bot runs in Sheets-only mode
- Commands like `/chart`, `/budget`, `/search`, `/last`, `/export` require the database
- `/summary` works with both (DB preferred, Sheets fallback)

### Adding a New Telegram Command

1. Add handler function in `bot/handlers/commands.py` (use `@authorized` decorator)
2. Register in `bot/main.py` with `CommandHandler`
3. Add to help text in **both** `bot/locales/en.py` and `bot/locales/pl.py`
4. Optionally add CLI equivalent in `bot/cli.py`

### Adding Translations

All user-facing strings go through `t("key", **kwargs)` from `bot/i18n.py`. Add the key to both `bot/locales/pl.py` and `bot/locales/en.py` STRINGS dicts.

### Database Migrations

SQL files in `migrations/` directory, named `NNN_description.sql`. Automatically applied on startup by `database.init_db()` → `_run_migrations()`. Version tracked in `schema_version` table.

### Expense Flow

1. User sends text → `messages.handle_message()`
2. AI parses via `ai_parser.parse_expenses()` → returns list of expense dicts
3. Stored as pending in `storage.save_pending()` with UUID
4. User sees preview with Save/Cancel/Edit buttons
5. On Save → `callbacks.handle_callback()` writes to DB + Sheets
6. Background job syncs any unsynced DB entries to Sheets every 5 min

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | Telegram Bot API token |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `SPREADSHEET_NAME` | Yes | Google Sheets spreadsheet name |
| `SHEET_TAB_NAME` | Yes | Sheet tab name (e.g., `Bot_Data`) |
| `ALLOWED_USER_ID` | Yes | Telegram user ID (single-user bot) |
| `DATABASE_URL` | No | PostgreSQL connection string (enables full features) |
| `GOOGLE_CREDENTIALS_BASE64` | No | Base64-encoded service account JSON (Railway) |
| `USER_LANGUAGE` | No | Default language: `pl` or `en` (default: `pl`) |

## Google Sheets Column Format

`date | amount | category | subcategory | description | original_text | month_name | day_number`

- Amount uses comma as decimal separator in Sheets
- Month names are Polish (Styczeń, Luty, etc.) — defined in `config.MONTHS_MAPPING`

## Deployment (Railway)

- **Builder**: Railpack (auto-detected)
- **Start command**: `python -m bot.main` (set in `railway.toml`)
- **Procfile**: `worker: python -m bot.main` (backup, but `railway.toml` takes precedence)
- Railway auto-deploys on push to `main`
- PostgreSQL provisioned as a separate Railway service, linked via `DATABASE_URL`

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python -m bot.main

# Use CLI
python -m bot.cli summary
python -m bot.cli add "50 biedronka zakupy"
python -m bot.cli import-sheets -v

# Run with Railway env vars (connects to production DB)
railway run python -m bot.cli import-sheets
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Tests are in `tests/` — unit tests for parsing, categories, formatting, database, sync, CLI, etc. Uses mocking for external services (OpenAI, Sheets, Telegram).

## Common Pitfalls

- **railway.toml** must set `startCommand` — without it, Railpack auto-detects and may pick the wrong file
- Month names are always Polish regardless of language setting (used as DB/Sheets keys)
- `@authorized` decorator checks `ALLOWED_USER_ID` — single-user bot, not multi-tenant
- Income is detected by `+amount description` pattern (regex in `messages.py`), not by AI
- The `i18n` system is global (not per-user) — `set_lang()` changes it for everyone
