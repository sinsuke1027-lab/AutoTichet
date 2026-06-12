# widget/windows/first_run_wizard.py
from __future__ import annotations
import sys
import threading
from typing import Callable

import customtkinter as ctk
import httpx

from widget.clients.backend_client import BackendClient, UserInfo
from widget.config import Config, normalize_backend_url, save_config
from widget.services import autostart
from widget.ui_constants import (
    DANGER, FONT_H1, FONT_H2, FONT_BODY, FONT_SMALL,
    PAD_S, PAD_M, PAD_L, PRIMARY, SUCCESS, WIN_WIZARD,
)


class FirstRunWizard(ctk.CTkToplevel):
    """3ステップの初回セットアップウィザード。
    完了時に config.first_run_complete = True を保存する。
    × で閉じた場合は保存しない（呼び出し側が first_run_complete を確認して終了する）。
    """

    def __init__(self, parent: ctk.CTk, config: Config) -> None:
        super().__init__(parent)
        self.title("AutoTicket セットアップ")
        self.geometry(f"{WIN_WIZARD[0]}x{WIN_WIZARD[1]}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set()  # モーダル

        self._config = config
        self._users: list[UserInfo] = []
        self._step = 1

        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True, padx=PAD_L, pady=PAD_M)

        self._show_step1()

    # ──────────────────────────────
    # Step 1: バックエンド URL
    # ──────────────────────────────
    def _show_step1(self) -> None:
        self._clear()
        self._step_label("バックエンドURLを入力してください", "1 / 3")

        ctk.CTkLabel(self._content_frame, text="バックエンド URL", font=ctk.CTkFont(*FONT_BODY)).pack(anchor="w", pady=(PAD_M, 4))
        self._url_entry = ctk.CTkEntry(self._content_frame, width=380)
        self._url_entry.insert(0, self._config.backend_url or "http://localhost:8000")
        self._url_entry.pack(fill="x")

        self._test_lbl = ctk.CTkLabel(self._content_frame, text="", font=ctk.CTkFont(*FONT_SMALL))
        self._test_lbl.pack(pady=(4, 0))

        btn_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(PAD_M, 0))

        ctk.CTkButton(
            btn_row, text="接続テスト", width=100,
            fg_color="gray50", hover_color="gray40",
            command=self._test_connection,
        ).pack(side="left")

        self._next_btn1 = ctk.CTkButton(
            btn_row, text="次へ →", width=100,
            fg_color=PRIMARY,
            command=self._step1_next,
        )
        self._next_btn1.pack(side="right")

        ctk.CTkButton(
            btn_row, text="スキップ", width=80,
            fg_color="transparent", text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            command=self._step1_next,
        ).pack(side="right", padx=PAD_S)

    def _test_connection(self) -> None:
        url = self._url_entry.get().strip()
        self._test_lbl.configure(text="接続テスト中…", text_color=("gray40", "gray60"))

        def _run() -> None:
            try:
                resp = httpx.get(f"{url}/health", timeout=5.0)
                ok = resp.status_code == 200
            except Exception:
                ok = False
            self.after(0, lambda: self._test_lbl.configure(
                text="✓ 接続成功" if ok else "✗ 接続失敗（URLを確認してください）",
                text_color=SUCCESS if ok else DANGER,
            ))

        threading.Thread(target=_run, daemon=True).start()

    def _step1_next(self) -> None:
        self._config.backend_url = normalize_backend_url(self._url_entry.get())
        self._show_step2()

    # ──────────────────────────────
    # Step 2: ユーザー選択
    # ──────────────────────────────
    def _show_step2(self) -> None:
        self._clear()
        self._step_label("あなたのユーザーを選択してください", "2 / 3")

        self._user_var = ctk.StringVar(value="読み込み中…")
        self._user_combo = ctk.CTkComboBox(
            self._content_frame, variable=self._user_var, width=380, state="disabled"
        )
        self._user_combo.pack(pady=(PAD_M, 0))

        btn_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(PAD_M, 0))

        ctk.CTkButton(
            btn_row, text="← 戻る", width=80,
            fg_color="gray50", hover_color="gray40",
            command=self._show_step1,
        ).pack(side="left")

        self._next_btn2 = ctk.CTkButton(
            btn_row, text="次へ →", width=100,
            fg_color=PRIMARY,
            command=self._step2_next,
        )
        self._next_btn2.pack(side="right")

        ctk.CTkButton(
            btn_row, text="後で設定", width=90,
            fg_color="transparent", text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            command=self._step2_next,
        ).pack(side="right", padx=PAD_S)

        threading.Thread(target=self._fetch_users, daemon=True).start()

    def _fetch_users(self) -> None:
        try:
            client = BackendClient(self._config.backend_url, UserInfo(user_id="", display_name=""))
            self._users = client.get_users_dev()
            names = [u.display_name for u in self._users]
        except Exception:
            names = []
        self.after(0, lambda: self._on_users_loaded(names))

    def _on_users_loaded(self, names: list[str]) -> None:
        if names:
            self._user_combo.configure(values=names, state="normal")
            # 既存の selected_user_id に対応するユーザーを初期選択
            current = next(
                (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
                names[0],
            )
            self._user_var.set(current)
        else:
            self._user_combo.configure(values=[], state="disabled")
            self._user_var.set("（取得できませんでした）")

    def _step2_next(self) -> None:
        selected_name = self._user_var.get()
        matched = next((u for u in self._users if u.display_name == selected_name), None)
        if matched:
            self._config.selected_user_id = matched.user_id
        self._show_step3()

    # ──────────────────────────────
    # Step 3: 完了
    # ──────────────────────────────
    def _show_step3(self) -> None:
        self._clear()
        self._step_label("セットアップ完了！", "3 / 3")

        user_name = next(
            (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
            self._config.selected_user_id or "（未設定）",
        )

        ctk.CTkLabel(
            self._content_frame,
            text=f"URL:  {self._config.backend_url or '（未設定）'}\nユーザー:  {user_name}",
            font=ctk.CTkFont(*FONT_BODY),
            justify="left",
        ).pack(pady=(PAD_M, PAD_S))

        # 自動起動トグル（.exe ビルド時のみ有効）
        self._autostart_var = ctk.BooleanVar(value=autostart.is_enabled())
        toggle_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        toggle_row.pack(pady=(PAD_S, PAD_M))
        switch = ctk.CTkSwitch(
            toggle_row,
            text="Windowsログイン時に自動起動",
            variable=self._autostart_var,
            font=ctk.CTkFont(*FONT_BODY),
        )
        switch.pack(side="left")
        if not autostart.is_frozen():
            switch.configure(state="disabled")
            ctk.CTkLabel(
                toggle_row, text=" (.exe ビルド後に有効)",
                font=ctk.CTkFont(*FONT_SMALL),
                text_color=("gray40", "gray60"),
            ).pack(side="left")

        ctk.CTkButton(
            self._content_frame, text="起動する 🚀", width=160,
            fg_color=PRIMARY,
            command=self._complete,
        ).pack(pady=(PAD_S, 0))

    def _complete(self) -> None:
        self._config.first_run_complete = True
        save_config(self._config)
        if self._autostart_var.get() and autostart.is_frozen():
            autostart.enable(autostart.get_current_exe_path())
        elif not self._autostart_var.get():
            autostart.disable()
        self.destroy()

    # ──────────────────────────────
    # 共通ヘルパー
    # ──────────────────────────────
    def _clear(self) -> None:
        for w in self._content_frame.winfo_children():
            w.destroy()

    def _step_label(self, title: str, step_text: str) -> None:
        row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=title, font=ctk.CTkFont(*FONT_H2)).pack(side="left")
        ctk.CTkLabel(
            row, text=step_text,
            font=ctk.CTkFont(*FONT_SMALL),
            text_color=("gray40", "gray60"),
        ).pack(side="right")
