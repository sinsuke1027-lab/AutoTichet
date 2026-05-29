import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

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
