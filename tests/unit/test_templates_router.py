import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
_admin = TokenPayload(sub="admin-1", name="Admin", email="a@t.com", roles=["admin"], tid="tid")


def _make_client(mock_db: AsyncMock, user: TokenPayload = _user) -> TestClient:
    from src.api.routers.templates import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _mock_template(created_by: str = "user-1") -> MagicMock:
    from src.db.models import TaskTemplate
    t = MagicMock(spec=TaskTemplate)
    t.id = uuid.uuid4()
    t.name = "月次報告テンプレート"
    t.description = "月次報告"
    t.template_data = {
        "title": "月次報告",
        "description": None,
        "priority": "medium",
        "visibility": "team",
        "tags": [],
        "estimated_hours": None,
        "due_date_offset_days": 3,
        "subtasks": [
            {"title": "データ収集", "description": None, "priority": "medium", "due_date_offset_days": 1}
        ],
    }
    t.created_by = created_by
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t


def test_templates_routes_exist() -> None:
    from src.api.routers.templates import router
    app = FastAPI()
    app.include_router(router)
    routes = [r.path for r in app.routes]
    assert "/api/v1/templates" in routes
    assert "/api/v1/templates/{template_id}" in routes
    assert "/api/v1/templates/{template_id}/apply" in routes


def test_list_templates_requires_auth() -> None:
    from src.api.routers.templates import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/templates")
    assert resp.status_code == 401


def test_list_templates_returns_list() -> None:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [_mock_template()]
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.get("/api/v1/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "月次報告テンプレート"


def test_create_template() -> None:
    mock_db = AsyncMock()

    async def _refresh(obj, *args: object, **kwargs: object) -> None:
        obj.id = uuid.uuid4()
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    client = _make_client(mock_db)
    resp = client.post(
        "/api/v1/templates",
        json={
            "name": "月次報告テンプレート",
            "template_data": {
                "title": "月次報告",
                "due_date_offset_days": 3,
                "subtasks": [],
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "月次報告テンプレート"
    assert "id" in data


def test_get_template_not_found() -> None:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/templates/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_template_by_creator() -> None:
    tmpl = _mock_template(created_by="user-1")
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = tmpl
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def _refresh(obj, *args: object, **kwargs: object) -> None:
        pass

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    client = _make_client(mock_db)
    resp = client.put(
        f"/api/v1/templates/{tmpl.id}",
        json={"name": "更新後の名前"},
    )
    assert resp.status_code == 200


def test_update_template_by_other_user_forbidden() -> None:
    tmpl = _mock_template(created_by="other-user")
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = tmpl
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.put(
        f"/api/v1/templates/{tmpl.id}",
        json={"name": "改ざん"},
    )
    assert resp.status_code == 403


def test_update_template_by_admin() -> None:
    tmpl = _mock_template(created_by="other-user")
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = tmpl
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def _refresh(obj, *args: object, **kwargs: object) -> None:
        pass

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    client = _make_client(mock_db, user=_admin)
    resp = client.put(
        f"/api/v1/templates/{tmpl.id}",
        json={"name": "admin 更新"},
    )
    assert resp.status_code == 200


def test_delete_template_by_creator() -> None:
    tmpl = _mock_template(created_by="user-1")
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = tmpl
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.delete(f"/api/v1/templates/{tmpl.id}")
    assert resp.status_code == 204


def test_delete_template_by_other_user_forbidden() -> None:
    tmpl = _mock_template(created_by="other-user")
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = tmpl
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.delete(f"/api/v1/templates/{tmpl.id}")
    assert resp.status_code == 403
