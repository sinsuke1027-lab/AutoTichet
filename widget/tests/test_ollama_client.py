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
    assert result == {"title": None, "due_date": None, "assignee_name": None, "priority": None, "clarifying_question": None}


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


# --- Vision テスト ---

def test_parse_image_returns_structured_dict():
    from widget.clients.ollama_client import OllamaClient
    from pathlib import Path

    mock_content = (
        '{"title": "報告書作成", "due_date": "2026-06-20", '
        '"assignee_name": "田中", "priority": "high", '
        '"description_hint": "月次報告書の作成が必要"}'
    )
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient(model="gemma4:e4b")
        result = client.parse_image(Path("/tmp/screen.png"))
    assert result["title"] == "報告書作成"
    assert result["due_date"] == "2026-06-20"
    assert result["description_hint"] == "月次報告書の作成が必要"


def test_parse_image_returns_empty_on_error():
    from widget.clients.ollama_client import OllamaClient
    from pathlib import Path

    with patch("ollama.chat", side_effect=Exception("vision error")):
        client = OllamaClient()
        result = client.parse_image(Path("/tmp/screen.png"))
    assert result["title"] is None
    assert result["description_hint"] is None


def test_parse_image_passes_image_path_to_ollama():
    from widget.clients.ollama_client import OllamaClient
    from pathlib import Path

    captured: dict = {}
    test_path = Path("/tmp/test.png")

    def fake_chat(model, messages, options):
        captured["images"] = messages[0]["images"]
        return _mock_ollama_response(
            '{"title": "test", "due_date": null, "assignee_name": null, '
            '"priority": null, "description_hint": null}'
        )

    with patch("ollama.chat", side_effect=fake_chat):
        client = OllamaClient()
        client.parse_image(test_path)

    assert captured["images"] == [str(test_path)]


# --- 2B: clarifying_question / generate_description ---

def test_parse_returns_clarifying_question():
    from widget.clients.ollama_client import OllamaClient
    mock_content = (
        '{"title": "報告書作成", "due_date": null, "assignee_name": null, '
        '"priority": "medium", "clarifying_question": "目的を一言で教えてください"}'
    )
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient()
        result = client.parse("報告書を作る")
    assert result["clarifying_question"] == "目的を一言で教えてください"


def test_parse_clarifying_question_can_be_null():
    from widget.clients.ollama_client import OllamaClient
    mock_content = (
        '{"title": "定例MTG", "due_date": null, "assignee_name": null, '
        '"priority": "low", "clarifying_question": null}'
    )
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient()
        result = client.parse("定例MTGの準備")
    assert result["clarifying_question"] is None


def test_generate_description_returns_string():
    from widget.clients.ollama_client import OllamaClient
    with patch("ollama.chat", return_value=_mock_ollama_response("月次報告書を作成します。期限は月末です。")):
        client = OllamaClient()
        result = client.generate_description(
            original_text="月次報告書を作る",
            answer="月末締め切りの提出用です",
        )
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_description_returns_empty_on_error():
    from widget.clients.ollama_client import OllamaClient
    with patch("ollama.chat", side_effect=Exception("error")):
        client = OllamaClient()
        result = client.generate_description("テキスト", "回答")
    assert result == ""
