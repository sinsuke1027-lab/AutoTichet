import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_leader = TokenPayload(sub="lead-1", name="Leader", email="l@l.com", roles=["leader"], tid="t")
_member = TokenPayload(sub="mem-1", name="Member", email="m@m.com", roles=["member"], tid="t")


def _make_project(created_by: str = "lead-1") -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.created_by = created_by
    return p


def _make_milestone(project_id: uuid.UUID | None = None) -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.project_id = project_id or uuid.uuid4()
    m.title = "ベータリリース"
    m.due_date = date(2026, 7, 1)
    m.completed = False
    m.completed_at = None
    m.created_at = datetime.now(UTC)
    return m


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


def _make_client(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    from src.api.routers.milestones import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_list_milestones(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = [_make_milestone(project.id)]

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    milestone_result = MagicMock()
    milestone_result.scalars.return_value.all.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, milestone_result])

    client = _make_client(_leader, mock_db)
    resp = client.get(f"/api/v1/projects/{project.id}/milestones")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_milestone(mock_db: AsyncMock) -> None:
    project = _make_project()
    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    mock_db.execute = AsyncMock(return_value=project_result)
    mock_db.commit = AsyncMock()

    async def _refresh(obj: object) -> None:
        # server_default で設定される created_at を Python 側で補完する
        if getattr(obj, "created_at", None) is None:
            setattr(obj, "created_at", datetime.now(UTC))

    mock_db.refresh = _refresh

    client = _make_client(_leader, mock_db)
    resp = client.post(
        f"/api/v1/projects/{project.id}/milestones",
        json={"title": "ベータリリース", "due_date": "2026-07-01"},
    )
    assert resp.status_code == 201


def test_update_milestone(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = _make_milestone(project.id)

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    ms_result = MagicMock()
    ms_result.scalar_one_or_none.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, ms_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    client = _make_client(_leader, mock_db)
    resp = client.put(
        f"/api/v1/projects/{project.id}/milestones/{ms.id}",
        json={"title": "GA リリース"},
    )
    assert resp.status_code == 200


def test_toggle_complete(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = _make_milestone(project.id)

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    ms_result = MagicMock()
    ms_result.scalar_one_or_none.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, ms_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    client = _make_client(_leader, mock_db)
    resp = client.patch(f"/api/v1/projects/{project.id}/milestones/{ms.id}/complete")
    assert resp.status_code == 200


def test_delete_milestone(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = _make_milestone(project.id)

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    ms_result = MagicMock()
    ms_result.scalar_one_or_none.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, ms_result])
    mock_db.commit = AsyncMock()

    client = _make_client(_leader, mock_db)
    resp = client.delete(f"/api/v1/projects/{project.id}/milestones/{ms.id}")
    assert resp.status_code == 204
