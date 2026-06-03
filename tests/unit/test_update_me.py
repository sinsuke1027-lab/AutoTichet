from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.users import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="User One", email="u@u.com", roles=["member"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_profile() -> MagicMock:
    p = MagicMock()
    p.user_id = "user-1"
    p.display_name = "User One"
    p.email = "u@u.com"
    p.role = "member"
    p.department_tags = ["dev"]
    p.capacity_hours_per_day = 8.0
    return p


def test_get_my_profile_returns_200(client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = _make_profile()
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/users/me/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "user-1"
    assert data["display_name"] == "User One"
    assert data["department_tags"] == ["dev"]


def test_get_my_profile_no_db_record_returns_404(
    client: TestClient, mock_db: AsyncMock
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/users/me/profile")
    assert resp.status_code == 404


def test_patch_me_updates_display_name(client: TestClient, mock_db: AsyncMock) -> None:
    profile = _make_profile()
    profile.display_name = "Updated"
    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    resp = client.patch("/api/v1/users/me", json={"display_name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated"


def test_patch_me_not_found_returns_404(client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.patch("/api/v1/users/me", json={"display_name": "X"})
    assert resp.status_code == 404
