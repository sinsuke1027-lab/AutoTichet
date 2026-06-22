# widget/windows/first_run_wizard.py
from __future__ import annotations
import logging
import queue
import re
import threading
import time

import customtkinter as ctk
import httpx

from widget.clients.backend_client import BackendClient, UserInfo
from widget.config import Config, normalize_backend_url, save_config
from widget.services import autostart
from widget.ui_constants import (
    DANGER, FONT_H2, FONT_BODY, FONT_SMALL,
    PAD_S, PAD_M, PAD_L, PRIMARY, SUCCESS, WIN_WIZARD,
)


class FirstRunWizard(ctk.CTkToplevel):
    """3ステップの初回セットアップウィザード。"""

    def __init__(self, parent: ctk.CTk, config: Config) -> None:
        super().__init__(parent)
        self.title("AutoTicket セットアップ")
        self.geometry(f"{WIN_WIZARD[0]}x{WIN_WIZARD[1]}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set()

        self._config = config
        self._users: list[UserInfo] = []
        self._testing: bool = False
        self._fetch_in_progress: bool = False

        # バックグラウンドスレッドから Tkinter を直接呼ぶのはスレッドセーフでない。
        # スレッドはキューに結果を入れるだけにして、メインスレッドが 100ms ごとに取り出す。
        self._q: queue.Queue[tuple] = queue.Queue()

        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True, padx=PAD_L, pady=PAD_M)

        self._show_step1()
        # キューの監視ループを開始（メインスレッドからなので安全）
        self.after(100, self._drain_queue)

    def _drain_queue(self) -> None:
        """100ms ごとにバックグラウンドスレッドからの結果をメインスレッドで処理する。"""
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "test_done":
                    _, ok, detail, elapsed = msg
                    self._on_test_done(ok, detail, elapsed)
                elif kind == "users_loaded":
                    _, names = msg
                    self._on_users_loaded(names)
        except queue.Empty:
            pass
        try:
            self.after(100, self._drain_queue)
        except Exception:
            pass  # ウィザードが既に破棄されている場合は無視

    # ──────────────────────────────
    # Step 1: バックエンド URL
    # ──────────────────────────────
    def _show_step1(self) -> None:
        self._testing = False
        self._fetch_in_progress = False
        self._clear()
        self._step_label("バックエンドURLを入力してください", "1 / 3")

        ctk.CTkLabel(
            self._content_frame, text="バックエンド URL", font=ctk.CTkFont(*FONT_BODY),
        ).pack(anchor="w", pady=(PAD_M, 4))

        self._url_entry = ctk.CTkEntry(self._content_frame, width=380)
        self._url_entry.insert(0, self._config.backend_url or "http://localhost:8000")
        self._url_entry.pack(fill="x")

        self._test_lbl = ctk.CTkLabel(
            self._content_frame,
            text="※ HuggingFace Spaces はスリープ復帰に最大60秒かかります",
            font=ctk.CTkFont(*FONT_SMALL),
            text_color=("gray40", "gray60"),
        )
        self._test_lbl.pack(pady=(4, 0))

        btn_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(PAD_M, 0))

        self._test_btn = ctk.CTkButton(
            btn_row, text="接続テスト", width=100,
            fg_color="gray50", hover_color="gray40",
            command=self._test_connection,
        )
        self._test_btn.pack(side="left")

        ctk.CTkButton(
            btn_row, text="次へ →", width=100,
            fg_color=PRIMARY,
            command=self._step1_next,
        ).pack(side="right")

        ctk.CTkButton(
            btn_row, text="スキップ", width=80,
            fg_color="transparent", text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            command=self._step1_next,
        ).pack(side="right", padx=PAD_S)

    def _test_connection(self) -> None:
        raw = self._url_entry.get().strip()
        url = normalize_backend_url(raw)
        logging.debug("接続テスト開始: %s", url)

        self._testing = True
        self._test_lbl.configure(text="接続テスト中… (0秒)", text_color=("gray40", "gray60"))
        self._test_btn.configure(state="disabled")

        def _run() -> None:
            detail = ""
            t0 = time.time()
            try:
                resp = httpx.get(f"{url}/health", timeout=60.0)
                ok = resp.status_code == 200
                if not ok:
                    detail = f"HTTP {resp.status_code}"
            except Exception as e:
                ok = False
                detail = type(e).__name__
            elapsed = int(time.time() - t0)
            logging.debug("接続テスト完了: ok=%s detail=%s elapsed=%ds", ok, detail, elapsed)
            self._testing = False
            # Tkinter を直接呼ばずキューに入れる
            self._q.put(("test_done", ok, detail, elapsed))

        threading.Thread(target=_run, daemon=True).start()
        # カウンターはメインスレッドの after チェーンで動かす（スレッド不要）
        self.after(1000, self._test_tick)

    def _test_tick(self) -> None:
        """メインスレッドで 1 秒ごとにカウンターを更新する。"""
        if not self._testing:
            return
        try:
            current = self._test_lbl.cget("text")
            m = re.search(r"\((\d+)秒\)", current)
            n = int(m.group(1)) + 1 if m else 1
            self._test_lbl.configure(
                text=f"接続テスト中… ({n}秒)",
                text_color=("gray40", "gray60"),
            )
        except Exception as exc:
            logging.warning("_test_tick error: %s", exc)
        self.after(1000, self._test_tick)

    def _on_test_done(self, ok: bool, detail: str, elapsed: int) -> None:
        logging.debug("_on_test_done: ok=%s detail=%s elapsed=%d", ok, detail, elapsed)
        self._testing = False
        try:
            if ok:
                text = f"✓ 接続成功（{elapsed}秒）"
            elif detail:
                text = f"✗ 接続失敗（{elapsed}秒 / {detail}）— URLを確認するかスキップしてください"
            else:
                text = f"✗ 接続失敗（{elapsed}秒）— URLを確認するかスキップしてください"
            self._test_lbl.configure(text=text, text_color=SUCCESS if ok else DANGER)
            self._test_btn.configure(state="normal")
        except Exception as exc:
            logging.error("_on_test_done UI error: %s", exc)

    def _step1_next(self) -> None:
        self._config.backend_url = normalize_backend_url(self._url_entry.get())
        self._show_step2()

    # ──────────────────────────────
    # Step 2: ユーザー選択
    # ──────────────────────────────
    def _show_step2(self) -> None:
        self._testing = False
        self._fetch_in_progress = True
        self._clear()
        self._step_label("あなたのユーザーを選択してください", "2 / 3")

        self._user_var = ctk.StringVar(value="ユーザー一覧を取得中… (0秒)")
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

        ctk.CTkButton(
            btn_row, text="次へ →", width=100,
            fg_color=PRIMARY,
            command=self._step2_next,
        ).pack(side="right")

        ctk.CTkButton(
            btn_row, text="後で設定", width=90,
            fg_color="transparent", text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            command=self._step2_next,
        ).pack(side="right", padx=PAD_S)

        threading.Thread(target=self._fetch_users, daemon=True).start()
        self.after(1000, self._loading_tick)

    def _loading_tick(self) -> None:
        """メインスレッドで 1 秒ごとにローディング表示を更新する。"""
        if not self._fetch_in_progress:
            return
        try:
            current = self._user_var.get()
            m = re.search(r"\((\d+)秒\)", current)
            n = int(m.group(1)) + 1 if m else 1
            msg = f"ユーザー一覧を取得中… ({n}秒)" if n < 10 else f"サーバー起動中（最大60秒）… ({n}秒)"
            self._user_var.set(msg)
        except Exception as exc:
            logging.warning("_loading_tick error: %s", exc)
        self.after(1000, self._loading_tick)

    def _fetch_users(self) -> None:
        try:
            client = BackendClient(self._config.backend_url, UserInfo(user_id="", display_name=""))
            self._users = client.get_users_dev()
            names = [u.display_name for u in self._users]
            logging.debug("ユーザー取得成功: %d 名", len(names))
        except Exception as exc:
            logging.warning("ユーザー取得失敗: %s", exc)
            names = []
        self._fetch_in_progress = False
        # Tkinter を直接呼ばずキューに入れる
        self._q.put(("users_loaded", names))

    def _on_users_loaded(self, names: list[str]) -> None:
        logging.debug("_on_users_loaded: %d 名", len(names))
        try:
            if names:
                self._user_combo.configure(values=names, state="normal")
                current = next(
                    (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
                    names[0],
                )
                self._user_var.set(current)
            else:
                self._user_combo.configure(values=[], state="disabled")
                self._user_var.set("（取得できませんでした — 後で設定できます）")
        except Exception as exc:
            logging.error("_on_users_loaded UI error: %s", exc)

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
        self._fetch_in_progress = False
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
