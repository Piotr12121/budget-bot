"""Text formatting utilities for expense previews, messages, and charts."""

from io import BytesIO
from bot.i18n import t
from bot.categories import CATEGORY_EMOJIS


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


# --- Chart generation ---

_CHART_COLORS = [
    "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
    "#FF9F40", "#C9CBCF", "#7BC225", "#E74C3C", "#3498DB", "#2ECC71",
]


def generate_pie_chart(categories_data: dict[str, float], title: str) -> BytesIO:
    """Generate a pie chart from category totals. Returns PNG BytesIO."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(categories_data.keys())
    values = list(categories_data.values())
    colors = _CHART_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct=lambda pct: f"{pct:.1f}%\n({pct/100*sum(values):.0f} PLN)",
        colors=colors,
        startangle=140,
        textprops={"fontsize": 9},
    )
    ax.set_title(title, fontsize=14, fontweight="bold")

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_bar_chart(months_data: dict[str, dict[str, float]], title: str) -> BytesIO:
    """Generate a grouped bar chart comparing months. Returns PNG BytesIO."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    months = list(months_data.keys())
    all_cats = set()
    for data in months_data.values():
        all_cats.update(data.keys())
    categories = sorted(all_cats)

    x = np.arange(len(months))
    width = 0.8 / max(len(categories), 1)

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, cat in enumerate(categories):
        values = [months_data[m].get(cat, 0) for m in months]
        color = _CHART_COLORS[i % len(_CHART_COLORS)]
        bars = ax.bar(x + i * width, values, width, label=cat, color=color)
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height(),
                        f"{val:.0f}", ha="center", va="bottom", fontsize=7)

    ax.set_xlabel("Miesiąc")
    ax.set_ylabel("PLN")
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xticks(x + width * len(categories) / 2)
    ax.set_xticklabels(months)
    ax.legend(loc="upper right", fontsize=8)

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf
