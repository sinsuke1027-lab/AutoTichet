from __future__ import annotations
import logging
import sys
import threading
import traceback
import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray
from pynput import keyboard

import pathlib
_LOG_PATH = pathlib.Path(__file__).parent / "widget_error.log"
logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s\n%(message)s\n",
    encoding="utf-8",
)
logging.debug("widget started")

from widget.config import load_config, save_config, Config
from widget.clients.backend_client import BackendClient, UserInfo, ProjectInfo
from widget.clients.ollama_client import OllamaClient
from widget.windows.user_select_window import UserSelectWindow
from widget.windows.input_window import InputWindow
from widget.services.clipboard_reader import ClipboardReader
from widget.services.vision_parser import VisionParser

_MAX_CONNECT_ATTEMPTS = 5
_RETRY_INTERVAL_MS = 15_000  # 15秒ごとに再試行（HF Spaces の起動待ち）


def _make_tray_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(30, 120, 200))
    draw = ImageDraw.Draw(img)
    draw.text((10, 18), "AT", fill="white")
    return img


class _ConnectingWindow(ctk.CTkToplevel):
    """バックエンド接続中に表示する小さなステータスウィンドウ。"""

    def __init__(self, parent: ctk.CTk) -> None:
        super().__init__(parent)
        self.title("AutoTicket")
        self.geometry("340x90")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13))
        self._lbl.pack(expand=True)

    def set_message(self, msg: str) -> None:
        self._lbl.configure(text=msg)


class AppController:
    def __init__(self) -> None:
        self.config = load_config()
        self.users: list[UserInfo] = []
        self.projects: list[ProjectInfo] = []
        self.backend: BackendClient | None = None
        self.ollama: OllamaClient | None = None
        self._root: ctk.CTk | None = None
        self._window_open = False
        self._clipboard: ClipboardReader | None = None
        self._vision: VisionParser | None = None
        self._conn_win: _ConnectingWindow | None = None

    def start(self) -> None:
        if not self.config.backend_url:
            print(
                "エラー: config.json の backend_url が未設定です。\n"
                "widget/config.json を編集して HuggingFace Spaces の URL を設定してください。"
            )
            sys.exit(1)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self._root = ctk.CTk()
        self._root.withdraw()

        def _report_callback_exception(exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
            msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            logging.error(msg)
            print(msg, file=sys.stderr)

        self._root.report_callback_exception = _report_callback_exception

        self._conn_win = _ConnectingWindow(self._root)
        self._try_connect(attempt=1)
        self._root.mainloop()

    # ──────────────────────────────
    # バックエンド接続（リトライ付き）
    # ──────────────────────────────
    def _try_connect(self, attempt: int) -> None:
        assert self._conn_win is not None
        self._conn_win.set_message(
            f"バックエンドに接続中… ({attempt}/{_MAX_CONNECT_ATTEMPTS})\n"
            "HuggingFace Spaces の起動を待っています。"
        )
        dev_client = BackendClient(self.config.backend_url, UserInfo(user_id="", display_name=""))

        def _run() -> None:
            try:
                users = dev_client.get_users_dev()
                assert self._root is not None
                self._root.after(0, lambda u=users: self._on_connect_success(u))
            except Exception as exc:
                logging.warning("接続試行 %d 失敗: %s", attempt, exc)
                assert self._root is not None
                if attempt < _MAX_CONNECT_ATTEMPTS:
                    self._root.after(
                        _RETRY_INTERVAL_MS,
                        lambda: self._try_connect(attempt + 1),
                    )
                else:
                    self._root.after(0, lambda e=str(exc): self._on_connect_failed(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_connect_success(self, users: list[UserInfo]) -> None:
        self.users = users
        if self._conn_win:
            self._conn_win.destroy()
            self._conn_win = None
        self._setup_after_connect()

    def _on_connect_failed(self, error: str) -> None:
        if self._conn_win:
            self._conn_win.destroy()
            self._conn_win = None
        self._show_error_dialog(error)

    def _show_error_dialog(self, error: str) -> None:
        assert self._root is not None
        dialog = ctk.CTkToplevel(self._root)
        dialog.title("接続エラー")
        dialog.geometry("380x160")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(
            dialog,
            text="バックエンドに接続できませんでした。",
            font=ctk.CTkFont(weight="bold"),
        ).pack(pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text="HuggingFace Spaces がスリープ中の可能性があります。",
            text_color="gray",
        ).pack(pady=(0, 12))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def _retry() -> None:
            dialog.destroy()
            self._conn_win = _ConnectingWindow(self._root)
            self._try_connect(attempt=1)

        ctk.CTkButton(btn_row, text="再試行", width=120, command=_retry).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="終了", width=100,
            fg_color="gray40", hover_color="gray30",
            command=self._quit,
        ).pack(side="left", padx=8)

    # ──────────────────────────────
    # 接続後の初期化
    # ──────────────────────────────
    def _setup_after_connect(self) -> None:
        assert self._root is not None

        if not self.config.selected_user_id:
            win = UserSelectWindow(self._root, self.config, self.users)
            self._root.wait_window(win)
            if not self.config.selected_user_id:
                print("ユーザーが選択されませんでした。終了します。")
                sys.exit(0)

        selected_user = next(
            (u for u in self.users if u.user_id == self.config.selected_user_id), None
        )
        if selected_user is None:
            selected_user = UserInfo(
                user_id=self.config.selected_user_id,
                display_name=self.config.selected_user_id,
            )
        self.backend = BackendClient(self.config.backend_url, selected_user)
        try:
            self.projects = self.backend.get_projects()
        except Exception as exc:
            logging.warning("プロジェクト一覧取得エラー: %s", exc)
            self.projects = []

        self.ollama = OllamaClient(
            model=self.config.ollama_model,
            vision_model=self.config.ollama_vision_model,
        )
        self._clipboard = ClipboardReader(
            get_clipboard=lambda: self._root.clipboard_get() if self._root else ""
        )
        self._vision = VisionParser(config=self.config, ollama=self.ollama)

        threading.Thread(target=self._start_hotkey_listener, daemon=True).start()

        icon = pystray.Icon(
            "AutoTicket",
            _make_tray_image(),
            "AutoTicket",
            menu=pystray.Menu(
                pystray.MenuItem("タスク入力", lambda _i, _it: self._root.after(0, self._show_window)),
                pystray.MenuItem("終了", lambda _i, _it: self._root.after(0, self._quit)),
            ),
        )
        threading.Thread(target=icon.run, daemon=True).start()

        print(f"AutoTicket 起動完了。{self.config.hotkey} でタスク入力ウィンドウを開けます。")

    # ──────────────────────────────
    # ホットキー・ウィンドウ管理
    # ──────────────────────────────
    def _start_hotkey_listener(self) -> None:
        def on_activate() -> None:
            if self._root:
                self._root.after(0, self._show_window)

        with keyboard.GlobalHotKeys({self.config.hotkey: on_activate}) as h:
            h.join()

    def _show_window(self) -> None:
        if self._window_open:
            return
        self._window_open = True
        win = InputWindow(
            self._root,
            self.config,
            self.ollama,
            self.backend,
            self.users,
            self.projects,
            clipboard=self._clipboard,
            vision=self._vision,
        )
        win.protocol("WM_DELETE_WINDOW", lambda: self._on_window_close(win))

    def _on_window_close(self, win: InputWindow) -> None:
        self._window_open = False
        win.destroy()

    def _quit(self) -> None:
        if self._root:
            self._root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    AppController().start()
