from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user
from src.api.routers.dashboard import router
from src.api.auth import TokenPayload
from src.db.engine import get_db

_user = TokenPayload(sub="u1", name="U", email="u@u.com", roles=["member"], tid="t")


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


def _make_side_effects() -> list[MagicMock]:
    """週4件 × (タスク集計 + 工数集計) + 期限超過 = 9回のexecuteモック"""
    mocks = []
    for _ in range(4):
        task_m = MagicMock()
        task_m.all.return_value = []
        mocks.append(task_m)
        wh_m = MagicMock()
        wh_m.one.return_value = (0.0, 0.0)
        mocks.append(wh_m)
    overdue_m = MagicMock()
    overdue_m.scalar_one.return_value = 0
    mocks.append(overdue_m)
    return mocks


def test_returns_4_weeks(client: TestClient, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(side_effect=_make_side_effects())
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert "week_start" in data[0]
    assert "planned_hours" in data[0]
    assert "task_count" in data[0]


def test_empty_work_hours_returns_zeros(client: TestClient, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(side_effect=_make_side_effects())
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    assert resp.status_code == 200
    for item in resp.json():
        assert item["planned_hours"] == 0.0
        assert item["actual_hours"] == 0.0
        assert item["task_count"] == 0


def test_overdue_count_in_last_item(client: TestClient, mock_db: AsyncMock) -> None:
    mocks = _make_side_effects()
    mocks[-1].scalar_one.return_value = 3  # 3件期限超過
    mock_db.execute = AsyncMock(side_effect=mocks)
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data[-1]["overdue_count"] == 3
    assert data[0]["overdue_count"] == 0  # 過去週は 0
    assert data[1]["overdue_count"] == 0


def test_older_weeks_have_zero_overdue(client: TestClient, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(side_effect=_make_side_effects())
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    data = resp.json()
    for item in data[:-1]:  # 最新週以外
        assert item["overdue_count"] == 0
