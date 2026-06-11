from __future__ import annotations

import logging
import threading
from typing import Callable

import customtkinter as ctk

from widget.clients.backend_client import BackendClient, TaskItem

_PRIORITY_LABEL: dict[str | None, str] = {
    "urgent": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    None: "  ",
}


class TodoWindow(ctk.CTkToplevel):
    """今日のタスク一覧ウィンドウ。"""

    def __init__(self, parent: ctk.CTk, backend: BackendClient) -> None:
        super().__init__(parent)
        self.title("AutoTicket - 今日のタスク")
        self.geometry("500x460")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.minsize(380, 300)

        self._backend = backend
        self._tasks: list[TaskItem] = []
        self._row_widgets: list[dict] = []

        self._build_ui()
        self._load_tasks()

    # ──────────────────────────────
    # UI 構築
    # ──────────────────────────────
    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            header, text="今日のタスク", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        self._reload_btn = ctk.CTkButton(
            header, text="更新", width=72,
            command=self._load_tasks,
        )
        self._reload_btn.pack(side="right")

        self._status_lbl = ctk.CTkLabel(
            self, text="読み込み中…", text_color=("gray30", "gray70"), font=ctk.CTkFont(size=12)
        )
        self._status_lbl.pack(pady=(0, 4))

        self._scroll = ctk.CTkScrollableFrame(self, label_text="")
        self._scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._scroll.columnconfigure(0, weight=0)  # icon
        self._scroll.columnconfigure(1, weight=1)  # title
        self._scroll.columnconfigure(2, weight=0)  # button

    # ──────────────────────────────
    # データ取得
    # ──────────────────────────────
    def _load_tasks(self) -> None:
        self._reload_btn.configure(state="disabled", text="読込中…")
        self._status_lbl.configure(text="読み込み中…")
        for w in self._scroll.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        def _run() -> None:
            try:
                tasks = self._backend.get_today_tasks()
                self.after(0, lambda t=tasks: self._on_loaded(t))
            except Exception as exc:
                logging.error("TodoWindow._load_tasks error: %s", exc)
                self.after(0, lambda e=str(exc): self._on_load_error(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_loaded(self, tasks: list[TaskItem]) -> None:
        self._tasks = tasks
        self._reload_btn.configure(state="normal", text="更新")
        if not tasks:
            self._status_lbl.configure(text="今日のタスクはありません。")
            return
        incomplete = [t for t in tasks if t.status not in ("completed", "cancelled")]
        done_count = len(tasks) - len(incomplete)
        self._status_lbl.configure(
            text=f"{len(incomplete)} 件 未完了 / {done_count} 件 完了"
        )
        for i, task in enumerate(tasks):
            self._add_row(i, task)

    def _on_load_error(self, error: str) -> None:
        self._reload_btn.configure(state="normal", text="更新")
        self._status_lbl.configure(text=f"取得エラー: {error[:60]}", text_color="red")

    # ──────────────────────────────
    # 行の描画
    # ──────────────────────────────
    def _add_row(self, row_idx: int, task: TaskItem) -> None:
        is_done = task.status in ("completed", "cancelled")

        icon_lbl = ctk.CTkLabel(
            self._scroll,
            text=_PRIORITY_LABEL.get(task.priority, "  "),
            font=ctk.CTkFont(size=14),
            width=26,
        )
        icon_lbl.grid(row=row_idx, column=0, padx=(4, 2), pady=4, sticky="w")

        title_color: tuple[str, str] | str
        if is_done:
            title_color = ("gray60", "gray50")
        else:
            title_color = ("gray10", "gray90")

        title_lbl = ctk.CTkLabel(
            self._scroll,
            text=task.title,
            text_color=title_color,
            font=ctk.CTkFont(size=13, overstrike=is_done),
            anchor="w",
            wraplength=280,
        )
        title_lbl.grid(row=row_idx, column=1, padx=(2, 8), pady=4, sticky="ew")

        if is_done:
            btn = ctk.CTkLabel(
                self._scroll,
                text="✅",
                font=ctk.CTkFont(size=14),
                width=80,
            )
        else:
            btn = ctk.CTkButton(
                self._scroll,
                text="完了",
                width=72,
                height=28,
                command=lambda t=task, r=row_idx: self._on_complete(t, r),
            )
        btn.grid(row=row_idx, column=2, padx=(0, 6), pady=4)

        self._row_widgets.append({"icon": icon_lbl, "title": title_lbl, "btn": btn})

    # ──────────────────────────────
    # タスク完了
    # ──────────────────────────────
    def _on_complete(self, task: TaskItem, row_idx: int) -> None:
        widgets = self._row_widgets[row_idx]
        widgets["btn"].configure(state="disabled", text="処理中…")

        def _run() -> None:
            try:
                self._backend.complete_task(task.task_id)
                self.after(0, lambda: self._mark_done(task, row_idx))
            except Exception as exc:
                logging.error("complete_task error: %s", exc)
                err = str(exc)[:50]
                self.after(
                    0,
                    lambda: widgets["btn"].configure(state="normal", text="完了"),
                )
                self.after(
                    0,
                    lambda e=err: self._status_lbl.configure(
                        text=f"エラー: {e}", text_color="red"
                    ),
                )

        threading.Thread(target=_run, daemon=True).start()

    def _mark_done(self, task: TaskItem, row_idx: int) -> None:
        task.status = "completed"
        widgets = self._row_widgets[row_idx]

        widgets["title"].configure(
            text_color=("gray60", "gray50"),
            font=ctk.CTkFont(size=13, overstrike=True),
        )
        widgets["btn"].destroy()
        done_lbl = ctk.CTkLabel(
            self._scroll, text="✅", font=ctk.CTkFont(size=14), width=80
        )
        done_lbl.grid(row=row_idx, column=2, padx=(0, 6), pady=4)
        widgets["btn"] = done_lbl

        incomplete = sum(
            1 for t in self._tasks if t.status not in ("completed", "cancelled")
        )
        done_count = len(self._tasks) - incomplete
        self._status_lbl.configure(
            text=f"{incomplete} 件 未完了 / {done_count} 件 完了",
            text_color=("gray30", "gray70"),
        )
        logging.debug("Task %s marked as completed in UI", task.task_id)
