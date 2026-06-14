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
from src.db.models import Task

_admin = TokenPayload(
    sub="admin-1", name="Admin", email="a@t.com", roles=["admin"], tid="tid"
)


def _make_task(*, status: str = "not_started") -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "テストタスク"
    t.status = status
    t.priority = "medium"
    t.assignee_id = "user-1"
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
    t.visibility = "all"
    t.assignee = None
    t.parent_task = None
    t.dependencies = []
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


def test_export_csv_returns_200_and_text_csv() -> None:
    """正常リクエスト → 200, Content-Type: text/csv"""
    task = _make_task()
    client = _make_client(_make_db([task]))
    resp = client.get("/api/v1/tasks/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_csv_content_disposition() -> None:
    """Content-Disposition に attachment と filename が含まれる"""
    client = _make_client(_make_db([]))
    resp = client.get("/api/v1/tasks/export/csv")
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "tasks_" in cd
    assert ".csv" in cd


def test_export_csv_utf8_bom() -> None:
    """レスポンスが UTF-8 BOM 付きであること"""
    task = _make_task()
    client = _make_client(_make_db([task]))
    resp = client.get("/api/v1/tasks/export/csv")
    assert resp.content[:3] == b"\xef\xbb\xbf"


def test_export_csv_status_filter_row_value() -> None:
    """status=completed クエリパラメータ → CSV の ステータス 列が completed"""
    task = _make_task(status="completed")
    client = _make_client(_make_db([task]))
    resp = client.get("/api/v1/tasks/export/csv?status=completed")
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig")))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["ステータス"] == "completed"


def test_export_csv_sub_assignees_show_display_names() -> None:
    """サブ担当者が UUID でなく表示名で出力される（issue #16 バグ1）"""
    task = _make_task()
    sub1 = MagicMock()
    sub1.user_id = "user-2"
    sub2 = MagicMock()
    sub2.user_id = "user-3"
    task.sub_assignees = [sub1, sub2]

    mock_db = AsyncMock()
    tasks_result = MagicMock()
    tasks_result.scalars.return_value.all.return_value = [task]
    profiles_result = MagicMock()
    profiles_result.all.return_value = [("user-2", "佐藤太郎"), ("user-3", "鈴木花子")]
    mock_db.execute = AsyncMock(side_effect=[tasks_result, profiles_result])

    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/export/csv")
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig")))
    rows = list(reader)
    assert rows[0]["サブ担当者"] == "佐藤太郎,鈴木花子"


def test_export_csv_has_22_headers() -> None:
    """CSV ヘッダーが 22 列あること（ID〜依存関係（ブロック元））"""
    client = _make_client(_make_db([]))
    resp = client.get("/api/v1/tasks/export/csv")
    reader = csv.reader(io.StringIO(resp.content.decode("utf-8-sig")))
    headers = next(reader)
    assert len(headers) == 22
    assert headers[0] == "ID"
    assert headers[1] == "タイトル"
    assert headers[19] == "更新日時"
    assert headers[20] == "親タスク名"
    assert headers[21] == "依存関係（ブロック元）"
