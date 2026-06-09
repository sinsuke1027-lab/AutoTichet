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
from widget.services.screenshot_capture import ScreenshotCapture


def _make_tray_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(30, 120, 200))
    draw = ImageDraw.Draw(img)
    draw.text((10, 18), "AT", fill="white")
    return img


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
        self._screenshot: ScreenshotCapture | None = None

    def start(self) -> None:
        if not self.config.backend_url:
            print(
                "エラー: config.json の backend_url が未設定です。\n"
                "widget/config.json を編集して HuggingFace Spaces の URL を設定してください。"
            )
            sys.exit(1)

        # DEV_MODE 専用エンドポイントで認証なしユーザー一覧を取得
        dev_client = BackendClient(self.config.backend_url, UserInfo(user_id="", display_name=""))
        try:
            self.users = dev_client.get_users_dev()
        except Exception as exc:
            print(f"バックエンド接続エラー: {exc}")
            sys.exit(1)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._root = ctk.CTk()
        self._root.withdraw()

        def _report_callback_exception(exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
            msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            logging.error(msg)
            print(msg, file=sys.stderr)

        self._root.report_callback_exception = _report_callback_exception

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
            selected_user = UserInfo(user_id=self.config.selected_user_id, display_name=self.config.selected_user_id)
        self.backend = BackendClient(self.config.backend_url, selected_user)
        try:
            self.projects = self.backend.get_projects()
        except Exception as exc:
            print(f"プロジェクト一覧取得エラー: {exc}")
            self.projects = []
        self.ollama = OllamaClient(model=self.config.ollama_model)
        self._clipboard = ClipboardReader(
            get_clipboard=lambda: self._root.clipboard_get() if self._root else ""
        )
        self._screenshot = ScreenshotCapture()

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
        self._root.mainloop()

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
            screenshot=self._screenshot,
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
