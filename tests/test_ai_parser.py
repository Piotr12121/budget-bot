"""Tests for AI parser service."""

import json
import pytest
from unittest.mock import patch, MagicMock
from bot.services.ai_parser import parse_expenses, build_system_prompt


class TestBuildSystemPrompt:
    def test_contains_current_date(self):
        prompt = build_system_prompt()
        assert "Dzisiejsza data to:" in prompt

    def test_contains_categories(self):
        prompt = build_system_prompt()
        assert "Jedzenie" in prompt
        assert "Transport" in prompt

    def test_contains_json_format_instruction(self):
        prompt = build_system_prompt()
        assert "JSON array" in prompt


class TestParseExpenses:
    @patch("bot.services.ai_parser.client_ai")
    def test_single_expense(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps([{
            "amount": 50.0,
            "date": "2026-02-26",
            "category": "Jedzenie",
            "subcategory": "Jedzenie dom",
            "description": "biedronka",
        }])
        mock_client.chat.completions.create.return_value = mock_response

        result = parse_expenses("50 zł biedronka")
        assert len(result) == 1
        assert result[0]["amount"] == 50.0
        assert result[0]["category"] == "Jedzenie"

    @patch("bot.services.ai_parser.client_ai")
    def test_multiple_expenses(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps([
            {"amount": 50.0, "date": "2026-02-26", "category": "Jedzenie",
             "subcategory": "Jedzenie dom", "description": "biedronka"},
            {"amount": 120.0, "date": "2026-02-26", "category": "Rozrywka",
             "subcategory": "Siłownia / Basen", "description": "silownia"},
        ])
        mock_client.chat.completions.create.return_value = mock_response

        result = parse_expenses("biedronka 50, silownia 120")
        assert len(result) == 2

    @patch("bot.services.ai_parser.client_ai")
    def test_non_expense_returns_empty(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "[]"
        mock_client.chat.completions.create.return_value = mock_response

        result = parse_expenses("cześć, jak się masz?")
        assert result == []

    @patch("bot.services.ai_parser.client_ai")
    def test_strips_markdown_code_blocks(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '```json\n[{"amount": 50.0, "date": "2026-02-26", "category": "Jedzenie", "subcategory": "Jedzenie dom", "description": "test"}]\n```'
        mock_client.chat.completions.create.return_value = mock_response

        result = parse_expenses("test 50")
        assert len(result) == 1

    @patch("bot.services.ai_parser.client_ai")
    def test_wraps_single_dict_in_list(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "amount": 50.0, "date": "2026-02-26", "category": "Jedzenie",
            "subcategory": "Jedzenie dom", "description": "test"
        })
        mock_client.chat.completions.create.return_value = mock_response

        result = parse_expenses("test 50")
        assert isinstance(result, list)
        assert len(result) == 1

    @patch("bot.services.ai_parser.client_ai")
    def test_invalid_json_raises(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "not valid json {{"
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(json.JSONDecodeError):
            parse_expenses("test")
