from __future__ import annotations
from unittest.mock import MagicMock, patch
import widget.services.autostart as autostart


def test_is_enabled_returns_true_when_key_exists():
    mock_key = MagicMock()
    with patch("widget.services.autostart.winreg.OpenKey", return_value=mock_key):
        with patch("widget.services.autostart.winreg.QueryValueEx"):
            assert autostart.is_enabled() is True


def test_is_enabled_returns_false_when_key_missing():
    with patch(
        "widget.services.autostart.winreg.OpenKey",
        side_effect=FileNotFoundError,
    ):
        assert autostart.is_enabled() is False


def test_enable_writes_registry_value():
    mock_key = MagicMock()
    mock_key.__enter__ = lambda s: mock_key
    mock_key.__exit__ = MagicMock(return_value=False)
    with patch("widget.services.autostart.winreg.OpenKey", return_value=mock_key):
        with patch("widget.services.autostart.winreg.SetValueEx") as mock_set:
            autostart.enable("C:\\AutoTicket.exe")
    mock_set.assert_called_once_with(
        mock_key, autostart.APP_NAME, 0, autostart.winreg.REG_SZ, "C:\\AutoTicket.exe"
    )


def test_disable_deletes_registry_value():
    mock_key = MagicMock()
    mock_key.__enter__ = lambda s: mock_key
    mock_key.__exit__ = MagicMock(return_value=False)
    with patch("widget.services.autostart.winreg.OpenKey", return_value=mock_key):
        with patch("widget.services.autostart.winreg.DeleteValue") as mock_del:
            autostart.disable()
    mock_del.assert_called_once_with(mock_key, autostart.APP_NAME)


def test_disable_ignores_missing_key():
    with patch(
        "widget.services.autostart.winreg.OpenKey",
        side_effect=FileNotFoundError,
    ):
        autostart.disable()  # 例外が出なければ OK


def test_is_frozen_false_in_dev():
    with patch("widget.services.autostart.sys") as mock_sys:
        del mock_sys.frozen  # frozen 属性がない = 開発環境
        assert autostart.is_frozen() is False


def test_is_frozen_true_in_exe():
    with patch("widget.services.autostart.sys") as mock_sys:
        mock_sys.frozen = True
        assert autostart.is_frozen() is True
