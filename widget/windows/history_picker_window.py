from __future__ import annotations
from typing import Callable
import customtkinter as ctk

_DISPLAY_LEN = 80


class HistoryPickerWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTkToplevel,
        items: list[str],
        on_select: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self.title("クリップボード履歴")
        self.geometry("420x300")
        self.resizable(False, True)
        self.attributes("-topmost", True)
        self._on_select = on_select
        self._build(items)

    def _build(self, items: list[str]) -> None:
        if not items:
            ctk.CTkLabel(self, text="クリップボード履歴が見つかりませんでした").pack(pady=20)
            return

        scroll = ctk.CTkScrollableFrame(self, height=270)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        for text in items:
            display = text.replace("\n", " ")
            if len(display) > _DISPLAY_LEN:
                display = display[:_DISPLAY_LEN] + "…"
            ctk.CTkButton(
                scroll,
                text=display,
                anchor="w",
                fg_color="transparent",
                hover_color=("gray75", "gray30"),
                text_color=("gray10", "gray90"),
                command=lambda t=text: self._pick(t),
            ).pack(fill="x", pady=1)

    def _pick(self, text: str) -> None:
        self._on_select(text)
        self.destroy()
