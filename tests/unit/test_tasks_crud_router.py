import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_current_user] = lambda: _user


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app_f = FastAPI()
    app_f.include_router(router)
    app_f.dependency_overrides[get_current_user] = lambda: _user
    app_f.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app_f, raise_server_exceptions=False)


def test_tasks_crud_routes_exist() -> None:
    routes = [r.path for r in app.routes]
    assert "/api/v1/tasks" in routes
    assert "/api/v1/tasks/{task_id}" in routes
    assert "/api/v1/tasks/{task_id}/subtasks" in routes


def test_list_tasks_requires_auth() -> None:
    app2 = FastAPI()
    app2.include_router(router)
    client = TestClient(app2, raise_server_exceptions=False)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 401


def test_create_task_validates_required_fields() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/tasks", json={})
    assert resp.status_code == 422


def test_get_nonexistent_task_returns_404() -> None:
    from src.db.engine import get_db

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    app3 = FastAPI()
    app3.include_router(router)
    app3.dependency_overrides[get_current_user] = lambda: _user
    app3.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app3, raise_server_exceptions=False)
    resp = client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_delete_nonexistent_task_returns_404() -> None:
    from src.db.engine import get_db

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    app4 = FastAPI()
    app4.include_router(router)
    app4.dependency_overrides[get_current_user] = lambda: _user
    app4.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app4, raise_server_exceptions=False)
    resp = client.delete(f"/api/v1/tasks/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_nonexistent_task_returns_404() -> None:
    from src.db.engine import get_db

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    app5 = FastAPI()
    app5.include_router(router)
    app5.dependency_overrides[get_current_user] = lambda: _user
    app5.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app5, raise_server_exceptions=False)
    resp = client.put(f"/api/v1/tasks/{uuid.uuid4()}", json={"title": "new"})
    assert resp.status_code == 404


def test_list_tasks_with_keyword_filter(client, mock_db) -> None:
    """q パラメータがクエリパラメータとして受け付けられること"""
    # _visible_user_ids が ProjectMember クエリを1回実行するため scope_mock が先頭に必要
    scope_mock = MagicMock()
    scope_mock.scalars.return_value.all.return_value = []
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[scope_mock, count_mock, result_mock])
    resp = client.get("/api/v1/tasks?q=テスト")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_tasks_with_section_filter(client, mock_db) -> None:
    import uuid as _uuid
    sid = _uuid.uuid4()
    # _visible_user_ids が ProjectMember クエリを1回実行するため scope_mock が先頭に必要
    scope_mock = MagicMock()
    scope_mock.scalars.return_value.all.return_value = []
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[scope_mock, count_mock, result_mock])
    resp = client.get(f"/api/v1/tasks?section_id={sid}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_task_response_has_assignee_name(client: TestClient, mock_db: AsyncMock) -> None:
    """タスク一覧レスポンスに assignee_name と project_name が含まれる。"""
    from datetime import datetime, timezone
    from src.db.models import Task as TaskModel

    task_obj = MagicMock(spec=TaskModel)
    task_obj.id = uuid.uuid4()
    task_obj.project_id = None
    task_obj.parent_task_id = None
    task_obj.section_id = None
    task_obj.title = "テストタスク"
    task_obj.description = None
    task_obj.status = "not_started"
    task_obj.priority = "medium"
    task_obj.assignee_id = "user-1"
    task_obj.due_date = None
    task_obj.start_date = None
    task_obj.visibility = "team"
    task_obj.source_type = None
    task_obj.confidence_score = None
    task_obj.route = None
    task_obj.completed_at = None
    task_obj.order_index = 0.0
    task_obj.created_by = "user-1"
    task_obj.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    task_obj.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    task_obj.tags = []
    task_obj.sub_assignees = []
    task_obj.subtasks = []
    task_obj.work_hours = []
    task_obj.recurrence_rule = None
    task_obj.recurrence_end_date = None
    task_obj.recurrence_origin_id = None
    task_obj.visibility_tag = None
    task_obj.visibility_project_id = None
    task_obj.assignee = MagicMock()
    task_obj.assignee.display_name = "石川 太郎"
    task_obj.project = MagicMock()
    task_obj.project.name = "テストプロジェクト"

    # _visible_user_ids が ProjectMember クエリを1回実行するため scope_mock が先頭に必要
    scope_mock = MagicMock()
    scope_mock.scalars.return_value.all.return_value = []
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 1
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [task_obj]
    mock_db.execute = AsyncMock(side_effect=[scope_mock, count_mock, result_mock])

    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert "assignee_name" in items[0]
    assert "project_name" in items[0]
    assert items[0]["assignee_name"] == "石川 太郎"
    assert items[0]["project_name"] == "テストプロジェクト"
