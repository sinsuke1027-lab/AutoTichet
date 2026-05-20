from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.admin import router
from src.db.engine import get_db

_admin = TokenPayload(sub="admin-1", name="Admin", email="a@a.com", roles=["admin"], tid="t")
_member = TokenPayload(sub="mem-1", name="Mem", email="m@m.com", roles=["member"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def admin_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def member_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _member
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_list_users_non_admin_returns_403(member_client: TestClient, mock_db: AsyncMock) -> None:
    resp = member_client.get("/api/v1/admin/users")
    assert resp.status_code == 403


def test_list_users_admin_returns_200(admin_client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    resp = admin_client.get("/api/v1/admin/users")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_user_validates_required_fields(
    admin_client: TestClient, mock_db: AsyncMock
) -> None:
    resp = admin_client.post("/api/v1/admin/users", json={})
    assert resp.status_code == 422


def test_delete_nonexistent_user_returns_404(
    admin_client: TestClient, mock_db: AsyncMock
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    resp = admin_client.delete("/api/v1/admin/users/nonexistent")
    assert resp.status_code == 404


def test_update_nonexistent_user_returns_404(
    admin_client: TestClient, mock_db: AsyncMock
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    resp = admin_client.patch("/api/v1/admin/users/nonexistent", json={"role": "leader"})
    assert resp.status_code == 404
