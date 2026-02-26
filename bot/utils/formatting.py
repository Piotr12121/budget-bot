"""Text formatting utilities for expense previews and messages."""


def build_preview_text(expenses: list[dict]) -> str:
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


def build_save_confirmation(expenses: list[dict]) -> str:
    """Build confirmation text after saving expenses."""
    if len(expenses) == 1:
        e = expenses[0]
        return (
            f"✅ Zapisano!\n"
            f"📅 {e['date']}\n"
            f"💰 {e['amount']} PLN\n"
            f"📂 {e['category']} > {e['subcategory']}\n"
            f"📝 {e['description']}"
        )
    lines = [f"✅ Zapisano {len(expenses)} wydatków!\n"]
    total = 0
    for i, e in enumerate(expenses, 1):
        lines.append(f"{i}. {e['description']} — {e['amount']} PLN")
        total += e["amount"]
    lines.append(f"\n💰 Razem: {total:.2f} PLN")
    return "\n".join(lines)
