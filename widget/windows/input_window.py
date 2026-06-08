from __future__ import annotations
import logging
import threading
import traceback
from datetime import date, datetime
import customtkinter as ctk
from tkcalendar import DateEntry
from widget.clients.backend_client import BackendClient, UserInfo, ProjectInfo
from widget.clients.ollama_client import OllamaClient
from widget.config import Config
from widget.payload_builder import build_payload

_PRIORITY_OPTIONS = ["低", "中", "高", "緊急"]
_NO_SELECT = "（なし）"


class InputWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        config: Config,
        ollama: OllamaClient,
        backend: BackendClient,
        users: list[UserInfo],
        projects: list[ProjectInfo],
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._ollama = ollama
        self._backend = backend
        self._users = users
        self._projects = projects

        self.title("AutoTicket")
        self.geometry("440x190")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._build_input_panel()

    # ──────────────────────────────
    # 入力パネル（初期表示）
    # ──────────────────────────────
    def _build_input_panel(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("440x190")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(top, text="👤").pack(side="left")
        user_names = [u.display_name for u in self._users]
        current = next(
            (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
            user_names[0] if user_names else "",
        )
        self._user_combo = ctk.CTkComboBox(top, values=user_names, width=220, state="readonly")
        self._user_combo.set(current)
        self._user_combo.pack(side="left", padx=8)

        self._text = ctk.CTkTextbox(self, height=70, width=410)
        self._text.pack(padx=16, pady=4)
        self._text.focus()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))
        self._status_lbl = ctk.CTkLabel(btn_row, text="", text_color="gray")
        self._status_lbl.pack(side="left")
        self._submit_btn = ctk.CTkButton(btn_row, text="AIで起票する →", command=self._on_ai_submit)
        self._submit_btn.pack(side="right")

    # ──────────────────────────────
    # AI 解析 → ConfirmPanel 表示
    # ──────────────────────────────
    def _on_ai_submit(self) -> None:
        text = self._text.get("1.0", "end").strip()
        if not text:
            return
        self._submit_btn.configure(state="disabled", text="解析中…")
        self._status_lbl.configure(text="Ollama で解析しています…")

        def _run() -> None:
            parsed = self._ollama.parse(text)
            self.after(0, lambda: self._build_confirm_panel(parsed))

        threading.Thread(target=_run, daemon=True).start()

    # ──────────────────────────────
    # ConfirmPanel（インライン展開）
    # ──────────────────────────────
    def _build_confirm_panel(self, parsed: dict) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("440x330")
        self.title("AutoTicket - 確認")

        ctk.CTkLabel(
            self, text="✅ 解析結果（編集できます）", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(12, 4))

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", padx=16, pady=4)

        def _row(label: str, widget: ctk.CTkBaseClass) -> ctk.CTkBaseClass:
            r = ctk.CTkFrame(frame, fg_color="transparent")
            r.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(r, text=label, width=90, anchor="w").pack(side="left")
            widget.pack(side="left", fill="x", expand=True)
            return widget

        # タイトル
        self._title_entry = ctk.CTkEntry(frame, placeholder_text="タスクタイトル（必須）")
        _row("タイトル", self._title_entry)
        title_val = parsed.get("title") or ""
        self._title_entry.insert(0, title_val)
        if not title_val:
            self._title_entry.configure(border_color="red")

        # 期限（カレンダーピッカー）
        due_str = parsed.get("due_date") or ""
        try:
            _initial = datetime.strptime(due_str, "%Y-%m-%d").date() if due_str else date.today()
        except ValueError:
            _initial = date.today()
        self._due_entry = DateEntry(
            frame,
            date_pattern="yyyy-mm-dd",
            year=_initial.year,
            month=_initial.month,
            day=_initial.day,
            width=18,
            background="#1f538d",
            foreground="white",
            headersbackground="#144870",
            headersforeground="white",
            selectbackground="#1f538d",
            normalbackground="#2b2b2b",
            normalforeground="white",
            weekendbackground="#2b2b2b",
            weekendforeground="#cccccc",
            othermonthbackground="#1a1a1a",
            othermonthforeground="#666666",
        )
        _row("期限", self._due_entry)

        # 担当者
        user_names = [_NO_SELECT] + [u.display_name for u in self._users]
        assignee_raw = parsed.get("assignee_name") or ""
        matched = next(
            (u.display_name for u in self._users if assignee_raw.lower() in u.display_name.lower()),
            _NO_SELECT,
        )
        self._assignee_combo = ctk.CTkComboBox(frame, values=user_names, state="readonly")
        _row("担当者", self._assignee_combo)
        self._assignee_combo.set(matched)

        # プロジェクト
        proj_names = [_NO_SELECT] + [p.name for p in self._projects]
        self._project_combo = ctk.CTkComboBox(frame, values=proj_names, state="readonly")
        _row("プロジェクト", self._project_combo)
        self._project_combo.set(_NO_SELECT)

        # 優先度
        priority_inv = {"low": "低", "medium": "中", "high": "高", "urgent": "緊急"}
        priority_jp = priority_inv.get(parsed.get("priority") or "", "中")
        self._priority_combo = ctk.CTkComboBox(frame, values=_PRIORITY_OPTIONS, state="readonly", width=120)
        _row("優先度", self._priority_combo)
        self._priority_combo.set(priority_jp)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkButton(btn_row, text="キャンセル", width=100, command=self._build_input_panel).pack(side="left")
        self._send_btn = ctk.CTkButton(btn_row, text="送信する", command=self._on_send)
        self._send_btn.pack(side="right")

        self._error_lbl = ctk.CTkLabel(self, text="", text_color="red")
        self._error_lbl.pack(pady=(0, 8))

    # ──────────────────────────────
    # 送信
    # ──────────────────────────────
    def _on_send(self) -> None:
        title = self._title_entry.get().strip()
        if not title:
            self._title_entry.configure(border_color="red")
            self._error_lbl.configure(text="タイトルは必須です")
            return

        payload = build_payload(
            title=title,
            due_date_str=self._due_entry.get(),
            assignee_display=self._assignee_combo.get(),
            project_name=self._project_combo.get(),
            priority_jp=self._priority_combo.get(),
            users=self._users,
            projects=self._projects,
        )
        self._send_btn.configure(state="disabled", text="送信中…")

        def _run() -> None:
            try:
                self._backend.create_task(payload)
                logging.debug("create_task success")
                self.after(0, self._on_success)
            except Exception as exc:
                logging.error("create_task failed:\n" + traceback.format_exc())
                self.after(0, lambda msg=str(exc): self._on_error(msg))

        threading.Thread(target=_run, daemon=True).start()

    def _on_success(self) -> None:
        try:
            self._build_input_panel()
            self._status_lbl.configure(text="✅ 起票しました！", text_color="green")
            self.after(3000, lambda: self._status_lbl.configure(text=""))
        except Exception:
            logging.error("_on_success failed:\n" + traceback.format_exc())

    def _on_error(self, msg: str) -> None:
        self._error_lbl.configure(text=f"送信エラー: {msg}")
        self._send_btn.configure(state="normal", text="送信する")
