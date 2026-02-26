"""Internationalization system for Polish and English."""

from bot.locales import pl, en
from bot.config import USER_LANGUAGE

_LOCALES = {
    "pl": pl.STRINGS,
    "en": en.STRINGS,
}

# Current language (will be per-user when DB is added)
_current_lang = USER_LANGUAGE


def get_lang() -> str:
    return _current_lang


def set_lang(lang: str) -> None:
    global _current_lang
    if lang in _LOCALES:
        _current_lang = lang


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Get translated string by key.

    Args:
        key: Translation key (e.g. "help_text")
        lang: Language code ("pl" or "en"). Uses current language if None.
        **kwargs: Format parameters for the string.
    """
    lang = lang or _current_lang
    strings = _LOCALES.get(lang, _LOCALES["pl"])
    text = strings.get(key, _LOCALES["pl"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text
