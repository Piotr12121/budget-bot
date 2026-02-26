"""Text formatting utilities for expense previews and messages."""

from bot.i18n import t


def build_preview_text(expenses: list[dict]) -> str:
    """Format a list of parsed expenses into a human-readable preview."""
    if len(expenses) == 1:
        e = expenses[0]
        return (
            f"{t('preview_single')}\n"
            f"📅 Data: `{e['date']}`\n"
            f"💰 Kwota: *{e['amount']} PLN*\n"
            f"📂 {e['category']} > {e['subcategory']}\n"
            f"📝 {e['description']}"
        )
    lines = [f"{t('preview_multi')}\n"]
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
            f"{t('saved_single')}\n"
            f"📅 {e['date']}\n"
            f"💰 {e['amount']} PLN\n"
            f"📂 {e['category']} > {e['subcategory']}\n"
            f"📝 {e['description']}"
        )
    lines = [t("saved_multi", n=len(expenses)) + "\n"]
    total = 0
    for i, e in enumerate(expenses, 1):
        lines.append(f"{i}. {e['description']} — {e['amount']} PLN")
        total += e["amount"]
    lines.append(f"\n💰 {t('total')}: {total:.2f} PLN")
    return "\n".join(lines)
