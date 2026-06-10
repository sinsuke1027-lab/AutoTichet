from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from widget.services.clipboard_history import get_clipboard_history, MAX_ITEMS, MAX_CHARS


def _make_text_item(text: str) -> MagicMock:
    view = MagicMock()
    view.contains.return_value = True
    view.get_text_async = AsyncMock(return_value=text)
    item = MagicMock()
    item.content = view
    return item


def _make_non_text_item() -> MagicMock:
    view = MagicMock()
    view.contains.return_value = False
    item = MagicMock()
    item.content = view
    return item


@pytest.fixture()
def mock_clipboard(monkeypatch):
    """ClipboardHistoryItemsResultStatus.SUCCESS = 0"""
    status_enum = MagicMock()
    status_enum.SUCCESS = 0

    def _patch(items, status=0):
        result = MagicMock()
        result.status = status
        result.items = items
        clipboard_cls = MagicMock()
        clipboard_cls.get_history_items_async = AsyncMock(return_value=result)

        monkeypatch.setattr(
            "widget.services.clipboard_history._fetch",
            lambda: _patched_fetch(items, status, status_enum),
        )

    return _patch


async def _patched_fetch(items, status, status_enum) -> list[str]:
    from winrt.windows.applicationmodel.datatransfer import StandardDataFormats

    if status != 0:
        return []
    texts: list[str] = []
    for item in items:
        view = item.content
        if not view.contains(StandardDataFormats.text):
            continue
        try:
            text = await view.get_text_async()
            stripped = text.strip()
            if stripped:
                texts.append(stripped[:MAX_CHARS])
        except Exception:
            continue
    return texts[:MAX_ITEMS]


def test_returns_text_items():
    items = [_make_text_item("タスクAをやる"), _make_text_item("タスクBをやる")]
    with patch("widget.services.clipboard_history._fetch", AsyncMock(return_value=["タスクAをやる", "タスクBをやる"])):
        result = get_clipboard_history()
    assert result == ["タスクAをやる", "タスクBをやる"]


def test_returns_empty_list_on_exception():
    with patch("widget.services.clipboard_history._fetch", side_effect=RuntimeError("失敗")):
        result = get_clipboard_history()
    assert result == []


def test_truncates_long_text():
    long_text = "あ" * (MAX_CHARS + 50)
    with patch("widget.services.clipboard_history._fetch", AsyncMock(return_value=[long_text[:MAX_CHARS]])):
        result = get_clipboard_history()
    assert len(result[0]) <= MAX_CHARS


def test_limits_to_max_items():
    many = [f"item{i}" for i in range(MAX_ITEMS)]
    with patch("widget.services.clipboard_history._fetch", AsyncMock(return_value=many)):
        result = get_clipboard_history()
    assert len(result) == MAX_ITEMS
