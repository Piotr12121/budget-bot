"""Tests for i18n translation system."""

from bot.i18n import t, set_lang, get_lang


class TestI18n:
    def setup_method(self):
        set_lang("pl")

    def test_default_language_is_pl(self):
        set_lang("pl")
        assert get_lang() == "pl"

    def test_switch_to_english(self):
        set_lang("en")
        assert get_lang() == "en"

    def test_pl_translation(self):
        set_lang("pl")
        assert t("access_denied") == "🔒 Brak dostępu."

    def test_en_translation(self):
        set_lang("en")
        assert t("access_denied") == "🔒 Access denied."

    def test_format_params(self):
        set_lang("pl")
        result = t("start_greeting", user_id=12345)
        assert "12345" in result

    def test_unknown_key_returns_key(self):
        result = t("nonexistent_key_xyz")
        assert result == "nonexistent_key_xyz"

    def test_explicit_lang_param(self):
        set_lang("pl")
        result = t("access_denied", lang="en")
        assert result == "🔒 Access denied."

    def test_invalid_lang_falls_back_to_pl(self):
        result = t("access_denied", lang="xx")
        assert result == "🔒 Brak dostępu."
