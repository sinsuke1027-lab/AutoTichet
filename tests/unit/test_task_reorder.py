import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.db.models import Task

_admin = TokenPayload(
    sub="admin-1", name="Admin", email="a@t.com", roles=["admin"], tid="tid"
)


def _make_task(*, order_index: float = 1000.0, section_id: uuid.UUID | None = None) -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "テストタスク"
    t.status = "not_started"
    t.priority = "medium"
    t.assignee_id = "user-1"
    t.start_date = date(2026, 6, 1)
    t.due_date = date(2026, 6, 30)
    t.completed_at = None
    t.project_id = None
    t.section_id = section_id
    t.description = None
    t.confidence_score = None
    t.source_type = None
    t.created_at = datetime(2026, 6, 1, 0, 0, 0)
    t.updated_at = datetime(2026, 6, 1, 0, 0, 0)
    t.tags = []
    t.sub_assignees = []
    t.work_hours = []
    t.subtasks = []
    t.project = None
    t.section = None
    t.visibility = "all"
    t.order_index = order_index
    return t


def _make_db_for_reorder(
    target: MagicMock,
    before: MagicMock | None = None,
    after: MagicMock | None = None,
    section_tasks: list | None = None,
    *,
    query_before: bool = True,
    query_after: bool = True,
) -> AsyncMock:
    """reorder エンドポイント用の DB モック。

    query_before=False のとき before クエリをスキップ（before_id=None の場合）。
    query_after=False のとき after クエリをスキップ（after_id=None の場合）。
    """
    mock_db = AsyncMock()
    call_count = 0

    # エンドポイントが実行する順序でスカラー結果を積む
    scalar_seq: list[MagicMock | None] = [target]
    if query_before:
        scalar_seq.append(before)
    if query_after:
        scalar_seq.append(after)

    def _scalar_result(val: MagicMock | None) -> MagicMock:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        return r

    def _scalars_result(tasks: list) -> MagicMock:
        r = MagicMock()
        r.scalars.return_value.all.return_value = tasks
        return r

    async def _execute(query: object) -> MagicMock:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(scalar_seq):
            return _scalar_result(scalar_seq[idx])
        return _scalars_result(section_tasks or [])

    mock_db.execute = _execute
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    return mock_db


def _make_client(db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_reorder_to_middle_returns_204() -> None:
    """前後タスクの中間値で order_index が更新される → 204"""
    before = _make_task(order_index=1000.0)
    target = _make_task(order_index=3000.0)
    after = _make_task(order_index=2000.0)
    db = _make_db_for_reorder(target, before, after)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": str(before.id), "after_id": str(after.id)},
    )
    assert resp.status_code == 204
    assert target.order_index == 1500.0


def test_reorder_to_top_returns_204() -> None:
    """before_id=null → after.order_index - 1000.0"""
    target = _make_task(order_index=3000.0)
    after = _make_task(order_index=1000.0)
    db = _make_db_for_reorder(target, None, after, query_before=False)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": None, "after_id": str(after.id)},
    )
    assert resp.status_code == 204
    assert target.order_index == 0.0


def test_reorder_to_bottom_returns_204() -> None:
    """after_id=null → before.order_index + 1000.0"""
    target = _make_task(order_index=1000.0)
    before = _make_task(order_index=3000.0)
    db = _make_db_for_reorder(target, before, None, query_after=False)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": str(before.id), "after_id": None},
    )
    assert resp.status_code == 204
    assert target.order_index == 4000.0


def test_reorder_triggers_renormalization() -> None:
    """差が 0.001 未満のとき再採番が実行される → 204"""
    before = _make_task(order_index=1000.0)
    target = _make_task(order_index=3000.0)
    after = _make_task(order_index=1000.0005)  # gap = 0.0005 < 0.001
    section_tasks = [before, after, target]
    db = _make_db_for_reorder(target, before, after, section_tasks=section_tasks)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": str(before.id), "after_id": str(after.id)},
    )
    assert resp.status_code == 204


def test_reorder_task_not_found_returns_404() -> None:
    """存在しない task_id → 404"""
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    client = _make_client(mock_db)
    resp = client.patch(
        f"/api/v1/tasks/{uuid.uuid4()}/order",
        json={"before_id": None, "after_id": None},
    )
    assert resp.status_code == 404
