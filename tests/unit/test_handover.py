import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.models.config import Settings

_FAKE_SETTINGS = Settings(
    gemini_api_key="fake-key",
    database_url="postgresql+asyncpg://x:x@localhost/x",
)
_EMPTY_SETTINGS = Settings(
    gemini_api_key="",
    database_url="postgresql+asyncpg://x:x@localhost/x",
)

_member_user = TokenPayload(
    sub="user-1", name="Member", email="m@t.com", roles=["member"], tid="tid"
)
_leader_user = TokenPayload(
    sub="leader-1", name="Leader", email="l@t.com", roles=["leader"], tid="tid"
)


def _make_client(mock_db: AsyncMock, user: TokenPayload = _member_user) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_task(
    *,
    title: str = "テスト作業",
    status: str = "in_progress",
    priority: str = "medium",
    due_date: object = None,
    description: str | None = None,
    comments: list | None = None,
) -> MagicMock:
    from src.db.models import Task

    task = MagicMock(spec=Task)
    task.title = title
    task.status = status
    task.priority = priority
    task.due_date = due_date
    task.description = description
    task.comments = comments if comments is not None else []
    return task


def _make_db(tasks: list) -> AsyncMock:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def test_generate_handover_own_tasks() -> None:
    """assignee_id=None → 自分の未完了タスクで引き継ぎ書生成・200"""
    mock_task = _make_task(title="設計書を書く")
    mock_db = _make_db([mock_task])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(return_value="# 引き継ぎ書\n\n内容")
            resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 200
    data = resp.json()
    assert "document" in data
    assert data["document"] != ""


def test_generate_handover_for_member_by_leader() -> None:
    """leader ロールで他メンバーの assignee_id を指定 → 200"""
    mock_task = _make_task(title="レポート作成")
    mock_db = _make_db([mock_task])
    client = _make_client(mock_db, user=_leader_user)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(return_value="# 引き継ぎ書")
            resp = client.post(
                "/api/v1/tasks/generate-handover",
                json={"assignee_id": "other-user-999"},
            )
    assert resp.status_code == 200


def test_generate_handover_member_cannot_target_others() -> None:
    """member ロールで他人の assignee_id を指定 → 403"""
    mock_db = _make_db([])
    client = _make_client(mock_db, user=_member_user)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        resp = client.post(
            "/api/v1/tasks/generate-handover",
            json={"assignee_id": "other-user-999"},
        )
    assert resp.status_code == 403


def test_generate_handover_no_tasks() -> None:
    """未完了タスクなし → 200・document が空でない"""
    mock_db = _make_db([])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(return_value="未完了タスクはありません。")
            resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 200
    assert resp.json()["document"] != ""


def test_generate_handover_gemini_error() -> None:
    """GeminiProvider が例外 → 503"""
    mock_task = _make_task()
    mock_db = _make_db([mock_task])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(side_effect=RuntimeError("API error"))
            resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 503


def test_generate_handover_no_api_key() -> None:
    """gemini_api_key="" → 503"""
    mock_db = _make_db([])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_EMPTY_SETTINGS):
        resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 503
