"""OpenAI-based expense parsing service."""

import json
import logging
from datetime import datetime
from bot.config import client_ai
from bot.categories import CATEGORIES_CONTEXT

logger = logging.getLogger(__name__)


def build_system_prompt() -> str:
    """Build the system prompt for expense parsing."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_year = now.year

    return (
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


def parse_expenses(user_text: str) -> list[dict]:
    """Parse user text into expense dicts using OpenAI.

    Returns a list of expense dicts, or empty list for non-expense messages.
    Raises json.JSONDecodeError or Exception on failure.
    """
    system_prompt = build_system_prompt()

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

    return data
