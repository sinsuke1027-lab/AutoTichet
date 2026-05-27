import uuid
from datetime import UTC, datetime

import pytest

from src.models.task_web import (
    DashboardSummary,
    ProjectCreate,
    ProjectResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
    WorkHourCreate,
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
    wh = WorkHourCreate(estimated_hours=2.5, actual_hours=3.0)
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


# --- Phase 2A 追加モデルのテスト ---


def test_section_create_valid() -> None:
    from src.models.task_web import SectionCreate
    s = SectionCreate(name="バックオフィス", order_index=1)
    assert s.name == "バックオフィス"
    assert s.order_index == 1


def test_section_response_from_attributes() -> None:
    import uuid
    from datetime import datetime

    from src.models.task_web import SectionResponse

    class FakeSection:
        pass
    obj = FakeSection()
    obj.id = uuid.uuid4()
    obj.project_id = uuid.uuid4()
    obj.name = "テスト"
    obj.order_index = 0
    obj.created_at = datetime.now(UTC)
    obj.updated_at = datetime.now(UTC)
    resp = SectionResponse.model_validate(obj)
    assert resp.name == "テスト"


def test_task_assignee_create() -> None:
    from src.models.task_web import TaskAssigneeCreate
    a = TaskAssigneeCreate(user_id="entra-oid-123", role="sub")
    assert a.role == "sub"


def test_import_preview_response() -> None:
    from src.models.task_web import ImportPreviewResponse
    preview = ImportPreviewResponse(
        file_name="test.xlsx",
        projects=[{"name": "総務", "will_create": True}],
        sections=[{"project": "総務", "name": "S1", "task_count": 3}],
        tasks={"total": 3, "completed": 1, "with_subtasks": 0, "with_dependencies": 0},
        warnings=[],
    )
    assert preview.tasks["total"] == 3


def test_import_result() -> None:
    from src.models.task_web import ImportResult
    r = ImportResult(created_tasks=5, created_sections=2, skipped_duplicates=1, errors=[])
    assert r.created_tasks == 5


def test_task_response_has_new_fields() -> None:
    import uuid
    from datetime import datetime

    from src.models.task_web import TaskResponse, TaskStatus
    resp = TaskResponse(
        id=uuid.uuid4(),
        title="test",
        status=TaskStatus.NOT_STARTED,
        priority="medium",
        visibility="team",
        created_by="uid",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        section_id=None,
        completed_at=None,
        order_index=0,
        sub_assignees=[],
    )
    assert resp.section_id is None
    assert resp.order_index == 0
    assert resp.sub_assignees == []


def test_task_create_has_section_id() -> None:
    from src.models.task_web import TaskCreate
    t = TaskCreate(title="Test", section_id=None)
    assert t.section_id is None


def test_task_update_has_section_id() -> None:
    import uuid

    from src.models.task_web import TaskUpdate
    sid = uuid.uuid4()
    t = TaskUpdate(section_id=sid)
    assert t.section_id == sid
