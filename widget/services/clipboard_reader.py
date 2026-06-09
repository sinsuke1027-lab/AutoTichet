from __future__ import annotations
from typing import Callable

MAX_CHARS = 1000


class ClipboardReader:
    def __init__(self, get_clipboard: Callable[[], str]) -> None:
        self._get = get_clipboard

    def read(self) -> str:
        try:
            text = self._get()
            if not text:
                return ""
            return text[:MAX_CHARS]
        except Exception:
            return ""

    def has_content(self) -> bool:
        return bool(self.read())
