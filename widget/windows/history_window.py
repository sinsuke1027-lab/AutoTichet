from __future__ import annotations

import logging
import threading
import webbrowser

import customtkinter as ctk

from widget.services.history_store import HistoryEntry, get_history


class HistoryWindow(ctk.CTkToplevel):
    """起票履歴一覧ウィンドウ（直近10件）。"""

    def __init__(self, parent: ctk.CTk, frontend_url: str) -> None:
        super().__init__(parent)
        self.title("AutoTicket - 起票履歴")
        self.geometry("500x400")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.minsize(380, 280)
        self._frontend_url = frontend_url.rstrip("/")
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            header, text="起票履歴（直近10件）", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(side="left")
        self._reload_btn = ctk.CTkButton(header, text="更新", width=72, command=self._load)
        self._reload_btn.pack(side="right")

        self._status_lbl = ctk.CTkLabel(
            self, text="読み込み中…", text_color=("gray30", "gray70"), font=ctk.CTkFont(size=12)
        )
        self._status_lbl.pack(pady=(0, 4))

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._scroll.columnconfigure(0, weight=1)
        self._scroll.columnconfigure(1, weight=0)

    def _load(self) -> None:
        self._reload_btn.configure(state="disabled", text="読込中…")
        for w in self._scroll.winfo_children():
            w.destroy()

        def _run() -> None:
            items = get_history()
            self.after(0, lambda it=items: self._on_loaded(it))

        threading.Thread(target=_run, daemon=True).start()

    def _on_loaded(self, items: list[HistoryEntry]) -> None:
        self._reload_btn.configure(state="normal", text="更新")
        if not items:
            self._status_lbl.configure(text="起票履歴がありません。")
            return
        self._status_lbl.configure(text=f"{len(items)} 件")
        for i, entry in enumerate(items):
            self._add_row(i, entry)

    def _add_row(self, row_idx: int, entry: HistoryEntry) -> None:
        proj = f"  [{entry.project_name}]" if entry.project_name else ""
        date_str = entry.created_at[:10] if len(entry.created_at) >= 10 else ""
        label_text = f"{date_str}  {entry.title}{proj}"
        lbl = ctk.CTkLabel(
            self._scroll,
            text=label_text,
            anchor="w",
            font=ctk.CTkFont(size=12),
            wraplength=320,
        )
        lbl.grid(row=row_idx, column=0, padx=(8, 4), pady=4, sticky="ew")

        if self._frontend_url:
            url = f"{self._frontend_url}/tasks/{entry.task_id}"
            btn = ctk.CTkButton(
                self._scroll,
                text="開く",
                width=60,
                height=26,
                command=lambda u=url: webbrowser.open(u),
            )
        else:
            btn = ctk.CTkLabel(self._scroll, text="", width=60)
        btn.grid(row=row_idx, column=1, padx=(0, 8), pady=4)
