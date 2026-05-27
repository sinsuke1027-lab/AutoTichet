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


def test_generate_subtasks_route_exists() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = [r.path for r in app.routes]
    assert "/api/v1/tasks/{task_id}/generate-subtasks" in routes


def test_generate_subtasks_task_not_found() -> None:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/generate-subtasks")
    assert resp.status_code == 404


def test_generate_subtasks_returns_suggestions() -> None:
    from src.db.models import Task

    mock_task = MagicMock(spec=Task)
    mock_task.id = uuid.uuid4()
    mock_task.title = "議事録のまとめ"
    mock_task.description = "先週の会議内容を整理してチームに共有する"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)

    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.generate_subtasks = AsyncMock(
            return_value=["会議メモを収集する", "要点を箇条書きにする", "Teamsに投稿する"]
        )
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/generate-subtasks")

    assert resp.status_code == 200
    data = resp.json()
    assert "suggested_titles" in data
    assert data["suggested_titles"] == ["会議メモを収集する", "要点を箇条書きにする", "Teamsに投稿する"]


def test_generate_subtasks_requires_auth() -> None:
    app2 = FastAPI()
    app2.include_router(router)
    client = TestClient(app2, raise_server_exceptions=False)
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/generate-subtasks")
    assert resp.status_code == 401


def test_generate_subtasks_empty_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """google_api_key が空の場合は 503 を返す"""
    from src.models.config import Settings, get_settings  # noqa: F401

    empty_settings = Settings(
        google_api_key="",
        database_url="postgresql+asyncpg://x:x@localhost/x",
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_task = MagicMock()
    mock_task.id = uuid.uuid4()
    mock_task.title = "テスト"
    mock_task.description = None
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)

    with patch("src.api.routers.tasks_crud.get_settings", return_value=empty_settings):
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/generate-subtasks")

    assert resp.status_code == 503


def test_generate_subtasks_provider_error() -> None:
    """GeminiProvider が例外を発生させた場合は 503 を返す"""
    from src.db.models import Task

    mock_task = MagicMock(spec=Task)
    mock_task.id = uuid.uuid4()
    mock_task.title = "テスト"
    mock_task.description = None

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)

    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.generate_subtasks = AsyncMock(side_effect=RuntimeError("API unavailable"))
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/generate-subtasks")

    assert resp.status_code == 503
