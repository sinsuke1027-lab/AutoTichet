from __future__ import annotations

import logging
import queue
import threading
from datetime import date

import customtkinter as ctk

from widget.clients.backend_client import BackendClient, TaskItem

_PRIORITY_LABEL: dict[str | None, str] = {
    "urgent": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    None: "  ",
}

_STATUS_LABEL: dict[str, str] = {
    "not_started": "未着手",
    "in_progress": "進行中",
}


class TodoWindow(ctk.CTkToplevel):
    """今日のタスク一覧ウィンドウ（開始日超過アラート付き）。"""

    def __init__(self, parent: ctk.CTk, backend: BackendClient) -> None:
        super().__init__(parent)
        self.title("AutoTicket - 今日のタスク")
        self.geometry("520x500")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.minsize(380, 300)

        self._backend = backend
        self._today_tasks: list[TaskItem] = []
        self._overdue_tasks: list[TaskItem] = []
        self._row_widgets: dict[str, dict] = {}  # task_id → {icon, title, btn, row}
        self._q: queue.Queue[tuple] = queue.Queue()
        self._pending_loads: int = 0

        self._build_ui()
        self._load_all()
        self.after(100, self._drain_queue)

    # ──────────────────────────────
    # キュー処理（スレッドセーフ）
    # ──────────────────────────────
    def _drain_queue(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "today_loaded":
                    self._today_tasks = msg[1]
                    self._pending_loads -= 1
                    self._render_sections()
                elif kind == "overdue_loaded":
                    self._overdue_tasks = msg[1]
                    self._pending_loads -= 1
                    self._render_sections()
                elif kind == "load_error":
                    self._pending_loads -= 1
                    self._on_load_error(msg[1])
        except queue.Empty:
            pass
        try:
            self.after(100, self._drain_queue)
        except Exception:
            pass

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
            command=self._load_all,
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
    def _load_all(self) -> None:
        self._reload_btn.configure(state="disabled", text="読込中…")
        self._status_lbl.configure(text="読み込み中…")
        self._today_tasks = []
        self._overdue_tasks = []
        self._pending_loads = 2
        for w in self._scroll.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        def _run_today() -> None:
            try:
                tasks = self._backend.get_today_tasks()
                self._q.put(("today_loaded", tasks))
            except Exception as exc:
                logging.error("TodoWindow._load_today error: %s", exc)
                self._q.put(("load_error", str(exc)))

        def _run_overdue() -> None:
            try:
                tasks = self._backend.get_start_overdue_tasks()
                self._q.put(("overdue_loaded", tasks))
            except Exception as exc:
                logging.error("TodoWindow._load_overdue error: %s", exc)
                self._q.put(("overdue_loaded", []))  # エラー時は空リストで続行

        threading.Thread(target=_run_today, daemon=True).start()
        threading.Thread(target=_run_overdue, daemon=True).start()

    # ──────────────────────────────
    # セクション描画
    # ──────────────────────────────
    def _render_sections(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        today_str = date.today().isoformat()
        row = 0

        # ── 開始日超過セクション ──
        active_overdue = [
            t for t in self._overdue_tasks
            if t.status in ("not_started", "in_progress")
            and t.start_date and t.start_date < today_str
        ]
        if active_overdue:
            ctk.CTkLabel(
                self._scroll,
                text="⚠️  開始日超過（未着手・進行中）",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("#d97706", "#f59e0b"),
            ).grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(8, 2))
            row += 1
            for task in active_overdue:
                row = self._add_row(row, task, show_start_date=True)

        # ── 今日の期限セクション ──
        overdue_ids = {t.task_id for t in active_overdue}
        today_tasks = [t for t in self._today_tasks if t.task_id not in overdue_ids]

        ctk.CTkLabel(
            self._scroll,
            text="📅  今日の期限",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray30", "gray70"),
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(8, 2))
        row += 1

        for task in today_tasks:
            row = self._add_row(row, task, show_start_date=False)

        if not today_tasks:
            ctk.CTkLabel(
                self._scroll,
                text="今日の期限タスクはありません",
                text_color=("gray50", "gray60"),
                font=ctk.CTkFont(size=12),
            ).grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=4)
            row += 1

        # ステータスバー更新（両方ロード完了したら確定表示）
        if self._pending_loads == 0:
            self._reload_btn.configure(state="normal", text="更新")

        incomplete_today = sum(1 for t in self._today_tasks if t.status not in ("completed", "cancelled"))
        done_today = len(self._today_tasks) - incomplete_today
        overdue_count = len(active_overdue)

        parts = []
        if overdue_count:
            parts.append(f"⚠️ 超過 {overdue_count} 件")
        parts.append(f"今日 {incomplete_today} 件未完了 / {done_today} 件完了")
        self._status_lbl.configure(
            text=" ／ ".join(parts),
            text_color=("#d97706", "#f59e0b") if overdue_count else ("gray30", "gray70"),
        )

    def _on_load_error(self, error: str) -> None:
        self._reload_btn.configure(state="normal", text="更新")
        self._status_lbl.configure(text=f"取得エラー: {error[:60]}", text_color="red")

    # ──────────────────────────────
    # 行の描画
    # ──────────────────────────────
    def _add_row(self, row_idx: int, task: TaskItem, show_start_date: bool = False) -> int:
        is_done = task.status in ("completed", "cancelled")

        icon_lbl = ctk.CTkLabel(
            self._scroll,
            text=_PRIORITY_LABEL.get(task.priority, "  "),
            font=ctk.CTkFont(size=14),
            width=26,
        )
        icon_lbl.grid(row=row_idx, column=0, padx=(4, 2), pady=4, sticky="w")

        if is_done:
            title_color: tuple[str, str] | str = ("gray60", "gray50")
        else:
            title_color = ("gray10", "gray90")

        title_text = task.title
        if show_start_date and task.start_date:
            status_jp = _STATUS_LABEL.get(task.status, task.status)
            title_text = f"{task.title}\n開始予定: {task.start_date}  [{status_jp}]"

        title_lbl = ctk.CTkLabel(
            self._scroll,
            text=title_text,
            text_color=title_color,
            font=ctk.CTkFont(size=13, overstrike=is_done),
            anchor="w",
            wraplength=280,
            justify="left",
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

        self._row_widgets[task.task_id] = {"icon": icon_lbl, "title": title_lbl, "btn": btn, "row": row_idx}
        return row_idx + 1

    # ──────────────────────────────
    # タスク完了
    # ──────────────────────────────
    def _on_complete(self, task: TaskItem, row_idx: int) -> None:
        widgets = self._row_widgets.get(task.task_id)
        if not widgets:
            return
        widgets["btn"].configure(state="disabled", text="…")
        self._show_actual_hours_dialog(task, widgets)

    def _show_actual_hours_dialog(self, task: TaskItem, widgets: dict) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("実績工数")
        dialog.geometry("320x170")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        title_short = task.title[:28] + "…" if len(task.title) > 28 else task.title
        ctk.CTkLabel(
            dialog, text=f"「{title_short}」", font=ctk.CTkFont(size=12), wraplength=290
        ).pack(pady=(14, 2))
        ctk.CTkLabel(
            dialog, text="実績工数を入力して完了してください",
            font=ctk.CTkFont(size=12), text_color=("gray30", "gray70"),
        ).pack(pady=(0, 10))

        entry_row = ctk.CTkFrame(dialog, fg_color="transparent")
        entry_row.pack()
        entry = ctk.CTkEntry(entry_row, placeholder_text="例: 1.5", width=110)
        entry.pack(side="left", padx=4)
        ctk.CTkLabel(entry_row, text="時間").pack(side="left")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(12, 0))

        def _on_skip() -> None:
            dialog.destroy()
            self._do_complete(task, widgets, actual_hours=None)

        def _on_confirm() -> None:
            actual_hours: float | None = None
            try:
                val = entry.get().strip()
                if val:
                    actual_hours = float(val)
            except ValueError:
                pass
            dialog.destroy()
            self._do_complete(task, widgets, actual_hours=actual_hours)

        ctk.CTkButton(
            btn_row, text="スキップ", width=100,
            fg_color="gray50", hover_color="gray40",
            command=_on_skip,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text="記録して完了", width=120,
            command=_on_confirm,
        ).pack(side="left", padx=6)

        entry.bind("<Return>", lambda e: _on_confirm())
        entry.focus()

    def _do_complete(self, task: TaskItem, widgets: dict, actual_hours: float | None) -> None:
        widgets["btn"].configure(state="disabled", text="処理中…")

        def _run() -> None:
            try:
                self._backend.complete_task(task.task_id)
                if actual_hours is not None:
                    try:
                        self._backend.record_work_hours(task.task_id, actual_hours=actual_hours)
                    except Exception as exc:
                        logging.warning("record_work_hours failed: %s", exc)
                self.after(0, lambda: self._mark_done(task))
            except Exception as exc:
                logging.error("complete_task error: %s", exc)
                err = str(exc)[:50]
                self.after(0, lambda: widgets["btn"].configure(state="normal", text="完了"))
                self.after(0, lambda e=err: self._status_lbl.configure(
                    text=f"エラー: {e}", text_color="red"
                ))

        threading.Thread(target=_run, daemon=True).start()

    def _mark_done(self, task: TaskItem) -> None:
        task.status = "completed"
        widgets = self._row_widgets.get(task.task_id)
        if not widgets:
            return

        widgets["title"].configure(
            text_color=("gray60", "gray50"),
            font=ctk.CTkFont(size=13, overstrike=True),
        )
        widgets["btn"].destroy()
        row_idx = widgets["row"]
        done_lbl = ctk.CTkLabel(
            self._scroll, text="✅", font=ctk.CTkFont(size=14), width=80
        )
        done_lbl.grid(row=row_idx, column=2, padx=(0, 6), pady=4)
        widgets["btn"] = done_lbl

        today_str = date.today().isoformat()
        active_overdue = [
            t for t in self._overdue_tasks
            if t.status in ("not_started", "in_progress")
            and t.start_date and t.start_date < today_str
        ]
        incomplete_today = sum(1 for t in self._today_tasks if t.status not in ("completed", "cancelled"))
        done_today = len(self._today_tasks) - incomplete_today
        overdue_count = len(active_overdue)

        parts = []
        if overdue_count:
            parts.append(f"⚠️ 超過 {overdue_count} 件")
        parts.append(f"今日 {incomplete_today} 件未完了 / {done_today} 件完了")
        self._status_lbl.configure(
            text=" ／ ".join(parts),
            text_color=("#d97706", "#f59e0b") if overdue_count else ("gray30", "gray70"),
        )
        logging.debug("Task %s marked as completed in UI", task.task_id)
