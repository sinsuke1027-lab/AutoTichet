from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.admin import router
from src.db.engine import get_db
from src.db.models import DepartmentTag

_admin = TokenPayload(sub="admin-1", name="Admin", email="a@a.com", roles=["admin"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_list_tags_returns_tag_objects(client: TestClient, mock_db: AsyncMock) -> None:
    """GET /admin/tags が DepartmentTagResponse のリストを返す"""
    tag = DepartmentTag(name="営業部", description="営業・提案担当")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [tag]
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/admin/tags")

    assert resp.status_code == 200
    assert resp.json() == [{"name": "営業部", "description": "営業・提案担当"}]


def test_create_tag_returns_201(client: TestClient, mock_db: AsyncMock) -> None:
    """POST /admin/tags が 201 を返し、作成したタグを返す"""
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=not_found)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    resp = client.post("/api/v1/admin/tags", json={"name": "人事部", "description": "採用担当"})

    assert resp.status_code == 201
    assert resp.json()["name"] == "人事部"


def test_create_tag_conflict_returns_409(client: TestClient, mock_db: AsyncMock) -> None:
    """既存名で POST すると 409"""
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = DepartmentTag(name="営業部", description=None)
    mock_db.execute = AsyncMock(return_value=existing_result)

    resp = client.post("/api/v1/admin/tags", json={"name": "営業部"})

    assert resp.status_code == 409


def test_update_tag_not_found_returns_404(client: TestClient, mock_db: AsyncMock) -> None:
    """存在しないタグを PATCH すると 404"""
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=not_found)

    resp = client.patch("/api/v1/admin/tags/nonexistent", json={"description": "新説明"})

    assert resp.status_code == 404


def test_delete_tag_returns_204(client: TestClient, mock_db: AsyncMock) -> None:
    """DELETE /admin/tags/{tag} が 204 を返す"""
    tag = DepartmentTag(name="営業部", description=None)
    tag_result = MagicMock()
    tag_result.scalar_one_or_none.return_value = tag
    user_result = MagicMock()
    user_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[tag_result, user_result])
    mock_db.commit = AsyncMock()

    resp = client.delete("/api/v1/admin/tags/%E5%96%B6%E6%A5%AD%E9%83%A8")  # URL encode "営業部"

    assert resp.status_code == 204
