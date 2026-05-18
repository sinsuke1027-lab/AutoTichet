import uuid
from datetime import date, datetime

import pytest

from src.models.task_web import (
    CommentCreate,
    CommentResponse,
    DashboardSummary,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
    WorkHourCreate,
    WorkHourResponse,
    WorkloadItem,
)


def test_task_status_enum_values() -> None:
    assert TaskStatus.NOT_STARTED == "not_started"
    assert TaskStatus.IN_PROGRESS == "in_progress"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.CANCELLED == "cancelled"


def test_task_create_defaults() -> None:
    t = TaskCreate(title="テストタスク", created_by="user-123")
    assert t.status == TaskStatus.NOT_STARTED
    assert t.priority == "medium"
    assert t.visibility == "team"
    assert t.tags == []


def test_task_create_requires_title_and_created_by() -> None:
    with pytest.raises(Exception):
        TaskCreate(created_by="user-123")  # type: ignore[call-arg]


def test_task_response_serialization() -> None:
    task_id = uuid.uuid4()
    now = datetime.now()
    resp = TaskResponse(
        id=task_id,
        title="テスト",
        status=TaskStatus.NOT_STARTED,
        priority="medium",
        visibility="team",
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )
    data = resp.model_dump()
    assert data["id"] == task_id
    assert data["status"] == "not_started"
    assert data["tags"] == []


def test_task_update_partial() -> None:
    upd = TaskUpdate(title="新タイトル")
    assert upd.title == "新タイトル"
    assert upd.status is None
    assert upd.priority is None


def test_project_create_defaults() -> None:
    p = ProjectCreate(name="プロジェクトA", created_by="user-1")
    assert p.status == "active"
    assert p.description is None


def test_project_response_from_attributes() -> None:
    task_id = uuid.uuid4()
    now = datetime.now()
    resp = ProjectResponse(
        id=task_id,
        name="テストPJ",
        status="active",
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )
    assert resp.name == "テストPJ"


def test_work_hour_create() -> None:
    wh = WorkHourCreate(user_id="user-1", estimated_hours=2.5, actual_hours=3.0)
    assert wh.estimated_hours == 2.5
    assert wh.actual_hours == 3.0
    assert wh.notes is None


def test_dashboard_summary() -> None:
    summary = DashboardSummary(
        total_tasks=10,
        not_started=3,
        in_progress=4,
        completed=3,
        overdue=1,
        completion_rate=30.0,
    )
    assert summary.total_tasks == 10
    assert summary.completion_rate == 30.0


def test_workload_item() -> None:
    item = WorkloadItem(
        user_id="user-1",
        display_name="山田太郎",
        estimated_hours=45.0,
        capacity_hours=40.0,
        overload=True,
    )
    assert item.overload is True


def test_task_list_response() -> None:
    lst = TaskListResponse(items=[], total=0)
    assert lst.total == 0
    assert lst.items == []
