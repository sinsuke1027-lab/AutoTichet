from __future__ import annotations
import asyncio

MAX_ITEMS = 20
MAX_CHARS = 500


def get_clipboard_history() -> list[str]:
    """Windows クリップボード履歴からテキスト項目を返す（新しい順）。"""
    try:
        return asyncio.run(_fetch())
    except Exception:
        return []


async def _fetch() -> list[str]:
    from winrt.windows.applicationmodel.datatransfer import (
        Clipboard,
        ClipboardHistoryItemsResultStatus,
        StandardDataFormats,
    )

    result = await Clipboard.get_history_items_async()
    if result.status != ClipboardHistoryItemsResultStatus.SUCCESS:
        return []

    texts: list[str] = []
    for item in result.items:
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
