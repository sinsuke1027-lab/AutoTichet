"""CSVエクスポートのバグ修正テスト (#16)

- my_tasks_only の余分な visibility 条件削除
- assignee を display_name に変更
- 二重 JOIN を subquery に安全化
"""
import csv
import io
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.db.models import Task, UserProfile


_admin = TokenPayload(
    sub="admin-1", name="Admin", email="a@t.com", roles=["admin"], tid="tid"
)


def _make_task(
    *,
    status: str = "not_started",
    assignee_id: str | None = "user-1",
    visibility: str = "all",
) -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "テストタスク"
    t.status = status
    t.priority = "medium"
    t.assignee_id = assignee_id
    t.start_date = date(2026, 6, 1)
    t.due_date = date(2026, 6, 30)
    t.completed_at = None
    t.project_id = None
    t.section_id = None
    t.description = "テスト説明"
    t.confidence_score = None
    t.source_type = None
    t.created_at = datetime(2026, 6, 1, 0, 0, 0)
    t.updated_at = datetime(2026, 6, 1, 0, 0, 0)
    t.tags = []
    t.sub_assignees = []
    t.work_hours = []
    t.subtasks = []
    t.project = None
    t.section = None
    t.visibility = visibility
    # assignee リレーション
    assignee_mock = MagicMock(spec=UserProfile)
    assignee_mock.display_name = "石川 花子"
    t.assignee = assignee_mock
    return t


def _make_db(tasks: list) -> AsyncMock:
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    return mock_db


def _make_client(db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_csv_export_returns_200() -> None:
    """CSV エクスポートが 200 を返す。"""
    client = _make_client(_make_db([_make_task()]))
    r = client.get("/api/v1/tasks/export/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


def test_csv_has_japanese_headers() -> None:
    """CSV の先頭行が日本語ヘッダーを含む。"""
    client = _make_client(_make_db([]))
    r = client.get("/api/v1/tasks/export/csv")
    content = r.content.decode("utf-8-sig")
    first_line = content.split("\r\n")[0]
    assert "タイトル" in first_line
    assert "担当者" in first_line
    assert "プロジェクト名" in first_line


def test_assignee_shows_display_name() -> None:
    """担当者列に display_name が表示されること（assignee_id ではなく）。"""
    task = _make_task()
    client = _make_client(_make_db([task]))
    r = client.get("/api/v1/tasks/export/csv")
    content = r.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["担当者"] == "石川 花子"


def test_assignee_falls_back_to_id_when_no_profile() -> None:
    """assignee が None の場合は assignee_id にフォールバックすること。"""
    task = _make_task()
    task.assignee = None  # type: ignore[assignment]
    task.assignee_id = "user-fallback"
    client = _make_client(_make_db([task]))
    r = client.get("/api/v1/tasks/export/csv")
    content = r.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert rows[0]["担当者"] == "user-fallback"


def test_my_tasks_only_does_not_filter_by_visibility() -> None:
    """my_tasks_only=true でも visibility によるフィルタが掛からないこと。

    admin ロールのため ロールベースフィルタは通過する。
    mock DB が返すタスクをそのまま CSV に含める。
    """
    task = _make_task(visibility="team")  # private ではない
    client = _make_client(_make_db([task]))
    r = client.get("/api/v1/tasks/export/csv?my_tasks_only=true")
    assert r.status_code == 200
    content = r.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    # DB モックが 1 件返すのでそれが CSV に含まれること
    assert len(rows) == 1
