import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="u1", roles=["member"], department_tags=[])


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_similar_route_exists(client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.get("/api/v1/tasks/similar?q=テスト")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_similar_requires_min_3_chars(client: TestClient) -> None:
    resp = client.get("/api/v1/tasks/similar?q=ab")
    assert resp.status_code == 422


def test_similar_returns_scored_results(client: TestClient, mock_db: AsyncMock) -> None:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.title = "テストタスク作成"
    task.status = "not_started"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [task]
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.get("/api/v1/tasks/similar?q=テストタスク")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["score"] >= 0.5


def test_similar_excludes_low_score_results(client: TestClient, mock_db: AsyncMock) -> None:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.title = "全く関係ない題名"
    task.status = "not_started"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [task]
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.get("/api/v1/tasks/similar?q=テストタスク作成")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0
