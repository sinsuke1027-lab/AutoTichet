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
from widget.services.history_store import add_history
from widget.services.toast_notifier import notify_success
import json as _json
from widget.services.audio_recorder import AudioRecorder
from widget.services.connection_monitor import ConnectionMonitor, ConnectionState
from widget.services.draft_queue import DraftQueue
from widget.ui_constants import WIN_INPUT

_DND_AVAILABLE = False
try:
    from tkinterdnd2 import DND_FILES  # type: ignore[import]
    _DND_AVAILABLE = True
except ImportError:
    pass

_PRIORITY_OPTIONS = ["低", "中", "高", "緊急"]
_NO_SELECT = "（なし）"


def _load_templates() -> list[dict]:
    """Load text templates from JSON file."""
    p = Path(__file__).parent.parent / "data" / "templates.json"
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


class InputWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        config: Config,
        ollama: OllamaClient,
        backend: BackendClient,
        users: list[UserInfo],
        projects: list[ProjectInfo],
        clipboard: ClipboardReader | None = None,
        vision: VisionParser | None = None,
        connection_monitor: ConnectionMonitor | None = None,
        draft_queue: DraftQueue | None = None,
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
        self._recorder = AudioRecorder()
        self._recording = False
        self._connection_monitor = connection_monitor
        self._draft_queue = draft_queue

        self.title("AutoTicket")
        self.geometry(f"{WIN_INPUT[0]}x{WIN_INPUT[1]}")
        self.resizable(True, False)
        self.attributes("-topmost", True)
        # Escape / 閉じるの処理は親（AppController._show_window）が
        # WM_DELETE_WINDOW と Escape の両方を _on_window_close に紐づけて一元管理する。
        # ここで self.destroy() を直接バインドすると _window_open フラグが
        # リセットされず、以後ウィンドウが開けなくなる（issue #22）。
        self._build_input_panel()

    # ──────────────────────────────
    # 入力パネル（初期表示）
    # ──────────────────────────────
    def _build_input_panel(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry(f"{WIN_INPUT[0]}x{WIN_INPUT[1]}")

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
        if self._recorder.is_available:
            self._mic_btn = ctk.CTkButton(
                tools, text="🎤 音声入力", width=110, height=28,
                command=self._toggle_recording,
            )
            self._mic_btn.pack(side="left", padx=(8, 0))

        templates = _load_templates()
        if templates:
            tpl_frame = ctk.CTkFrame(self, fg_color="transparent")
            tpl_frame.pack(fill="x", padx=16, pady=(0, 2))
            ctk.CTkLabel(tpl_frame, text="📝", width=24).pack(side="left")
            tpl_names = ["テンプレートを選択…"] + [t["name"] for t in templates]
            tpl_combo = ctk.CTkComboBox(
                tpl_frame, values=tpl_names, width=200, state="readonly",
                command=lambda v, ts=templates: self._on_template_select(v, ts),
            )
            tpl_combo.set("テンプレートを選択…")
            tpl_combo.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(
            self, text="タスク内容を自由に入力（Ctrl+Enter で送信）",
            text_color=("gray30", "gray70"), anchor="w", font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=18, pady=(2, 0))

        self._text = ctk.CTkTextbox(self, height=80)
        self._text.pack(fill="x", padx=16, pady=(2, 2))
        self._text.bind("<Control-Return>", lambda e: self._on_ai_submit())
        if self._last_input_text:
            self._text.insert("1.0", self._last_input_text)
        self._text.focus()
        self._setup_dnd()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(2, 12))
        self._status_lbl = ctk.CTkLabel(btn_row, text="", text_color=("gray30", "gray70"))
        self._status_lbl.pack(side="left")
        self._submit_btn = ctk.CTkButton(btn_row, text="AIで起票する →", command=self._on_ai_submit)
        self._submit_btn.pack(side="right")

    def _show_clipboard_history(self) -> None:
        self._status_lbl.configure(text="履歴を取得中…", text_color=("gray30", "gray70"))

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

    def _on_template_select(self, name: str, templates: list[dict]) -> None:
        """Handle template selection and insert text into textarea."""
        if name == "テンプレートを選択…":
            return
        tpl = next((t for t in templates if t["name"] == name), None)
        if tpl:
            self._text.delete("1.0", "end")
            self._text.insert("1.0", tpl["text"])
            self._text.focus()

    def _setup_dnd(self) -> None:
        if not _DND_AVAILABLE:
            return
        try:
            inner = self._text._textbox  # type: ignore[attr-defined]
            inner.drop_target_register(DND_FILES)
            inner.dnd_bind("<<Drop>>", self._on_drop)
        except Exception as exc:
            logging.debug("D&D setup failed: %s", exc)

    def _on_drop(self, event: object) -> None:
        raw: str = getattr(event, "data", "")
        raw = raw.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = Path(raw)
        suffix = path.suffix.lower()
        if suffix == ".txt":
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                self._text.delete("1.0", "end")
                self._text.insert("1.0", text[:1000])
                self._text.focus()
            except Exception as exc:
                logging.error("D&D txt read error: %s", exc)
        elif suffix in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            self._submit_btn.configure(state="disabled")
            self._status_lbl.configure(
                text="画像を解析中…", text_color=("gray30", "gray70")
            )
            self._start_elapsed_timer("画像を解析中")

            def _run() -> None:
                parsed = self._vision.parse_image(path)
                self.after(0, lambda p=parsed: self._on_image_parsed(p))

            threading.Thread(target=_run, daemon=True).start()
        else:
            self._status_lbl.configure(
                text=f"未対応のファイル形式: {suffix}",
                text_color=("gray30", "gray70"),
            )

    def _toggle_recording(self) -> None:
        if not self._recording:
            self._recording = True
            self._mic_btn.configure(
                text="⏹ 録音停止", fg_color="red", hover_color="#cc0000"
            )
            self._status_lbl.configure(text="🎤 録音中…", text_color="red")
            self._recorder.start()
        else:
            self._recording = False
            self._mic_btn.configure(
                text="🎤 音声入力",
                fg_color=["#3B8ED0", "#1F6AA5"],
                hover_color=["#36719F", "#144870"],
            )
            self._status_lbl.configure(
                text="文字起こし中…", text_color=("gray30", "gray70")
            )
            threading.Thread(target=self._run_transcribe, daemon=True).start()

    def _run_transcribe(self) -> None:
        audio_path = self._recorder.stop_and_save()
        if audio_path is None:
            self.after(0, lambda: self._status_lbl.configure(text=""))
            return
        text = self._recorder.transcribe(audio_path)
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass
        if text:
            self.after(0, lambda t=text: self._insert_transcribed(t))
        else:
            self.after(
                0,
                lambda: self._status_lbl.configure(
                    text="文字起こし失敗", text_color=("gray30", "gray70")
                ),
            )

    def _insert_transcribed(self, text: str) -> None:
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.focus()
        self._status_lbl.configure(text="")

    def _open_image_file(self) -> None:
        path_str = filedialog.askopenfilename(
            title="画像ファイルを選択",
            filetypes=[("画像ファイル", "*.png *.jpg *.jpeg *.bmp *.gif"), ("すべてのファイル", "*.*")],
            parent=self,
        )
        if not path_str:
            return
        self._submit_btn.configure(state="disabled")
        self._status_lbl.configure(text="画像を解析中…", text_color=("gray30", "gray70"))
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
                self, text=f"入力: {preview}", text_color=("gray30", "gray70"),
                font=ctk.CTkFont(size=11), wraplength=440, justify="left",
            ).pack(padx=20, pady=(0, 4))

        ctk.CTkLabel(
            self, text="回答（Ctrl+Enter で送信）", text_color=("gray30", "gray70"),
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=22)

        self._hearing_text = ctk.CTkTextbox(self, height=60)
        self._hearing_text.pack(fill="x", padx=20, pady=(2, 6))
        self._hearing_text.bind("<Control-Return>", lambda e: self._on_hearing_answer(parsed))
        self._hearing_text.focus()

        self._status_lbl = ctk.CTkLabel(self, text="", text_color=("gray30", "gray70"))
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
        _is_dark = ctk.get_appearance_mode() == "Dark"
        self._due_entry = DateEntry(
            due_frame,
            date_pattern="yyyy-mm-dd",
            year=_initial.year,
            month=_initial.month,
            day=_initial.day,
            width=14,
            background="#1f538d" if _is_dark else "#1f538d",
            foreground="white",
            headersbackground="#144870" if _is_dark else "#1a6fb5",
            headersforeground="white",
            selectbackground="#1f538d",
            normalbackground="#2b2b2b" if _is_dark else "#ffffff",
            normalforeground="white" if _is_dark else "#1a1a1a",
            weekendbackground="#2b2b2b" if _is_dark else "#f5f5f5",
            weekendforeground="#cccccc" if _is_dark else "#555555",
            othermonthbackground="#1a1a1a" if _is_dark else "#eeeeee",
            othermonthforeground="#666666" if _is_dark else "#aaaaaa",
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
        self._priority_combo = ctk.CTkComboBox(
            frame, values=_PRIORITY_OPTIONS, state="readonly", width=120
        )
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
        ctk.CTkButton(
            btn_row, text="キャンセル", width=100, command=self._build_input_panel
        ).pack(side="left")
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
    def _show_offline_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("バックエンド未接続")
        dialog.geometry("360x180")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="⚠️  バックエンドに接続できません",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text="このまま送信すると下書きとして保存され、\n復旧後に自動送信されます。",
            justify="center",
            text_color=("gray30", "gray70"),
        ).pack(pady=(0, 12))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def _save_draft() -> None:
            dialog.destroy()
            if self._draft_queue is None:
                return
            title = self._build_pending_title()
            if not title:
                return
            payload = self._build_pending_payload()
            if payload:
                self._draft_queue.add(payload)
                self._last_input_text = ""
                self._build_input_panel()
                self._status_lbl.configure(
                    text="📋 下書き保存しました", text_color=("gray30", "gray70")
                )

        ctk.CTkButton(
            btn_row, text="設定を開く", width=110,
            fg_color="gray40", hover_color="gray30",
            command=lambda: (dialog.destroy(), self._open_settings()),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text="下書き保存", width=110,
            command=_save_draft,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_row, text="閉じる", width=90,
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).pack(side="left", padx=6)

    def _build_pending_title(self) -> str:
        """オフラインダイアログから下書き保存するタイトルを取得する。ConfirmPanel表示中はタイトル入力欄から取得。"""
        try:
            return self._title_entry.get().strip()
        except AttributeError:
            return self._text.get("1.0", "end").strip()[:80]

    def _build_pending_payload(self) -> dict | None:
        """ConfirmPanel の現在値から payload を組み立てる。入力パネル表示中は空dictを返す。"""
        try:
            from widget.payload_builder import build_payload as _build
            title = self._title_entry.get().strip()
            if not title:
                return None
            due_date_str = "" if self._no_due_var.get() else self._due_entry.get()
            return _build(
                title=title,
                due_date_str=due_date_str,
                assignee_display=self._assignee_combo.get(),
                project_name=self._project_combo.get(),
                priority_jp=self._priority_combo.get(),
                users=self._users,
                projects=self._projects,
                description=self._desc_text.get("1.0", "end").strip(),
            )
        except AttributeError:
            return {"title": self._text.get("1.0", "end").strip()[:80]}

    def _open_settings(self) -> None:
        """設定ウィンドウを開く（main.py の _show_settings_window を呼び出す）。"""
        try:
            master = self.master
            if hasattr(master, "_show_settings_window"):
                master._show_settings_window()  # type: ignore[attr-defined]
        except Exception as exc:
            logging.debug("_open_settings failed: %s", exc)

    def _on_send(self) -> None:
        # バックエンド切断時はオフラインダイアログを表示
        if self._connection_monitor is not None and not self._connection_monitor.is_connected():
            self._show_offline_dialog()
            return
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
        proj_name = self._project_combo.get()
        if proj_name == _NO_SELECT:
            proj_name = None
        self._send_btn.configure(state="disabled", text="送信中…")

        def _run() -> None:
            try:
                result = self._backend.create_task(payload)
                logging.debug("create_task success")
                self.after(0, lambda: self._on_success(result, title, proj_name))
            except Exception as exc:
                logging.error("create_task failed:\n" + traceback.format_exc())
                self.after(0, lambda msg=str(exc): self._on_error(msg))

        threading.Thread(target=_run, daemon=True).start()

    def _on_success(self, result: dict, title: str, project_name: str | None) -> None:
        try:
            task_id = str(result.get("id", ""))
            add_history(task_id, title, project_name)
            task_url = ""
            if task_id and self._config.frontend_url:
                task_url = f"{self._config.frontend_url.rstrip('/')}/tasks/{task_id}"
            notify_success(title, launch_url=task_url)
            self._last_input_text = ""
            self._build_input_panel()
            self._status_lbl.configure(
                text="✅ 起票しました！", text_color="green",
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            self.after(
                3000,
                lambda: self._status_lbl.configure(text="", font=ctk.CTkFont(size=13)),
            )
        except Exception:
            logging.error("_on_success failed:\n" + traceback.format_exc())

    def _on_error(self, msg: str) -> None:
        self._error_lbl.configure(text=f"送信エラー: {msg}")
        self._send_btn.configure(state="normal", text="送信する")
