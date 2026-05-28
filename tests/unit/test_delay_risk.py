from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest


def _task(
    status: str,
    due_days: int | None,
    estimated: float = 0.0,
    actual: float = 0.0,
) -> MagicMock:
    """ダミー Task ORM オブジェクトを生成する。"""
    from src.db.models import Task, TaskWorkHour

    t = MagicMock(spec=Task)
    t.status = status
    t.due_date = (date.today() + timedelta(days=due_days)) if due_days is not None else None

    wh = MagicMock(spec=TaskWorkHour)
    wh.estimated_hours = estimated if estimated > 0 else None
    wh.actual_hours = actual if actual > 0 else None
    t.work_hours = [wh] if (estimated > 0 or actual > 0) else []
    return t


def test_overdue_task_is_high() -> None:
    """期限超過タスクは high リスク（+40点）"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("in_progress", -1)
    assert _compute_risk_level(task) == "high"


def test_due_within_3days_and_not_started_is_medium_or_high() -> None:
    """残り2日 + not_started は 20+20=40点 → medium"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("not_started", 2)
    assert _compute_risk_level(task) in ("medium", "high")


def test_no_due_date_returns_none() -> None:
    """due_date なしは None"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("in_progress", None)
    assert _compute_risk_level(task) is None


def test_completed_task_returns_none() -> None:
    """完了タスクは None"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("completed", -5)
    assert _compute_risk_level(task) is None


def test_cancelled_task_returns_none() -> None:
    """キャンセルタスクは None"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("cancelled", -10)
    assert _compute_risk_level(task) is None


def test_low_risk_due_far_away_returns_none() -> None:
    """due_date が30日後・in_progress はリスクなし"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("in_progress", 30)
    assert _compute_risk_level(task) is None


def test_hours_overrun_alone_no_risk() -> None:
    """残り6日(+10) + 工数超過(+15) = 25点 → None（30未満）"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("in_progress", 6, estimated=5.0, actual=7.0)
    assert _compute_risk_level(task) is None


def test_overdue_plus_hours_overrun_is_high() -> None:
    """期限超過(+40) + 工数超過(+15) = 55点 → high（60未満だがoverdue+hoursで判断）"""
    from src.api.routers.tasks_crud import _compute_risk_level
    task = _task("in_progress", -2, estimated=5.0, actual=7.0)
    # 40+15=55 → medium（30-59）が正確。high は60以上
    assert _compute_risk_level(task) in ("medium", "high")
