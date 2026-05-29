import uuid  # noqa: F401
from unittest.mock import AsyncMock, MagicMock  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
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

import asyncio as _asyncio
import logging as _logging


def test_dev_mode_logs_critical_warning() -> None:
    """DEV_MODE=true のとき lifespan が CRITICAL ログを出力する"""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("src.api.main.get_settings") as mock_get_settings, \
         patch("src.api.main.init_db", new_callable=AsyncMock), \
         patch("src.api.main.scheduler"):
        mock_get_settings.return_value = MagicMock(dev_mode=True, polling_interval_seconds=60)

        from src.api.main import app as main_app, lifespan

        with patch("src.api.main.logger") as mock_logger:
            async def run() -> None:
                async with lifespan(main_app):
                    pass

            _asyncio.run(run())

        mock_logger.critical.assert_called_once()
        args = mock_logger.critical.call_args[0]
        assert any("DEV_MODE" in str(a) for a in args)
