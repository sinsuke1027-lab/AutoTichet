from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from widget.config import Config, save_config
from widget.services import autostart
from widget.ui_constants import WIN_SETTINGS


class SettingsWindow(ctk.CTkToplevel):
    """設定画面ウィンドウ。"""

    def __init__(
        self,
        parent: ctk.CTk,
        config: Config,
        on_save: Callable[[Config], None],
    ) -> None:
        super().__init__(parent)
        self.title("AutoTicket - 設定")
        self.geometry(f"{WIN_SETTINGS[0]}x{WIN_SETTINGS[1]}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._config = config
        self._on_save = on_save
        self._build_ui()

    def _build_ui(self) -> None:
        ctk.CTkLabel(
            self, text="設定", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(16, 8))

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=4)
        frame.columnconfigure(1, weight=1)

        row = [0]

        def _field(label: str, value: str, note: str = "") -> ctk.CTkEntry:
            ctk.CTkLabel(frame, text=label, width=150, anchor="w").grid(
                row=row[0], column=0, padx=(10, 4), pady=6, sticky="w"
            )
            entry = ctk.CTkEntry(frame)
            entry.insert(0, value)
            entry.grid(row=row[0], column=1, padx=(0, 10), pady=6, sticky="ew")
            row[0] += 1
            if note:
                ctk.CTkLabel(
                    frame, text=note, text_color=("gray40", "gray60"),
                    font=ctk.CTkFont(size=10), anchor="w",
                ).grid(
                    row=row[0], column=1, padx=(0, 10), pady=(0, 4), sticky="w"
                )
                row[0] += 1
            return entry

        self._hotkey_entry = _field(
            "ホットキー", self._config.hotkey,
            note="例: <ctrl>+<shift>+<space>  ※再起動後に反映"
        )
        self._ollama_model_entry = _field(
            "Ollama テキストモデル", self._config.ollama_model
        )
        self._ollama_vision_entry = _field(
            "Ollama ビジョンモデル", self._config.ollama_vision_model
        )
        self._backend_url_entry = _field(
            "バックエンド URL", self._config.backend_url
        )
        self._frontend_url_entry = _field(
            "フロントエンド URL", self._config.frontend_url
        )

        # 自動起動トグル
        autostart_row = ctk.CTkFrame(frame, fg_color="transparent")
        autostart_row.grid(row=row[0], column=0, columnspan=2, padx=(10, 10), pady=(6, 2), sticky="ew")
        row[0] += 1

        autostart_label = ctk.CTkLabel(autostart_row, text="Windowsログイン時に自動起動", width=150, anchor="w")
        autostart_label.pack(side="left")

        self._autostart_var = ctk.BooleanVar(value=autostart.is_enabled())
        autostart_switch = ctk.CTkSwitch(autostart_row, text="", variable=self._autostart_var, width=46)
        autostart_switch.pack(side="left", padx=(8, 0))

        if not autostart.is_frozen():
            autostart_switch.configure(state="disabled")
            ctk.CTkLabel(
                frame,
                text=".exeビルド後に有効",
                text_color=("gray40", "gray60"),
                font=ctk.CTkFont(size=10),
                anchor="w",
            ).grid(row=row[0], column=1, padx=(0, 10), pady=(0, 4), sticky="w")
            row[0] += 1

        self._note_lbl = ctk.CTkLabel(
            self, text="", text_color="green", font=ctk.CTkFont(size=12)
        )
        self._note_lbl.pack(pady=(4, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(8, 16))
        ctk.CTkButton(
            btn_row, text="キャンセル", width=110,
            fg_color="gray40", hover_color="gray30",
            command=self.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="保存", width=110, command=self._on_save_click
        ).pack(side="left", padx=8)

    def _on_save_click(self) -> None:
        self._config.hotkey = self._hotkey_entry.get().strip()
        self._config.ollama_model = self._ollama_model_entry.get().strip()
        self._config.ollama_vision_model = self._ollama_vision_entry.get().strip()
        self._config.backend_url = self._backend_url_entry.get().strip()
        self._config.frontend_url = self._frontend_url_entry.get().strip()
        save_config(self._config)
        try:
            if self._autostart_var.get():
                autostart.enable(autostart.get_current_exe_path())
            else:
                autostart.disable()
        except Exception as exc:
            import logging
            logging.warning("autostart toggle failed: %s", exc)
        self._on_save(self._config)
        self._note_lbl.configure(
            text="✅ 保存しました（一部設定は再起動後に反映）"
        )
        self.after(2500, self.destroy)
