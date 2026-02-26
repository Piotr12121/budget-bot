"""Single source of truth for categories and subcategories."""

from collections import OrderedDict

CATEGORIES: OrderedDict[str, list[str]] = OrderedDict([
    ("Jedzenie", [
        "Jedzenie dom", "Jedzenie miasto", "Jedzenie praca", "Alkohol", "Woda",
    ]),
    ("Mieszkanie / dom", [
        "Czynsz", "Prąd", "Konserwacja i naprawy", "Wyposażenie",
    ]),
    ("Transport", [
        "Paliwo do auta", "Przeglądy i naprawy auta", "Wyposażenie dodatkowe",
        "Bilet komunikacji miejskiej", "Bilet PKP/PKS", "Taxi",
    ]),
    ("Telekomunikacja", [
        "Telefon 1", "Internet", "Inne",
    ]),
    ("Opieka zdrowotna", [
        "Lekarz", "Badania", "Lekarstwa", "Suple",
    ]),
    ("Ubranie", [
        "Ubranie zwykłe", "Ubranie sportowe", "Buty", "Dodatki", "Inne",
    ]),
    ("Higiena", [
        "Kosmetyki", "Środki czystości", "Fryzjer", "Inne",
    ]),
    ("Rozrywka", [
        "Siłownia / Basen", "Kino / Teatr / Vod", "Koncerty", "Sprzęt RTV",
        "Książki", "Hobby / sprzęt sportowy", "Wakacje poza budzetem", "Inne",
    ]),
    ("Inne wydatki", [
        "Dobroczynność", "Prezenty", "Oprogramowanie", "Edukacja / Szkolenia",
        "Podatki", "Zwierzęta",
    ]),
    ("Spłata długów", [
        "Kredyt hipoteczny", "Kredyt konsumpcyjny", "Inne",
    ]),
    ("Budowanie oszczędności", [
        "Fundusz awaryjny", "Fundusz wydatków nieregularnych", "Poduszka finansowa",
        "Konto emerytalne IKE/IKZE", "Krypto", "Fundusz: wakacje",
        "Fundusz: prezenty świąteczne", "Inne",
    ]),
])

CATEGORY_EMOJIS = {
    "Jedzenie": "🍔",
    "Mieszkanie / dom": "🏠",
    "Transport": "🚗",
    "Telekomunikacja": "📱",
    "Opieka zdrowotna": "🏥",
    "Ubranie": "👕",
    "Higiena": "🧴",
    "Rozrywka": "🎮",
    "Inne wydatki": "📦",
    "Spłata długów": "💳",
    "Budowanie oszczędności": "💰",
}

CATEGORY_NAMES = list(CATEGORIES.keys())


def build_categories_context() -> str:
    """Build the category context string for AI prompts."""
    lines = ["Główne kategorie i podkategorie:"]
    for i, (cat, subs) in enumerate(CATEGORIES.items(), 1):
        lines.append(f"{i}. {cat} ({', '.join(subs)})")
    return "\n".join(lines)


def build_categories_display() -> str:
    """Build the formatted display string for /categories command."""
    lines = []
    for i, (cat, subs) in enumerate(CATEGORIES.items(), 1):
        emoji = CATEGORY_EMOJIS.get(cat, "📂")
        lines.append(f"{emoji} *{i}. {cat}*")
        lines.append(f"   {' · '.join(subs)}")
        lines.append("")
    return "\n".join(lines)


CATEGORIES_CONTEXT = build_categories_context()
CATEGORIES_DISPLAY = build_categories_display()
