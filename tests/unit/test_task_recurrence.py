import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models import Task


def _make_task(
    *,
    rule: str | None = "daily",
    end_date: date | None = None,
    due_date: date = date(2026, 6, 10),
    start_date: date | None = None,
    origin_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "週次レポート"
    t.description = None
    t.status = "completed"
    t.priority = "medium"
    t.assignee_id = "user-1"
    t.due_date = due_date
    t.start_date = start_date
    t.visibility = "team"
    t.project_id = project_id
    t.section_id = section_id
    t.parent_task_id = None
    t.created_by = "user-1"
    t.recurrence_rule = rule
    t.recurrence_end_date = end_date
    t.recurrence_origin_id = origin_id if origin_id is not None else t.id
    t.tags = []
    t.order_index = 1000.0
    t.completed_at = datetime(2026, 6, 10, 12, 0, 0)
    t.created_at = datetime(2026, 6, 1, 0, 0, 0)
    t.updated_at = datetime(2026, 6, 10, 12, 0, 0)
    t.confidence_score = None
    t.source_type = None
    t.sub_assignees = []
    t.work_hours = []
    t.subtasks = []
    t.project = None
    t.section = None
    return t


def _make_db(*, pending_task: MagicMock | None = None, max_order: float | None = 1000.0) -> AsyncMock:
    """_spawn_next_recurrence が実行するクエリ順にモックを設定する。
    Query 0: 既存の pending インスタンス確認 -> scalar_one_or_none = pending_task
    Query 1: max order_index 取得 -> scalar_one_or_none = max_order
    """
    mock_db = AsyncMock()
    call_count = 0

    def _scalar_result(val: object) -> MagicMock:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        return r

    async def _execute(query: object) -> MagicMock:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx == 0:
            return _scalar_result(pending_task)
        return _scalar_result(max_order)

    mock_db.execute = _execute
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    return mock_db


@pytest.mark.asyncio
async def test_spawn_next_daily() -> None:
    """daily タスク完了後、翌日 due_date の新タスクが生成される"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="daily", due_date=date(2026, 6, 10))
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 6, 11)
    assert new_task.status == "not_started"
    assert new_task.recurrence_rule == "daily"
    assert new_task.recurrence_origin_id == task.recurrence_origin_id


@pytest.mark.asyncio
async def test_spawn_next_weekly() -> None:
    """weekly タスク完了後、+7日の新タスクが生成される"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="weekly", due_date=date(2026, 6, 10))
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 6, 17)


@pytest.mark.asyncio
async def test_spawn_next_monthly() -> None:
    """monthly タスク完了後、+1ヶ月の新タスクが生成される"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="monthly", due_date=date(2026, 6, 10))
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 7, 10)


@pytest.mark.asyncio
async def test_no_spawn_after_end_date() -> None:
    """次の due_date が end_date を超える場合は生成しない"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(
        rule="weekly",
        due_date=date(2026, 6, 10),
        end_date=date(2026, 6, 15),  # 次は 6/17 → 超過
    )
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_no_spawn_if_pending_exists() -> None:
    """同じ origin_id の未完了タスクが存在する場合は生成しない"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="daily", due_date=date(2026, 6, 10))
    pending = _make_task(rule="daily", due_date=date(2026, 6, 11))
    db = _make_db(pending_task=pending)
    await _spawn_next_recurrence(task, db)

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_no_spawn_if_no_rule() -> None:
    """recurrence_rule が None のタスクは何もしない"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule=None)
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_preserves_start_date_offset() -> None:
    """start_date が設定されている場合、due_date との差分を保って次インスタンスに引き継ぐ"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(
        rule="weekly",
        due_date=date(2026, 6, 10),
        start_date=date(2026, 6, 8),  # 2日前から開始
    )
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 6, 17)
    assert new_task.start_date == date(2026, 6, 15)  # 2日前を維持
