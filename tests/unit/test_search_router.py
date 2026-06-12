import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="User", email="u@u.com", roles=["member"], tid="t")


def _make_task(title: str = "テスト面接") -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.project_id = uuid.uuid4()
    t.title = title
    t.description = "説明文テキスト"
    t.visibility = "team"
    t.assignee_id = "other-user"
    return t


def _make_comment(task_id: uuid.UUID | None = None) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.task_id = task_id or uuid.uuid4()
    c.content = "コメントのテキスト"
    return c


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


def _make_client(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    from src.api.routers.search import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_search_task_title(mock_db: AsyncMock) -> None:
    task = _make_task()
    project_name = "採用プロジェクト"

    task_result = MagicMock()
    task_result.all.return_value = [(task, project_name)]
    comment_result = MagicMock()
    comment_result.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "テスト面接"
    assert data["items"][0]["match_type"] == "title"


def test_search_comment(mock_db: AsyncMock) -> None:
    task = _make_task("別のタスク")
    comment = _make_comment(task.id)
    comment.content = "コメント内に面接という文言"
    project_name = "採用プロジェクト"

    task_result = MagicMock()
    task_result.all.return_value = []
    comment_result = MagicMock()
    comment_result.all.return_value = [(comment, task, project_name)]
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["match_type"] == "comment"


def test_search_deduplication(mock_db: AsyncMock) -> None:
    task = _make_task("面接の準備")
    comment = _make_comment(task.id)
    comment.content = "面接のフィードバック"
    project_name = "採用プロジェクト"

    task_result = MagicMock()
    task_result.all.return_value = [(task, project_name)]
    comment_result = MagicMock()
    comment_result.all.return_value = [(comment, task, project_name)]
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["match_type"] == "title"


def test_search_comment_not_buried_by_many_task_matches(mock_db: AsyncMock) -> None:
    # タスク一致が limit 件あってもコメント一致が埋もれず表示される（issue #41）
    tasks = [(_make_task(f"面接タスク{i}"), "採用P") for i in range(20)]
    comment_task = _make_task("コメントのみ一致")
    comment = _make_comment(comment_task.id)
    comment.content = "面接の記録メモ"

    task_result = MagicMock()
    task_result.all.return_value = tasks
    comment_result = MagicMock()
    comment_result.all.return_value = [(comment, comment_task, "採用P")]
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接&limit=20")
    assert resp.status_code == 200
    data = resp.json()
    match_types = [it["match_type"] for it in data["items"]]
    assert "comment" in match_types
    assert len(data["items"]) <= 20


def test_search_short_query(mock_db: AsyncMock) -> None:
    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=a")
    assert resp.status_code == 422


def test_search_unauthenticated() -> None:
    from src.api.routers.search import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/search?q=テスト")
    assert resp.status_code == 401
