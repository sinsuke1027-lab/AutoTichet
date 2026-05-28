import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")


def _make_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_task(
    *,
    due_date=None,
    sub_assignees=None,
    description=None,
) -> MagicMock:
    from src.db.models import Task

    task = MagicMock(spec=Task)
    task.id = uuid.uuid4()
    task.title = "テストタスク"
    task.description = description
    task.due_date = due_date
    task.sub_assignees = sub_assignees if sub_assignees is not None else []
    return task


def test_clarify_due_date_missing() -> None:
    """due_date が null の場合 due_date issue が返る"""
    from src.models.config import Settings

    fake_settings = Settings(gemini_api_key="fake-key", database_url="postgresql+asyncpg://x:x@localhost/x")
    mock_task = _make_task(due_date=None, sub_assignees=[MagicMock()])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=fake_settings):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.clarify_requirements = AsyncMock(return_value=None)
            resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "due_date" in fields
    assert "assignees" not in fields


def test_clarify_assignees_missing() -> None:
    """assignees が空の場合 assignees issue が返る"""
    from datetime import date

    from src.models.config import Settings

    fake_settings = Settings(gemini_api_key="fake-key", database_url="postgresql+asyncpg://x:x@localhost/x")
    mock_task = _make_task(due_date=date.today(), sub_assignees=[])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=fake_settings):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.clarify_requirements = AsyncMock(return_value=None)
            resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "assignees" in fields
    assert "due_date" not in fields


def test_clarify_no_issues() -> None:
    """due_date あり・assignees あり・Gemini 問題なし → issues 空"""
    from datetime import date

    from src.models.config import Settings

    fake_settings = Settings(gemini_api_key="fake-key", database_url="postgresql+asyncpg://x:x@localhost/x")
    mock_task = _make_task(
        due_date=date.today(),
        sub_assignees=[MagicMock()],
        description="ユーザーが〇〇できたら完了とする",
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=fake_settings):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.clarify_requirements = AsyncMock(return_value=None)
            resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    assert resp.json()["issues"] == []


def test_clarify_task_not_found() -> None:
    """タスク不存在 → 404"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/clarify-requirements")
    assert resp.status_code == 404


def test_clarify_no_api_key_returns_rule_issues_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini APIキー未設定 → ルールチェック結果のみ返し 503 にならない"""
    from src.models.config import Settings

    empty_settings = Settings(
        gemini_api_key="",
        database_url="postgresql+asyncpg://x:x@localhost/x",
    )

    mock_task = _make_task(due_date=None, sub_assignees=[])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=empty_settings):
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "due_date" in fields
    assert "assignees" in fields
    assert "description" not in fields


def test_clarify_gemini_detects_issue() -> None:
    """Gemini が有問題と判定 → description issue が含まれる"""
    from datetime import date

    from src.models.config import Settings

    fake_settings = Settings(gemini_api_key="fake-key", database_url="postgresql+asyncpg://x:x@localhost/x")
    mock_task = _make_task(
        due_date=date.today(),
        sub_assignees=[MagicMock()],
        description="なんかやる",
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=fake_settings):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.clarify_requirements = AsyncMock(
                return_value="「〇〇が完了したら終了」のような受け入れ基準を追加してください"
            )
            resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    desc_issues = [i for i in data["issues"] if i["field"] == "description"]
    assert len(desc_issues) == 1
    assert desc_issues[0]["suggestion"] is not None
    assert desc_issues[0]["suggestion"] != ""


def test_clarify_gemini_exception_returns_rule_issues() -> None:
    """Gemini が例外を発生させても 200 でルールチェック結果を返す"""
    from src.models.config import Settings

    fake_settings = Settings(gemini_api_key="fake-key", database_url="postgresql+asyncpg://x:x@localhost/x")
    mock_task = _make_task(due_date=None, sub_assignees=[])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=fake_settings):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.clarify_requirements = AsyncMock(side_effect=RuntimeError("API unavailable"))
            resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "due_date" in fields
    assert "assignees" in fields
    assert "description" not in fields
