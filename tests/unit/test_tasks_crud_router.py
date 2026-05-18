import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_current_user] = lambda: _user


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
