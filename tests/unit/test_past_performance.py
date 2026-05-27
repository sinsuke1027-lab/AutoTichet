import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")


def _make_client(mock_db: AsyncMock) -> TestClient:
    from src.api.routers.task_details import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _task_mock() -> MagicMock:
    from src.db.models import Task

    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    return t


def _exec_task(task: MagicMock | None) -> MagicMock:
    m = MagicMock()
    m.scalar_one_or_none.return_value = task
    return m


def _exec_tags(tags: list[str]) -> MagicMock:
    m = MagicMock()
    m.scalars.return_value.all.return_value = tags
    return m


def _exec_agg(
    avg: float | None,
    min_h: float | None,
    max_h: float | None,
    count: int,
) -> MagicMock:
    row = MagicMock()
    row.avg_hours = avg
    row.min_hours = min_h
    row.max_hours = max_h
    row.task_count = count
    m = MagicMock()
    m.one.return_value = row
    return m


def _exec_similar(rows: list) -> MagicMock:
    m = MagicMock()
    m.all.return_value = rows
    return m


def _similar_row(title: str, actual_hours: float) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.title = title
    row.actual_hours = actual_hours
    return row


def test_past_performance_no_tags() -> None:
    """タグなしタスクは task_count=0 の空レスポンスを返す"""
    task = _task_mock()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags([]),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["similar_tasks"] == []
    assert data["avg_actual_hours"] is None


def test_past_performance_with_matching_tasks() -> None:
    """類似完了タスクがある場合、集計値と一覧を返す"""
    task = _task_mock()
    mock_db = AsyncMock()
    similar = [
        _similar_row("月次報告（4月）", 2.0),
        _similar_row("月次報告（3月）", 3.0),
    ]
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["報告"]),
        _exec_agg(2.5, 2.0, 3.0, 2),
        _exec_similar(similar),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 2
    assert data["avg_actual_hours"] == 2.5
    assert data["min_actual_hours"] == 2.0
    assert data["max_actual_hours"] == 3.0
    assert len(data["similar_tasks"]) == 2
    assert data["similar_tasks"][0]["title"] == "月次報告（4月）"
    assert data["similar_tasks"][0]["actual_hours"] == 2.0


def test_past_performance_no_completed_tasks() -> None:
    """タグ一致タスクはあるが実績なし（未完了 or actual_hours=null）"""
    task = _task_mock()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["報告"]),
        _exec_agg(None, None, None, 0),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None
    assert data["similar_tasks"] == []


def test_past_performance_task_not_found() -> None:
    """存在しない task_id は 404"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(None),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{uuid.uuid4()}/past-performance")
    assert resp.status_code == 404


def test_past_performance_limited_to_3() -> None:
    """similar_tasks は最大 3 件（DB 側で LIMIT 3 をかける）"""
    task = _task_mock()
    mock_db = AsyncMock()
    similar = [_similar_row(f"タスク{i}", float(i + 1)) for i in range(3)]
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["月次"]),
        _exec_agg(2.0, 1.0, 3.0, 5),
        _exec_similar(similar),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["similar_tasks"]) == 3


def test_past_performance_multiple_tags() -> None:
    """複数タグを持つタスクでも正常動作する"""
    task = _task_mock()
    mock_db = AsyncMock()
    similar = [_similar_row("週次レビュー（先週）", 1.5)]
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["週次", "レビュー", "報告"]),
        _exec_agg(1.5, 1.5, 1.5, 1),
        _exec_similar(similar),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 1
    assert data["similar_tasks"][0]["actual_hours"] == 1.5
