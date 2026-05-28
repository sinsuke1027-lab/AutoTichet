import uuid
from datetime import datetime, timedelta, timezone, UTC
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_user = TokenPayload(
    sub="user-1", name="Test", email="t@t.com", roles=["manager"], tid="tid"
)


def _make_client(mock_db: AsyncMock) -> TestClient:
    from src.api.routers.dashboard import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _stale_task(days_ago: int, status: str = "in_progress") -> MagicMock:
    from src.db.models import Task

    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = f"放置タスク（{days_ago}日前）"
    t.assignee_id = "user-1"
    t.due_date = None
    t.updated_at = datetime.now(UTC) - timedelta(days=days_ago)
    t.status = status
    return t


def _exec_tasks(tasks: list) -> MagicMock:
    m = MagicMock()
    m.scalars.return_value.all.return_value = tasks
    return m


def test_stale_tasks_returns_old_tasks() -> None:
    """15日放置タスクは返却される"""
    task = _stale_task(15)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_exec_tasks([task]))
    client = _make_client(mock_db)
    resp = client.get("/api/v1/dashboard/stale-tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["days_stale"] >= 15


def test_stale_tasks_empty_when_none() -> None:
    """放置タスクが0件のとき空リストを返す"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_exec_tasks([]))
    client = _make_client(mock_db)
    resp = client.get("/api/v1/dashboard/stale-tasks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_stale_tasks_requires_auth() -> None:
    """認証なしは 401"""
    from src.api.routers.dashboard import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/dashboard/stale-tasks")
    assert resp.status_code == 401


def test_stale_tasks_days_stale_is_correct() -> None:
    """days_stale の値が正しく計算される"""
    task = _stale_task(20)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_exec_tasks([task]))
    client = _make_client(mock_db)
    resp = client.get("/api/v1/dashboard/stale-tasks")
    data = resp.json()
    assert data[0]["days_stale"] == 20


def test_stale_tasks_returns_title_and_assignee() -> None:
    """レスポンスに title と assignee_id が含まれる"""
    task = _stale_task(16)
    task.title = "テストタスク"
    task.assignee_id = "user-abc"
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_exec_tasks([task]))
    client = _make_client(mock_db)
    resp = client.get("/api/v1/dashboard/stale-tasks")
    data = resp.json()
    assert data[0]["title"] == "テストタスク"
    assert data[0]["assignee_id"] == "user-abc"
