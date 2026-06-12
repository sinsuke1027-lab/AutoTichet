from __future__ import annotations

from pathlib import Path

import pytest

from widget.services.draft_queue import DraftEntry, DraftQueue


@pytest.fixture
def queue(tmp_path: Path) -> DraftQueue:
    return DraftQueue(db_path=tmp_path / "drafts.db")


def test_add_and_get_pending(queue: DraftQueue) -> None:
    payload = {"title": "テストタスク", "priority": "medium"}
    draft_id = queue.add(payload)
    pending = queue.get_pending()
    assert len(pending) == 1
    assert pending[0].id == draft_id
    assert pending[0].payload == payload
    assert pending[0].retry_count == 0


def test_remove_deletes_draft(queue: DraftQueue) -> None:
    draft_id = queue.add({"title": "削除テスト"})
    queue.remove(draft_id)
    assert queue.get_pending() == []


def test_increment_retry_updates_count_and_error(queue: DraftQueue) -> None:
    draft_id = queue.add({"title": "リトライテスト"})
    queue.increment_retry(draft_id, "Connection timeout")
    pending = queue.get_pending()
    assert pending[0].retry_count == 1
    assert pending[0].last_error == "Connection timeout"


def test_get_pending_empty_returns_empty_list(queue: DraftQueue) -> None:
    assert queue.get_pending() == []


def test_get_pending_excludes_max_retries(queue: DraftQueue) -> None:
    # リトライ上限（3回）に達したドラフトは再送対象から除外する（issue #35）
    from widget.services.draft_queue import MAX_DRAFT_RETRIES

    draft_id = queue.add({"title": "恒久失敗"})
    for _ in range(MAX_DRAFT_RETRIES):
        queue.increment_retry(draft_id, "error")
    assert queue.get_pending() == []


def test_get_pending_includes_below_max_retries(queue: DraftQueue) -> None:
    draft_id = queue.add({"title": "まだ再送対象"})
    queue.increment_retry(draft_id, "error")
    pending = queue.get_pending()
    assert len(pending) == 1
    assert pending[0].id == draft_id


def test_created_at_is_iso_format(queue: DraftQueue) -> None:
    queue.add({"title": "ISO確認"})
    entry = queue.get_pending()[0]
    # ISO 8601 形式であれば T が含まれる
    assert "T" in entry.created_at
