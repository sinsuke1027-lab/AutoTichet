import pytest
import pathlib
import tempfile


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """テスト用に history.db をテンポラリディレクトリに向ける。"""
    import widget.services.history_store as hs
    monkeypatch.setattr(hs, "_DB_PATH", tmp_path / "history.db")
    return tmp_path / "history.db"


def test_add_and_get_history(tmp_db) -> None:
    from widget.services.history_store import add_history, get_history
    add_history("task-1", "タスクA", "プロジェクト1")
    add_history("task-2", "タスクB", None)
    items = get_history()
    assert len(items) == 2
    assert items[0].task_id == "task-2"   # 新しい順
    assert items[0].title == "タスクB"
    assert items[0].project_name is None
    assert items[1].task_id == "task-1"
    assert items[1].project_name == "プロジェクト1"


def test_history_capped_at_10(tmp_db) -> None:
    from widget.services.history_store import add_history, get_history
    for i in range(15):
        add_history(f"task-{i}", f"タスク{i}")
    items = get_history()
    assert len(items) == 10


def test_get_history_returns_empty_list_when_no_entries(tmp_db) -> None:
    from widget.services.history_store import get_history
    assert get_history() == []


def test_history_entry_has_created_at(tmp_db) -> None:
    from widget.services.history_store import add_history, get_history
    add_history("task-x", "テスト")
    entry = get_history()[0]
    assert entry.created_at  # 空でない
    assert "T" in entry.created_at  # ISO 形式
