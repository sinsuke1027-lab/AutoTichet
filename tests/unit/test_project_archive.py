import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.projects import router
from src.db.engine import get_db

_creator = TokenPayload(
    sub="creator-1", name="Creator", email="c@t.com", roles=["member"], tid="tid"
)
_other_member = TokenPayload(
    sub="other-1", name="Other", email="o@t.com", roles=["member"], tid="tid"
)
_leader = TokenPayload(
    sub="leader-1", name="Leader", email="l@t.com", roles=["leader"], tid="tid"
)


def _make_project(*, created_by: str = "creator-1", status: str = "active") -> MagicMock:
    from src.db.models import Project

    p = MagicMock(spec=Project)
    p.id = uuid.uuid4()
    p.name = "テストプロジェクト"
    p.description = None
    p.status = status
    p.created_by = created_by
    p.created_at = datetime(2026, 1, 1)
    p.updated_at = datetime(2026, 1, 1)
    return p


def _make_db(project: MagicMock | None) -> AsyncMock:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = project
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _make_list_db(projects: list) -> AsyncMock:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = projects
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _make_client(user: TokenPayload, db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_archive_by_creator_returns_200() -> None:
    """作成者がアーカイブ → status が archived に変わり 200"""
    project = _make_project(created_by="creator-1")
    client = _make_client(_creator, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/archive")
    assert resp.status_code == 200
    assert project.status == "archived"


def test_unarchive_by_creator_returns_200() -> None:
    """作成者がアーカイブ解除 → status が active に戻り 200"""
    project = _make_project(created_by="creator-1", status="archived")
    client = _make_client(_creator, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/unarchive")
    assert resp.status_code == 200
    assert project.status == "active"


def test_archive_by_non_creator_member_returns_403() -> None:
    """非作成者の member がアーカイブ → 403"""
    project = _make_project(created_by="creator-1")
    client = _make_client(_other_member, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/archive")
    assert resp.status_code == 403


def test_archive_by_leader_returns_200() -> None:
    """leader が他人のプロジェクトをアーカイブ → 200"""
    project = _make_project(created_by="creator-1")
    client = _make_client(_leader, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/archive")
    assert resp.status_code == 200


def test_archive_not_found_returns_404() -> None:
    """存在しないプロジェクトをアーカイブ → 404"""
    client = _make_client(_creator, _make_db(None))
    resp = client.patch(f"/api/v1/projects/{uuid.uuid4()}/archive")
    assert resp.status_code == 404


def test_list_projects_default_excludes_archived() -> None:
    """GET /projects（デフォルト）→ 200"""
    active_project = _make_project(status="active")
    client = _make_client(_creator, _make_list_db([active_project]))
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_projects_include_archived_true() -> None:
    """GET /projects?include_archived=true → 200（全件）"""
    active_project = _make_project(status="active")
    archived_project = _make_project(status="archived")
    client = _make_client(_creator, _make_list_db([active_project, archived_project]))
    resp = client.get("/api/v1/projects?include_archived=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_unarchive_by_non_creator_member_returns_403() -> None:
    """非作成者の member がアーカイブ解除 → 403"""
    project = _make_project(created_by="creator-1", status="archived")
    client = _make_client(_other_member, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/unarchive")
    assert resp.status_code == 403
