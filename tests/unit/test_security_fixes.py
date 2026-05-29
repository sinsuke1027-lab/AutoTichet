import asyncio
import uuid  # noqa: F401
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.main import lifespan
from src.api.routers.tasks_crud import router
from src.db.engine import get_db  # noqa: F401

_member = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
_manager = TokenPayload(sub="mgr-1", name="Mgr", email="m@t.com", roles=["manager"], tid="tid")


def _make_app(user: TokenPayload | None = _member) -> FastAPI:
    """テスト用 FastAPI アプリ（user=None のとき認証なし）"""
    app = FastAPI()
    app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


# --- VULN-04: extract エンドポイント認証 ---

def test_extract_requires_auth() -> None:
    """認証なしで POST /api/v1/tasks/extract → 401"""
    app = _make_app(user=None)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/tasks/extract", json={"text": "テスト", "source_type": "email"})
    assert resp.status_code == 401


# --- VULN-02: DEV_MODE 起動警告 ---


def test_dev_mode_logs_critical_warning() -> None:
    """DEV_MODE=true のとき lifespan が CRITICAL ログを出力する"""
    from unittest.mock import patch

    with patch("src.api.main.get_settings") as mock_get_settings, \
         patch("src.api.main.init_db", new_callable=AsyncMock), \
         patch("src.api.main.scheduler"):
        mock_get_settings.return_value = MagicMock(dev_mode=True, polling_interval_seconds=60)

        from src.api.main import app as main_app

        with patch("src.api.main.logger") as mock_logger:
            async def run() -> None:
                async with lifespan(main_app):
                    pass

            asyncio.run(run())

        mock_logger.critical.assert_called_once()
        args = mock_logger.critical.call_args[0]
        assert any("DEV_MODE" in str(a) for a in args)


# --- VULN-06: タスク IDOR 修正 ---


def _make_mock_task(assignee_id: str = "owner-1") -> MagicMock:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.assignee_id = assignee_id
    task.tags = []
    task.sub_assignees = []
    task.subtasks = []
    task.status = "not_started"
    task.due_date = None
    task.start_date = None
    task.work_hours = []
    task.project_id = None
    task.parent_task_id = None
    task.section_id = None
    task.title = "テストタスク"
    task.description = None
    task.priority = "medium"
    task.visibility = "all"
    task.source_type = "manual"
    task.confidence_score = None
    task.route = "auto_create"
    task.completed_at = None
    task.order_index = 0
    task.created_by = "owner-1"
    task.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    task.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return task


def _make_db_with_task(task: MagicMock) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = task
    mock_result.scalar_one.return_value = task
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    return mock_db


def test_update_task_by_non_owner_member_returns_403() -> None:
    """member が他人のタスクを更新しようとすると 403"""
    task = _make_mock_task(assignee_id="owner-1")
    mock_db = _make_db_with_task(task)

    app = _make_app(user=_member)  # sub="user-1"（owner でない）
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.put(f"/api/v1/tasks/{task.id}", json={"title": "ハック"})
    assert resp.status_code == 403


def test_delete_task_by_non_owner_member_returns_403() -> None:
    """member が他人のタスクを削除しようとすると 403"""
    task = _make_mock_task(assignee_id="owner-1")
    mock_db = _make_db_with_task(task)

    app = _make_app(user=_member)
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.delete(f"/api/v1/tasks/{task.id}")
    assert resp.status_code == 403


def test_duplicate_task_by_non_owner_member_returns_403() -> None:
    """member が他人のタスクを複製しようとすると 403"""
    task = _make_mock_task(assignee_id="owner-1")
    mock_db = _make_db_with_task(task)

    app = _make_app(user=_member)
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post(f"/api/v1/tasks/{task.id}/duplicate")
    assert resp.status_code == 403


def test_update_task_by_manager_succeeds() -> None:
    """manager ロールなら他人のタスクでも更新できる"""
    task = _make_mock_task(assignee_id="owner-1")

    # update_task は commit 後に再クエリするため execute を 2 回呼ぶ
    mock_result_1 = MagicMock()
    mock_result_1.scalar_one_or_none.return_value = task
    mock_result_2 = MagicMock()
    mock_result_2.scalar_one.return_value = task
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.add = MagicMock()

    app = _make_app(user=_manager)  # roles=["manager"]
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.put(f"/api/v1/tasks/{task.id}", json={"title": "管理者が更新"})
    assert resp.status_code == 200
