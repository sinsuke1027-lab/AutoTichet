"""機密度ゲートと無認証 extract 削除のテスト（C-2 / C-3）"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.db.models import Task
from src.models.config import Settings

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["leader"], tid="tid")

_SETTINGS_WITH_KEY = Settings(
    gemini_api_key="dummy-key",
    database_url="postgresql+asyncpg://x:x@localhost/x",
)


def _make_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


# ── C-2: 旧無認証 /tasks/extract の削除 ──────────────────────────


def test_old_unauthenticated_extract_route_removed() -> None:
    from src.api.main import app

    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/tasks/extract" not in paths  # 旧無認証ルートは削除
    assert "/api/v1/tasks/extract" in paths  # 認証付きの正規版は残る


# ── C-3: 機密度ゲート ────────────────────────────────────────────


def test_generate_subtasks_blocks_sensitive_content() -> None:
    mock_task = MagicMock(spec=Task)
    mock_task.id = uuid.uuid4()
    mock_task.title = "給与改定の検討"  # 機密キーワード「給与」
    mock_task.description = None

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/generate-subtasks")
        MockProvider.assert_not_called()  # 外部 LLM を呼ばない
    assert resp.status_code == 403


def test_clarify_skips_llm_for_sensitive_but_returns_rules() -> None:
    mock_task = MagicMock(spec=Task)
    mock_task.id = uuid.uuid4()
    mock_task.title = "契約金額の調整"  # 機密キーワード「契約金額」
    mock_task.description = "詳細"
    mock_task.due_date = None
    mock_task.sub_assignees = []

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")
        MockProvider.assert_not_called()  # LLM 部分はスキップ
    assert resp.status_code == 200  # ルールベースのチェックは返す
    fields = [i["field"] for i in resp.json()["issues"]]
    assert "due_date" in fields
    assert "assignees" in fields


def test_generate_handover_blocks_sensitive_content() -> None:
    task = MagicMock(spec=Task)
    task.title = "重要案件"
    task.status = "in_progress"
    task.priority = "high"
    task.due_date = None
    task.description = "契約金額の交渉メモ"  # 機密キーワード
    task.comments = []

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [task]
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with (
        patch("src.api.routers.tasks_crud.get_settings", return_value=_SETTINGS_WITH_KEY),
        patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider,
    ):
        resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
        MockProvider.assert_not_called()
    assert resp.status_code == 403
