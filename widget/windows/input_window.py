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
from widget.services.vision_parser import VisionParser
from tkinter import filedialog
from pathlib import Path
from widget.services.clipboard_reader import ClipboardReader

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
        clipboard: ClipboardReader,
        vision: VisionParser,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._ollama = ollama
        self._vision = vision
        self._backend = backend
        self._users = users
        self._projects = projects
        self._clipboard = clipboard
        self._last_input_text: str = ""

        self.title("AutoTicket")
        self.geometry("480x250")
        self.resizable(True, False)
        self.attributes("-topmost", True)
        self.bind("<Escape>", lambda e: self.destroy())
        self._build_input_panel()

    # ──────────────────────────────
    # 入力パネル（初期表示）
    # ──────────────────────────────
    def _build_input_panel(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("480x250")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(top, text="👤").pack(side="left")
        user_names = [u.display_name for u in self._users]
        current = next(
            (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
            user_names[0] if user_names else "",
        )
        self._user_combo = ctk.CTkComboBox(top, values=user_names, width=220, state="readonly")
        self._user_combo.set(current)
        self._user_combo.pack(side="left", padx=8)

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=16, pady=(0, 2))
        ctk.CTkButton(
            tools, text="📋 クリップボード履歴", width=160, height=28,
            command=self._show_clipboard_history,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            tools, text="🖼️ 画像ファイル", width=170, height=28,
            command=self._open_image_file,
        ).pack(side="left")

        ctk.CTkLabel(
            self, text="タスク内容を自由に入力（Ctrl+Enter で送信）",
            text_color="gray", anchor="w", font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=18, pady=(2, 0))

        self._text = ctk.CTkTextbox(self, height=80)
        self._text.pack(fill="x", padx=16, pady=(2, 2))
        self._text.bind("<Control-Return>", lambda e: self._on_ai_submit())
        if self._last_input_text:
            self._text.insert("1.0", self._last_input_text)
        self._text.focus()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(2, 12))
        self._status_lbl = ctk.CTkLabel(btn_row, text="", text_color="gray")
        self._status_lbl.pack(side="left")
        self._submit_btn = ctk.CTkButton(btn_row, text="AIで起票する →", command=self._on_ai_submit)
        self._submit_btn.pack(side="right")

    def _show_clipboard_history(self) -> None:
        self._status_lbl.configure(text="履歴を取得中…", text_color="gray")

        def _run() -> None:
            from widget.services.clipboard_history import get_clipboard_history
            items = get_clipboard_history()
            self.after(0, lambda: self._on_history_fetched(items))

        threading.Thread(target=_run, daemon=True).start()

    def _on_history_fetched(self, items: list[str]) -> None:
        self._status_lbl.configure(text="")
        from widget.windows.history_picker_window import HistoryPickerWindow

        def _on_select(text: str) -> None:
            self._text.delete("1.0", "end")
            self._text.insert("1.0", text)

        HistoryPickerWindow(self, items, _on_select)

    def _open_image_file(self) -> None:
        path_str = filedialog.askopenfilename(
            title="画像ファイルを選択",
            filetypes=[("画像ファイル", "*.png *.jpg *.jpeg *.bmp *.gif"), ("すべてのファイル", "*.*")],
            parent=self,
        )
        if not path_str:
            return
        self._submit_btn.configure(state="disabled")
        self._status_lbl.configure(text="画像を解析中…", text_color="gray")
        self._start_elapsed_timer("画像を解析中")

        def _run() -> None:
            parsed = self._vision.parse_image(Path(path_str))
            self.after(0, lambda p=parsed: self._on_image_parsed(p))

        threading.Thread(target=_run, daemon=True).start()

    def _on_image_parsed(self, parsed: dict) -> None:
        self._stop_elapsed_timer()
        self._submit_btn.configure(state="normal")
        self._status_lbl.configure(text="")
        self._build_confirm_panel(parsed)

    # ──────────────────────────────
    # AI 解析
    # ──────────────────────────────
    def _start_elapsed_timer(self, label: str) -> None:
        self._parsing_active = True
        self._elapsed_secs = 0

        def _tick() -> None:
            if not self._parsing_active:
                return
            self._elapsed_secs += 1
            try:
                self._status_lbl.configure(text=f"{label}（{self._elapsed_secs}秒）")
                self.after(1000, _tick)
            except Exception:
                pass

        self.after(1000, _tick)

    def _stop_elapsed_timer(self) -> None:
        self._parsing_active = False

    def _on_ai_submit(self) -> None:
        text = self._text.get("1.0", "end").strip()
        if not text:
            self._text.configure(border_color="red")
            return
        self._text.configure(border_color=("gray65", "gray25"))
        self._submit_btn.configure(state="disabled", text="解析中…")
        self._status_lbl.configure(text="Ollama で解析しています…")
        self._start_elapsed_timer("Ollama で解析しています")
        self._last_input_text = text

        def _run() -> None:
            parsed = self._ollama.parse(text)
            self.after(0, lambda: self._on_ai_done(parsed))

        threading.Thread(target=_run, daemon=True).start()

    def _on_ai_done(self, parsed: dict) -> None:
        self._stop_elapsed_timer()
        self._submit_btn.configure(state="normal", text="AIで起票する →")
        self._status_lbl.configure(text="")
        question = parsed.get("clarifying_question")
        if question and question != "null":
            self._build_hearing_panel(parsed, question)
        else:
            self._build_confirm_panel(parsed)

    # ──────────────────────────────
    # HearingPanel
    # ──────────────────────────────
    def _build_hearing_panel(self, parsed: dict, question: str) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("480x300")
        self.title("AutoTicket - ヒアリング")

        ctk.CTkLabel(
            self, text="💬 AIからの質問", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(14, 4))

        ctk.CTkLabel(
            self, text=question, wraplength=440, justify="left"
        ).pack(padx=20, pady=(0, 6))

        if self._last_input_text:
            preview = (
                self._last_input_text[:60] + "…"
                if len(self._last_input_text) > 60
                else self._last_input_text
            )
            ctk.CTkLabel(
                self, text=f"入力: {preview}", text_color="gray",
                font=ctk.CTkFont(size=11), wraplength=440, justify="left",
            ).pack(padx=20, pady=(0, 4))

        ctk.CTkLabel(
            self, text="回答（Ctrl+Enter で送信）", text_color="gray",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=22)

        self._hearing_text = ctk.CTkTextbox(self, height=60)
        self._hearing_text.pack(fill="x", padx=20, pady=(2, 6))
        self._hearing_text.bind("<Control-Return>", lambda e: self._on_hearing_answer(parsed))
        self._hearing_text.focus()

        self._status_lbl = ctk.CTkLabel(self, text="", text_color="gray")
        self._status_lbl.pack()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(4, 12))

        ctk.CTkButton(
            btn_row, text="スキップ", width=110,
            fg_color="gray40", hover_color="gray30",
            command=lambda: self._build_confirm_panel(parsed),
        ).pack(side="left", padx=8)

        self._hearing_btn = ctk.CTkButton(
            btn_row, text="回答して起票へ →", width=160,
            command=lambda: self._on_hearing_answer(parsed),
        )
        self._hearing_btn.pack(side="left", padx=8)

    def _on_hearing_answer(self, parsed: dict) -> None:
        answer = self._hearing_text.get("1.0", "end").strip()
        if not answer:
            self._build_confirm_panel(parsed)
            return

        self._hearing_btn.configure(state="disabled", text="生成中…")
        self._start_elapsed_timer("説明文を生成中")

        def _run() -> None:
            description = self._ollama.generate_description(self._last_input_text, answer)
            parsed["description"] = description
            self.after(0, lambda: self._on_description_done(parsed))

        threading.Thread(target=_run, daemon=True).start()

    def _on_description_done(self, parsed: dict) -> None:
        self._stop_elapsed_timer()
        self._build_confirm_panel(parsed)

    # ──────────────────────────────
    # ConfirmPanel
    # ──────────────────────────────
    def _build_confirm_panel(self, parsed: dict) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("480x460")
        self.title("AutoTicket - 確認")

        ctk.CTkLabel(
            self, text="✅ 解析結果（編集できます）", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(12, 4))

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=16, pady=4)
        frame.columnconfigure(1, weight=1)

        row_idx = [0]

        def _row(label: str, widget: ctk.CTkBaseClass) -> ctk.CTkBaseClass:
            ctk.CTkLabel(frame, text=label, width=80, anchor="w").grid(
                row=row_idx[0], column=0, padx=(8, 4), pady=3, sticky="w"
            )
            widget.grid(row=row_idx[0], column=1, padx=(0, 8), pady=3, sticky="ew")
            row_idx[0] += 1
            return widget

        # タイトル
        self._title_entry = ctk.CTkEntry(frame, placeholder_text="タスクタイトル（必須）")
        _row("タイトル", self._title_entry)
        title_val = parsed.get("title") or ""
        self._title_entry.insert(0, title_val)
        if not title_val:
            self._title_entry.configure(border_color="red")

        # 期限 + 「なし」チェックボックス
        due_str = parsed.get("due_date") or ""
        try:
            _initial = datetime.strptime(due_str, "%Y-%m-%d").date() if due_str else date.today()
        except ValueError:
            _initial = date.today()

        due_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._due_entry = DateEntry(
            due_frame,
            date_pattern="yyyy-mm-dd",
            year=_initial.year,
            month=_initial.month,
            day=_initial.day,
            width=14,
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
        self._due_entry.pack(side="left")
        self._no_due_var = ctk.BooleanVar(value=not bool(due_str))
        ctk.CTkCheckBox(
            due_frame, text="なし", variable=self._no_due_var,
            width=60, command=self._on_no_due_toggle,
        ).pack(side="left", padx=(8, 0))
        _row("期限", due_frame)
        self._on_no_due_toggle()

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

        # 説明（任意）
        self._desc_text = ctk.CTkTextbox(frame, height=60)
        _row("説明（任意）", self._desc_text)
        desc_val = parsed.get("description") or ""
        if desc_val:
            self._desc_text.insert("1.0", desc_val)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkButton(btn_row, text="キャンセル", width=100, command=self._build_input_panel).pack(side="left")
        self._send_btn = ctk.CTkButton(btn_row, text="送信する", command=self._on_send)
        self._send_btn.pack(side="right")

        self._error_lbl = ctk.CTkLabel(self, text="", text_color="red")
        self._error_lbl.pack(pady=(0, 8))

    def _on_no_due_toggle(self) -> None:
        if self._no_due_var.get():
            self._due_entry.configure(state="disabled")
        else:
            self._due_entry.configure(state="normal")

    # ──────────────────────────────
    # 送信
    # ──────────────────────────────
    def _on_send(self) -> None:
        title = self._title_entry.get().strip()
        if not title:
            self._title_entry.configure(border_color="red")
            self._error_lbl.configure(text="タイトルは必須です")
            return

        due_date_str = "" if self._no_due_var.get() else self._due_entry.get()

        payload = build_payload(
            title=title,
            due_date_str=due_date_str,
            assignee_display=self._assignee_combo.get(),
            project_name=self._project_combo.get(),
            priority_jp=self._priority_combo.get(),
            users=self._users,
            projects=self._projects,
            description=self._desc_text.get("1.0", "end").strip(),
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
            self._last_input_text = ""
            self._build_input_panel()
            self._status_lbl.configure(
                text="✅ 起票しました！", text_color="green",
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            self.after(3000, lambda: self._status_lbl.configure(text="", font=ctk.CTkFont(size=13)))
        except Exception:
            logging.error("_on_success failed:\n" + traceback.format_exc())

    def _on_error(self, msg: str) -> None:
        self._error_lbl.configure(text=f"送信エラー: {msg}")
        self._send_btn.configure(state="normal", text="送信する")
