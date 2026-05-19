import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import CurrentUser, TokenPayload
from src.db.engine import get_db
from src.api.auth import get_current_user


def _make_app() -> FastAPI:
    from src.api.routers import sections as sections_module
    app = FastAPI()
    app.include_router(sections_module.router)
    return app


def _mock_user() -> TokenPayload:
    return TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"])


@pytest.fixture
def app_and_client():
    app = _make_app()
    mock_user = _mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield app, c


def test_list_sections_returns_empty(app_and_client) -> None:
    app, client = app_and_client
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    async def fake_db():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        yield db

    app.dependency_overrides[get_db] = fake_db
    resp = client.get(f"/api/v1/projects/{uuid.uuid4()}/sections")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_section_201(app_and_client) -> None:
    app, client = app_and_client
    project_id = uuid.uuid4()
    section_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async def fake_db():
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        async def fake_refresh(obj, **kw):
            obj.id = section_id
            obj.project_id = project_id
            obj.name = "新セクション"
            obj.order_index = 0
            obj.created_at = now
            obj.updated_at = now

        db.refresh = fake_refresh
        yield db

    app.dependency_overrides[get_db] = fake_db
    resp = client.post(
        f"/api/v1/projects/{project_id}/sections",
        json={"name": "新セクション", "order_index": 0},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "新セクション"


def test_delete_section_404_when_not_found(app_and_client) -> None:
    app, client = app_and_client

    async def fake_db():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)
        yield db

    app.dependency_overrides[get_db] = fake_db
    resp = client.delete(f"/api/v1/projects/{uuid.uuid4()}/sections/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_section_404_when_not_found(app_and_client) -> None:
    app, client = app_and_client

    async def fake_db():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)
        yield db

    app.dependency_overrides[get_db] = fake_db
    resp = client.put(
        f"/api/v1/projects/{uuid.uuid4()}/sections/{uuid.uuid4()}",
        json={"name": "更新後"},
    )
    assert resp.status_code == 404
