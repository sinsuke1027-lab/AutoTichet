"""LLM 抽出レスポンスのパース堅牢性テスト（issue #17）"""

from src.providers.parsing import parse_extracted_tasks

_VALID_TASK = {
    "is_task": True,
    "title": "勤怠を登録する",
    "assignee_name": None,
    "deadline": None,
    "priority": "medium",
    "category": "その他",
    "visibility": "team",
    "confidence_score": 0.9,
}


def test_parses_valid_json_list() -> None:
    import json

    result = parse_extracted_tasks(json.dumps([_VALID_TASK]), "email")
    assert len(result) == 1
    assert result[0].title == "勤怠を登録する"
    assert result[0].source_type == "email"


def test_returns_empty_on_malformed_json() -> None:
    # 途中で切れた不正 JSON でも例外を投げず空リストを返す
    result = parse_extracted_tasks('[{"is_task": true, "title": "壊れ', "email")
    assert result == []


def test_returns_empty_on_none() -> None:
    assert parse_extracted_tasks(None, "email") == []


def test_unwraps_dict_with_task_list() -> None:
    # LLM が配列でなく {"tasks": [...]} の dict で返すケースに対応
    import json

    result = parse_extracted_tasks(json.dumps({"tasks": [_VALID_TASK]}), "email")
    assert len(result) == 1
    assert result[0].title == "勤怠を登録する"


def test_skips_non_dict_elements() -> None:
    # 要素が dict でない（文字列等）混入時は当該要素をスキップ
    import json

    result = parse_extracted_tasks(json.dumps(["ただの文字列", _VALID_TASK]), "email")
    assert len(result) == 1


def test_strips_markdown_code_fence() -> None:
    # ```json ... ``` で囲まれた応答もパースできる
    import json

    fenced = "```json\n" + json.dumps([_VALID_TASK]) + "\n```"
    result = parse_extracted_tasks(fenced, "email")
    assert len(result) == 1


def test_skips_invalid_task_fields() -> None:
    # バリデーションに失敗する要素はスキップし、他は通す
    import json

    bad = {**_VALID_TASK, "priority": "INVALID_PRIORITY"}
    result = parse_extracted_tasks(json.dumps([bad, _VALID_TASK]), "email")
    assert len(result) == 1
