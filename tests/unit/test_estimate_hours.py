from unittest.mock import AsyncMock, MagicMock

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


def _exec_aggregate(
    avg_hours: float | None,
    task_count: int,
    min_hours: float | None = None,
    max_hours: float | None = None,
) -> MagicMock:
    """aggregate クエリ結果（.one() で row を返す）を模倣するモック。"""
    row = MagicMock()
    row.avg = avg_hours
    row.min = min_hours
    row.max = max_hours
    row.cnt = task_count
    m = MagicMock()
    m.one.return_value = row
    return m


def test_estimate_hours_with_matching_completed_tasks() -> None:
    """タグ一致あり・完了タスクがある場合 avg > 0, task_count >= 1 を返す。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=3.5, task_count=2, min_hours=2.0, max_hours=5.0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=backend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_actual_hours"] == 3.5
    assert data["task_count"] == 2
    assert data["min_actual_hours"] == 2.0
    assert data["max_actual_hours"] == 5.0


def test_estimate_hours_no_matching_tags() -> None:
    """タグ一致なしのとき task_count: 0, avg/min/max: null を返す。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=None, task_count=0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None
    assert data["min_actual_hours"] is None
    assert data["max_actual_hours"] is None


def test_estimate_hours_empty_tags() -> None:
    """タグ空リストのとき DB クエリ不要で task_count: 0 を返す。"""
    mock_db = AsyncMock()
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None
    assert data["min_actual_hours"] is None
    assert data["max_actual_hours"] is None
    mock_db.execute.assert_not_called()


def test_estimate_hours_excludes_in_progress_tasks() -> None:
    """進行中タスクは集計対象外（avg=None, task_count=0 を返す）。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=None, task_count=0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=design")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None


def test_estimate_hours_multiple_tags_or_search() -> None:
    """複数タグで OR 検索し、いずれか一致タスクが集計される。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=5.0, task_count=3, min_hours=3.0, max_hours=7.0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=backend&tags=frontend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_actual_hours"] == 5.0
    assert data["task_count"] == 3
    assert data["min_actual_hours"] == 3.0
    assert data["max_actual_hours"] == 7.0


def test_estimate_hours_returns_min_max() -> None:
    """単一タグで min/max/avg が正しく返る。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=2.5, task_count=4, min_hours=1.0, max_hours=4.0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=design")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_actual_hours"] == 2.5
    assert data["min_actual_hours"] == 1.0
    assert data["max_actual_hours"] == 4.0
    assert data["task_count"] == 4
