from pathlib import Path

import pytest

import src.services.state as state_mod
from src.services.state import init_db, is_processed, mark_processed, unmark_processed


@pytest.fixture(autouse=True)
async def clean_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state_mod, "DB_PATH", tmp_path / "test.db")
    await init_db()


async def test_new_message_is_not_processed() -> None:
    assert not await is_processed("msg-001")


async def test_mark_and_check_processed() -> None:
    await mark_processed("msg-001", "email")
    assert await is_processed("msg-001")


async def test_unmark_processed() -> None:
    await mark_processed("msg-002", "email")
    await unmark_processed("msg-002")
    assert not await is_processed("msg-002")


async def test_double_mark_is_idempotent() -> None:
    await mark_processed("msg-003", "email")
    await mark_processed("msg-003", "email")  # 重複しても例外なし
    assert await is_processed("msg-003")
