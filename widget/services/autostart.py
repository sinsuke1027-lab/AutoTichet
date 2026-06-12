from __future__ import annotations
import sys
import winreg

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AutoTicket"


def is_frozen() -> bool:
    """PyInstaller でビルドされた .exe で実行中なら True。"""
    return getattr(sys, "frozen", False)


def is_enabled() -> bool:
    """自動起動がレジストリに登録されていれば True。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def enable(exe_path: str) -> None:
    """HKCU Run キーに exe パスを登録する。"""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, REG_KEY, access=winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)


def disable() -> None:
    """HKCU Run キーからエントリを削除する。未登録なら何もしない。"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY, access=winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass


def get_current_exe_path() -> str:
    return sys.executable
