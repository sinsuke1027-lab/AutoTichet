import pytest
from unittest.mock import patch
from datetime import date


def _mock_ollama_response(content: str):
    return {"message": {"content": content}}


def test_parse_returns_structured_dict():
    from widget.clients.ollama_client import OllamaClient
    mock_content = '{"title": "〇〇の件をまとめる", "due_date": "2026-06-09", "assignee_name": "山田", "priority": "high"}'
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient(model="gemma4:e4b")
        result = client.parse("明日までに〇〇の件をまとめる 山田さんに頼む 急ぎで")
    assert result["title"] == "〇〇の件をまとめる"
    assert result["due_date"] == "2026-06-09"
    assert result["assignee_name"] == "山田"
    assert result["priority"] == "high"


def test_parse_extracts_json_from_noisy_response():
    from widget.clients.ollama_client import OllamaClient
    noisy = 'もちろんです。\n```json\n{"title": "報告書作成", "due_date": null, "assignee_name": null, "priority": "medium"}\n```'
    with patch("ollama.chat", return_value=_mock_ollama_response(noisy)):
        client = OllamaClient()
        result = client.parse("報告書を作る")
    assert result["title"] == "報告書作成"
    assert result["due_date"] is None


def test_parse_returns_empty_dict_on_ollama_error():
    from widget.clients.ollama_client import OllamaClient
    with patch("ollama.chat", side_effect=Exception("connection refused")):
        client = OllamaClient()
        result = client.parse("なんか作業する")
    assert result == {"title": None, "due_date": None, "assignee_name": None, "priority": None}


def test_parse_sends_today_date_in_system_prompt():
    from widget.clients.ollama_client import OllamaClient
    captured = {}
    def fake_chat(model, messages, options):
        captured["system"] = messages[0]["content"]
        return _mock_ollama_response('{"title": "test", "due_date": null, "assignee_name": null, "priority": null}')
    with patch("ollama.chat", side_effect=fake_chat):
        client = OllamaClient()
        client.parse("test")
    assert date.today().isoformat() in captured["system"]
