import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_manager = TokenPayload(sub="mgr-1", name="Manager", email="m@m.com", roles=["manager"], tid="t")
_member = TokenPayload(sub="mem-1", name="Member", email="mem@m.com", roles=["member"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


def _make_client(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_task(task_id: str, assignee_id: str = "mgr-1") -> MagicMock:
    t = MagicMock()
    t.id = uuid.UUID(task_id)
    t.assignee_id = assignee_id
    t.recurrence_rule = None
    t.status = "not_started"
    return t


def test_bulk_status_update(mock_db: AsyncMock) -> None:
    tid1 = str(uuid.uuid4())
    tid2 = str(uuid.uuid4())
    tasks = [_make_task(tid1), _make_task(tid2)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    client = _make_client(_manager, mock_db)
    resp = client.patch("/api/v1/tasks/bulk", json={"task_ids": [tid1, tid2], "status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 2


def test_bulk_assignee_update(mock_db: AsyncMock) -> None:
    tid1 = str(uuid.uuid4())
    tasks = [_make_task(tid1)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    client = _make_client(_manager, mock_db)
    resp = client.patch("/api/v1/tasks/bulk", json={"task_ids": [tid1], "assignee_id": "new-user"})
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1


def test_bulk_forbidden_task(mock_db: AsyncMock) -> None:
    tid1 = str(uuid.uuid4())
    tasks = [_make_task(tid1, assignee_id="other-user")]
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=result)
    client = _make_client(_member, mock_db)
    resp = client.patch("/api/v1/tasks/bulk", json={"task_ids": [tid1], "status": "completed"})
    assert resp.status_code == 403


def test_bulk_unauthenticated() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.patch(
        "/api/v1/tasks/bulk",
        json={"task_ids": [str(uuid.uuid4())], "status": "completed"},
    )
    assert resp.status_code in (401, 422)
