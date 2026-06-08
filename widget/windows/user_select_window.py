from __future__ import annotations
import customtkinter as ctk
from widget.clients.backend_client import UserInfo
from widget.config import Config, save_config


class UserSelectWindow(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, config: Config, users: list[UserInfo]) -> None:
        super().__init__(parent)
        self.config = config
        self.users = users

        self.title("AutoTicket - ユーザー選択")
        self.geometry("380x180")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set()  # modal behavior

        ctk.CTkLabel(self, text="使用するユーザーを選択してください").pack(pady=(20, 8))

        names = [u.display_name for u in users]
        self._combo = ctk.CTkComboBox(self, values=names, width=320, state="readonly")
        if names:
            self._combo.set(names[0])
        self._combo.pack(pady=8)

        ctk.CTkButton(self, text="決定", command=self._on_select, width=160).pack(pady=12)

    def _on_select(self) -> None:
        name = self._combo.get()
        for u in self.users:
            if u.display_name == name:
                self.config.selected_user_id = u.user_id
                save_config(self.config)
                break
        self.destroy()
