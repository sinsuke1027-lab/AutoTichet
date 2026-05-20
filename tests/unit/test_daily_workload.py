from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.dashboard import router
from src.db.engine import get_db


def _make_app(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _db_with_results(side_effects: list) -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=side_effects)
    return db


def _capacity_scalar(value: float) -> MagicMock:
    m = MagicMock()
    m.scalar_one.return_value = value
    return m


def _make_row(task_date: date, total_hours: float, task_count: int) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda i: [task_date, total_hours, task_count][i])
    return row


def _workload_rows_result(rows_data: list[tuple]) -> MagicMock:
    m = MagicMock()
    m.all.return_value = [_make_row(*r) for r in rows_data]
    return m


def _empty_workload() -> MagicMock:
    m = MagicMock()
    m.all.return_value = []
    return m


def test_daily_workload_member_returns_7_items() -> None:
    """member ユーザー: 2 回 execute（capacity + workload）→ 7 件返却"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7


def test_daily_workload_manager_returns_7_items() -> None:
    """manager ユーザー: 2 回 execute（capacity avg + workload）→ 7 件返却"""
    manager = TokenPayload(sub="mg1", roles=["manager"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(manager, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7


def test_daily_workload_leader_with_dept_tags() -> None:
    """leader（部署タグあり）: 3 回 execute（dept_ids + capacity avg + workload）"""
    leader = TokenPayload(sub="l1", roles=["leader"], department_tags=["営業部"])
    dept_result = MagicMock()
    dept_result.scalars.return_value.all.return_value = ["u-x"]
    db = _db_with_results([dept_result, _capacity_scalar(8.0), _empty_workload()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    assert len(resp.json()) == 7


def test_overload_flag_true_when_hours_exceed_capacity() -> None:
    """total_hours > capacity_hours → overload=True"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    today = date.today()
    workload = _workload_rows_result([(today, 10.0, 3)])
    db = _db_with_results([_capacity_scalar(8.0), workload])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    data = resp.json()
    today_item = next(d for d in data if d["date"] == today.isoformat())
    assert today_item["overload"] is True
    assert today_item["total_hours"] == 10.0
    assert today_item["task_count"] == 3


def test_days_without_tasks_have_zero_hours() -> None:
    """タスクがない日は total_hours=0, task_count=0, overload=False"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    data = resp.json()
    for item in data:
        assert item["total_hours"] == 0.0
        assert item["task_count"] == 0
        assert item["overload"] is False


def test_returned_dates_are_consecutive_from_today() -> None:
    """今日から連続 7 日の日付が返る"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    data = resp.json()
    expected = [(date.today() + timedelta(days=i)).isoformat() for i in range(7)]
    assert [d["date"] for d in data] == expected


def test_daily_workload_leader_without_dept_tags() -> None:
    """leader（部署タグなし）: member スコープにフォールバック（2 回 execute）"""
    leader = TokenPayload(sub="l2", roles=["leader"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    assert len(resp.json()) == 7
