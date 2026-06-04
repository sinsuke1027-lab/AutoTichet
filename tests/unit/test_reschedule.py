import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app_f = FastAPI()
    app_f.include_router(router)
    app_f.dependency_overrides[get_current_user] = lambda: _user
    app_f.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app_f, raise_server_exceptions=False)


def test_reschedule_route_exists() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = [r.path for r in app.routes]
    assert "/api/v1/tasks/{task_id}/reschedule" in routes


def test_reschedule_returns_404_for_missing_task(client: TestClient, mock_db: AsyncMock) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)
    resp = client.post(
        f"/api/v1/tasks/{uuid.uuid4()}/reschedule",
        json={"new_due_date": "2026-06-01"},
    )
    assert resp.status_code == 404


def test_list_tasks_accepts_due_date_gte(client: TestClient, mock_db: AsyncMock) -> None:
    # _visible_user_ids が ProjectMember クエリを1回実行するため scope_mock が先頭に必要
    scope_mock = MagicMock()
    scope_mock.scalars.return_value.all.return_value = []
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[scope_mock, count_mock, result_mock])
    resp = client.get("/api/v1/tasks?due_date_gte=2026-06-01")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_tasks_accepts_assignee_ids(client: TestClient, mock_db: AsyncMock) -> None:
    # _visible_user_ids が ProjectMember クエリを1回実行するため scope_mock が先頭に必要
    scope_mock = MagicMock()
    scope_mock.scalars.return_value.all.return_value = []
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[scope_mock, count_mock, result_mock])
    resp = client.get("/api/v1/tasks?assignee_ids=user-1&assignee_ids=user-2")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
