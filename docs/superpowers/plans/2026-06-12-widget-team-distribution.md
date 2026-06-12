# ウィジェット チーム配布対応 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ウィジェットをチームへ `.exe` 配布できるレベルに仕上げる（初回ウィザード・接続状態管理・オフラインドラフトキュー・UIテーマ統一・自動起動）

**Architecture:** `ConnectionMonitor`（バックグラウンドスレッド）が接続状態を監視してトレイアイコン色を更新し、切断中の起票は `DraftQueue`（SQLite）に保存して復旧後に自動再送する。初回起動時のみ `FirstRunWizard` でURL・ユーザー・自動起動を設定させ、`first_run_complete` フラグで以降はスキップする。

**Tech Stack:** Python 3.11, customtkinter, httpx, pystray, PIL, SQLite (sqlite3), winreg, pynput

---

## ファイルマップ

| 操作 | ファイル |
|------|---------|
| 新規作成 | `widget/ui_constants.py` |
| 新規作成 | `widget/services/connection_monitor.py` |
| 新規作成 | `widget/services/draft_queue.py` |
| 新規作成 | `widget/services/autostart.py` |
| 新規作成 | `widget/windows/first_run_wizard.py` |
| 新規作成 | `widget/tests/test_connection_monitor.py` |
| 新規作成 | `widget/tests/test_draft_queue.py` |
| 新規作成 | `widget/tests/test_autostart.py` |
| 変更 | `widget/config.py` — `first_run_complete: bool = False` 追加 |
| 変更 | `widget/main.py` — ウィザード・ConnectionMonitor・DraftQueue 統合、トレイ色変更 |
| 変更 | `widget/windows/input_window.py` — オフライン時ドラフト保存・UIテーマ適用 |
| 変更 | `widget/windows/settings_window.py` — 自動起動トグル・UIテーマ適用 |

---

## Task 1: ui_constants.py — 定数モジュール

**Files:**
- Create: `widget/ui_constants.py`

定数のみのモジュールなのでテスト不要。

- [ ] **Step 1: ファイルを作成する**

```python
# widget/ui_constants.py
from __future__ import annotations

# カラーパレット
PRIMARY = "#2563EB"
SUCCESS = "#16A34A"
WARNING = "#D97706"
DANGER  = "#DC2626"

# フォント（Meiryo UI が日本語レイアウトに最適）
FONT_H1    = ("Meiryo UI", 16, "bold")
FONT_H2    = ("Meiryo UI", 13, "bold")
FONT_BODY  = ("Meiryo UI", 12)
FONT_SMALL = ("Meiryo UI", 10)

# 余白グリッド（8px基準）
PAD_S = 8
PAD_M = 16
PAD_L = 24

# ウィンドウサイズ (width, height)
WIN_INPUT    = (480, 520)
WIN_WIZARD   = (480, 360)
WIN_SETTINGS = (480, 520)
WIN_HISTORY  = (420, 380)
WIN_TODO     = (400, 480)
```

- [ ] **Step 2: インポートできることを確認する**

```bash
cd widget && python -c "from widget.ui_constants import PRIMARY, WIN_WIZARD; print(PRIMARY, WIN_WIZARD)"
```

期待出力: `#2563EB (480, 360)`

- [ ] **Step 3: コミットする**

```bash
git add widget/ui_constants.py
git commit -m "feat(widget): ui_constants.py — 色・フォント・余白・サイズ定数を追加"
```

---

## Task 2: config.py — first_run_complete フラグ追加

**Files:**
- Modify: `widget/config.py`
- Test: `widget/tests/test_config.py`

- [ ] **Step 1: 既存テストを実行して全 PASS を確認する**

```bash
pytest widget/tests/test_config.py -v
```

期待: 3 passed

- [ ] **Step 2: 新規テストを追加する**

`widget/tests/test_config.py` の末尾に追加：

```python
def test_first_run_complete_defaults_to_false(tmp_path, monkeypatch):
    monkeypatch.setattr("widget.config.CONFIG_PATH", tmp_path / "config.json")
    cfg = load_config()
    assert cfg.first_run_complete is False


def test_first_run_complete_persists(tmp_path, monkeypatch):
    monkeypatch.setattr("widget.config.CONFIG_PATH", tmp_path / "config.json")
    cfg = load_config()
    cfg.first_run_complete = True
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.first_run_complete is True
```

- [ ] **Step 3: テストが失敗することを確認する**

```bash
pytest widget/tests/test_config.py::test_first_run_complete_defaults_to_false -v
```

期待: FAIL（フィールドがまだ存在しないため）

- [ ] **Step 4: config.py に first_run_complete を追加する**

`widget/config.py` の `Config` dataclass を以下に変更する：

```python
@dataclass
class Config:
    backend_url: str = ""
    frontend_url: str = ""
    selected_user_id: str = ""
    hotkey: str = "<ctrl>+<shift>+<space>"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_vision_model: str = "gemma4:e4b"
    vision_provider: str = "local"
    google_api_key: str = ""
    first_run_complete: bool = False
```

- [ ] **Step 5: テストが全 PASS することを確認する**

```bash
pytest widget/tests/test_config.py -v
```

期待: 5 passed

- [ ] **Step 6: コミットする**

```bash
git add widget/config.py widget/tests/test_config.py
git commit -m "feat(widget): Config に first_run_complete フラグを追加"
```

---

## Task 3: connection_monitor.py — 接続状態管理

**Files:**
- Create: `widget/services/connection_monitor.py`
- Create: `widget/tests/test_connection_monitor.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# widget/tests/test_connection_monitor.py
from __future__ import annotations
from unittest.mock import MagicMock, patch
from widget.services.connection_monitor import ConnectionMonitor, ConnectionState


def _make_monitor(callback=None):
    return ConnectionMonitor(
        url="http://localhost:8000",
        on_state_change=callback or (lambda s: None),
    )


def test_check_returns_connected_on_fast_200():
    monitor = _make_monitor()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("widget.services.connection_monitor.httpx.get", return_value=mock_resp):
        with patch("widget.services.connection_monitor.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.5]  # 0.5秒 < 2秒閾値
            result = monitor._check()
    assert result == ConnectionState.CONNECTED


def test_check_returns_degraded_on_slow_200():
    monitor = _make_monitor()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("widget.services.connection_monitor.httpx.get", return_value=mock_resp):
        with patch("widget.services.connection_monitor.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 3.0]  # 3秒 > 2秒閾値
            result = monitor._check()
    assert result == ConnectionState.DEGRADED


def test_check_returns_disconnected_on_exception():
    monitor = _make_monitor()
    with patch(
        "widget.services.connection_monitor.httpx.get",
        side_effect=Exception("connection refused"),
    ):
        result = monitor._check()
    assert result == ConnectionState.DISCONNECTED


def test_callback_fires_on_state_change():
    states: list[ConnectionState] = []
    monitor = _make_monitor(callback=states.append)
    monitor._state = ConnectionState.CONNECTED

    with patch(
        "widget.services.connection_monitor.httpx.get",
        side_effect=Exception("down"),
    ):
        monitor._check_and_notify()

    assert states == [ConnectionState.DISCONNECTED]


def test_callback_not_fired_when_state_unchanged():
    states: list[ConnectionState] = []
    monitor = _make_monitor(callback=states.append)
    monitor._state = ConnectionState.DISCONNECTED  # 既に DISCONNECTED

    with patch(
        "widget.services.connection_monitor.httpx.get",
        side_effect=Exception("still down"),
    ):
        monitor._check_and_notify()

    assert states == []  # 変化なし → コールバックなし


def test_is_connected_true_for_connected_and_degraded():
    monitor = _make_monitor()
    monitor._state = ConnectionState.CONNECTED
    assert monitor.is_connected() is True
    monitor._state = ConnectionState.DEGRADED
    assert monitor.is_connected() is True
    monitor._state = ConnectionState.DISCONNECTED
    assert monitor.is_connected() is False
```

- [ ] **Step 2: テストが失敗することを確認する（モジュール未存在）**

```bash
pytest widget/tests/test_connection_monitor.py -v
```

期待: ERROR（import できないため）

- [ ] **Step 3: connection_monitor.py を作成する**

```python
# widget/services/connection_monitor.py
from __future__ import annotations
import threading
import time
from enum import Enum
from typing import Callable

import httpx


class ConnectionState(Enum):
    CONNECTED    = "connected"
    DEGRADED     = "degraded"
    DISCONNECTED = "disconnected"


class ConnectionMonitor:
    """バックグラウンドスレッドでバックエンドの接続状態を定期チェックする。"""

    def __init__(
        self,
        url: str,
        on_state_change: Callable[[ConnectionState], None],
        check_interval_connected: float = 30.0,
        check_interval_disconnected: float = 10.0,
        degraded_threshold: float = 2.0,
    ) -> None:
        self._url = url
        self._on_state_change = on_state_change
        self._interval_connected = check_interval_connected
        self._interval_disconnected = check_interval_disconnected
        self._degraded_threshold = degraded_threshold
        self._state = ConnectionState.DISCONNECTED
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def state(self) -> ConnectionState:
        return self._state

    def is_connected(self) -> bool:
        return self._state in (ConnectionState.CONNECTED, ConnectionState.DEGRADED)

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _check(self) -> ConnectionState:
        try:
            start = time.monotonic()
            resp = httpx.get(f"{self._url}/health", timeout=5.0)
            elapsed = time.monotonic() - start
            if resp.status_code == 200:
                if elapsed > self._degraded_threshold:
                    return ConnectionState.DEGRADED
                return ConnectionState.CONNECTED
        except Exception:
            pass
        return ConnectionState.DISCONNECTED

    def _check_and_notify(self) -> None:
        new_state = self._check()
        if new_state != self._state:
            self._state = new_state
            self._on_state_change(new_state)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check_and_notify()
            interval = (
                self._interval_connected
                if self._state == ConnectionState.CONNECTED
                else self._interval_disconnected
            )
            self._stop_event.wait(interval)
```

- [ ] **Step 4: テストが全 PASS することを確認する**

```bash
pytest widget/tests/test_connection_monitor.py -v
```

期待: 6 passed

- [ ] **Step 5: コミットする**

```bash
git add widget/services/connection_monitor.py widget/tests/test_connection_monitor.py
git commit -m "feat(widget): ConnectionMonitor — 接続状態定期チェックと状態変化コールバックを追加"
```

---

## Task 4: draft_queue.py — オフラインドラフトキュー

**Files:**
- Create: `widget/services/draft_queue.py`
- Create: `widget/tests/test_draft_queue.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# widget/tests/test_draft_queue.py
from __future__ import annotations
from pathlib import Path
import pytest
from widget.services.draft_queue import DraftQueue, DraftEntry


@pytest.fixture
def queue(tmp_path: Path) -> DraftQueue:
    return DraftQueue(db_path=tmp_path / "drafts.db")


def test_add_and_get_pending(queue: DraftQueue):
    payload = {"title": "テストタスク", "priority": "medium"}
    draft_id = queue.add(payload)
    pending = queue.get_pending()
    assert len(pending) == 1
    assert pending[0].id == draft_id
    assert pending[0].payload == payload
    assert pending[0].retry_count == 0


def test_remove_deletes_draft(queue: DraftQueue):
    draft_id = queue.add({"title": "削除テスト"})
    queue.remove(draft_id)
    assert queue.get_pending() == []


def test_increment_retry_updates_count_and_error(queue: DraftQueue):
    draft_id = queue.add({"title": "リトライテスト"})
    queue.increment_retry(draft_id, "Connection timeout")
    pending = queue.get_pending()
    assert pending[0].retry_count == 1
    assert pending[0].last_error == "Connection timeout"


def test_get_pending_empty_returns_empty_list(queue: DraftQueue):
    assert queue.get_pending() == []


def test_created_at_is_iso_format(queue: DraftQueue):
    queue.add({"title": "ISO確認"})
    entry = queue.get_pending()[0]
    # ISO 8601 形式であれば + または Z が含まれる
    assert "T" in entry.created_at
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
pytest widget/tests/test_draft_queue.py -v
```

期待: ERROR（import できないため）

- [ ] **Step 3: draft_queue.py を作成する**

```python
# widget/services/draft_queue.py
from __future__ import annotations
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "drafts.db"


@dataclass
class DraftEntry:
    id: int
    payload: dict
    created_at: str
    retry_count: int
    last_error: str | None


class DraftQueue:
    """オフライン時のタスクドラフトを SQLite で管理する。"""

    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload     TEXT    NOT NULL,
                    created_at  TEXT    NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    last_error  TEXT
                )
            """)
            conn.commit()

    def add(self, payload: dict) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO drafts (payload, created_at) VALUES (?, ?)",
                (json.dumps(payload, ensure_ascii=False), now),
            )
            conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def get_pending(self) -> list[DraftEntry]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT id, payload, created_at, retry_count, last_error "
                "FROM drafts ORDER BY id ASC"
            ).fetchall()
        return [
            DraftEntry(
                id=r[0],
                payload=json.loads(r[1]),
                created_at=r[2],
                retry_count=r[3],
                last_error=r[4],
            )
            for r in rows
        ]

    def remove(self, draft_id: int) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.commit()

    def increment_retry(self, draft_id: int, error: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE drafts SET retry_count = retry_count + 1, last_error = ? "
                "WHERE id = ?",
                (error, draft_id),
            )
            conn.commit()
```

- [ ] **Step 4: テストが全 PASS することを確認する**

```bash
pytest widget/tests/test_draft_queue.py -v
```

期待: 5 passed

- [ ] **Step 5: コミットする**

```bash
git add widget/services/draft_queue.py widget/tests/test_draft_queue.py
git commit -m "feat(widget): DraftQueue — オフライン時ドラフト保存・リトライ管理を追加"
```

---

## Task 5: autostart.py — Windows 自動起動

**Files:**
- Create: `widget/services/autostart.py`
- Create: `widget/tests/test_autostart.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# widget/tests/test_autostart.py
from __future__ import annotations
from unittest.mock import MagicMock, patch, call
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
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
pytest widget/tests/test_autostart.py -v
```

期待: ERROR（import できないため）

- [ ] **Step 3: autostart.py を作成する**

```python
# widget/services/autostart.py
from __future__ import annotations
import sys
import winreg

REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
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
```

- [ ] **Step 4: テストが全 PASS することを確認する**

```bash
pytest widget/tests/test_autostart.py -v
```

期待: 7 passed

- [ ] **Step 5: コミットする**

```bash
git add widget/services/autostart.py widget/tests/test_autostart.py
git commit -m "feat(widget): autostart.py — Windows レジストリへの自動起動登録/解除を追加"
```

---

## Task 6: first_run_wizard.py — 初回起動ウィザード

**Files:**
- Create: `widget/windows/first_run_wizard.py`

GUI コンポーネントのため単体テストは省略し、Task 7 の手動確認でカバーする。
config保存は Task 2 のテスト済みコードを呼び出すだけ。

- [ ] **Step 1: first_run_wizard.py を作成する**

```python
# widget/windows/first_run_wizard.py
from __future__ import annotations
import sys
import threading
from typing import Callable

import customtkinter as ctk
import httpx

from widget.clients.backend_client import BackendClient, UserInfo
from widget.config import Config, save_config
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
        self._config.backend_url = self._url_entry.get().strip()
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
```

- [ ] **Step 2: コミットする**

```bash
git add widget/windows/first_run_wizard.py
git commit -m "feat(widget): FirstRunWizard — 3ステップ初回セットアップウィザードを追加"
```

---

## Task 7: main.py — ウィザード・ConnectionMonitor・DraftQueue を統合

**Files:**
- Modify: `widget/main.py`

手動テストで確認する（GUI 統合のため）。

- [ ] **Step 1: インポートを追加する**

`widget/main.py` の既存 import ブロック末尾に追加：

```python
from widget.services.connection_monitor import ConnectionMonitor, ConnectionState
from widget.services.draft_queue import DraftQueue
from widget.windows.first_run_wizard import FirstRunWizard
```

- [ ] **Step 2: _make_tray_image を ConnectionState 対応に変更する**

既存の `_make_tray_image()` 関数を以下に置き換える：

```python
_STATE_COLORS: dict[ConnectionState, tuple[int, int, int]] = {
    ConnectionState.CONNECTED:    (22, 163, 74),   # 緑
    ConnectionState.DEGRADED:     (217, 119, 6),   # 黄
    ConnectionState.DISCONNECTED: (220, 38, 38),   # 赤
}


def _make_tray_image(state: ConnectionState = ConnectionState.DISCONNECTED) -> Image.Image:
    color = _STATE_COLORS[state]
    img = Image.new("RGB", (64, 64), color=color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 18), "AT", fill="white")
    return img
```

- [ ] **Step 3: AppController に connection_monitor・draft_queue・tray_icon フィールドを追加する**

`AppController.__init__` に以下を追加する（既存フィールドの末尾）：

```python
self._connection_monitor: ConnectionMonitor | None = None
self._draft_queue: DraftQueue = DraftQueue()
self._tray_icon: pystray.Icon | None = None
```

- [ ] **Step 4: start() に初回ウィザードチェックを追加する**

`AppController.start()` の `if not self.config.backend_url:` より前に挿入する：

```python
# 初回起動チェック
if not self.config.first_run_complete:
    wizard = FirstRunWizard(self._root, self.config)
    self._root.wait_window(wizard)
    if not self.config.first_run_complete:
        # ウィザードが × で閉じられた
        sys.exit(0)
    self.config = load_config()
```

- [ ] **Step 5: start() の backend_url チェックを残しつつエラーメッセージを改善する**

既存の `if not self.config.backend_url:` ブロックを以下に変更する：

```python
if not self.config.backend_url:
    print(
        "エラー: バックエンド URL が未設定です。\n"
        "ウィジェットを再起動して初回ウィザードで URL を設定してください。"
    )
    sys.exit(1)
```

- [ ] **Step 6: _setup_after_connect() に ConnectionMonitor 起動を追加する**

`_setup_after_connect()` の末尾（`print(f"AutoTicket 起動完了…")` の前）に追加：

```python
self._connection_monitor = ConnectionMonitor(
    url=self.config.backend_url,
    on_state_change=self._on_connection_state_changed,
)
self._connection_monitor.start()
```

- [ ] **Step 7: pystray.Icon を self._tray_icon に保存する**

`_setup_after_connect()` 内の `icon = pystray.Icon(...)` を以下に変更する：

```python
self._tray_icon = pystray.Icon(
    "AutoTicket",
    _make_tray_image(ConnectionState.CONNECTED),
    "AutoTicket — 接続中",
    menu=pystray.Menu(
        pystray.MenuItem(
            "タスク入力",
            lambda _i, _it: self._root.after(0, self._show_window),
        ),
        pystray.MenuItem(
            "今日のタスク",
            lambda _i, _it: self._root.after(0, self._show_todo_window),
        ),
        pystray.MenuItem(
            "起票履歴",
            lambda _i, _it: self._root.after(0, self._show_history_window),
        ),
        pystray.MenuItem(
            "設定",
            lambda _i, _it: self._root.after(0, self._show_settings_window),
        ),
        pystray.MenuItem(
            "終了",
            lambda _i, _it: self._root.after(0, self._quit),
        ),
    ),
)
threading.Thread(target=self._tray_icon.run, daemon=True).start()
```

- [ ] **Step 8: _on_connection_state_changed と _retry_drafts を追加する**

`AppController` に新規メソッドを2つ追加する（`_quit` の直前）：

```python
def _on_connection_state_changed(self, state: ConnectionState) -> None:
    if self._tray_icon is None:
        return
    tooltip_map = {
        ConnectionState.CONNECTED:    "AutoTicket — 接続中",
        ConnectionState.DEGRADED:     "AutoTicket — 応答遅延",
        ConnectionState.DISCONNECTED: "AutoTicket — バックエンド未接続",
    }
    self._tray_icon.icon  = _make_tray_image(state)
    self._tray_icon.title = tooltip_map[state]
    # 接続復旧時にドラフトを自動再送
    if state == ConnectionState.CONNECTED and self.backend is not None:
        threading.Thread(target=self._retry_drafts, daemon=True).start()

def _retry_drafts(self) -> None:
    pending = self._draft_queue.get_pending()
    if not pending:
        return
    tasks_url = (
        (self.config.frontend_url.rstrip("/") + "/tasks")
        if self.config.frontend_url
        else ""
    )
    for draft in pending:
        try:
            self.backend.create_task(draft.payload)  # type: ignore[union-attr]
            self._draft_queue.remove(draft.id)
            title = draft.payload.get("title", "")
            if self._root:
                self._root.after(0, lambda t=title: notify_success(t, tasks_url))
        except Exception as exc:
            self._draft_queue.increment_retry(draft.id, str(exc))
            if draft.retry_count + 1 >= 3 and self._root:
                self._root.after(
                    0,
                    lambda: notify_today(
                        ["下書き送信に3回失敗しました。起票履歴から手動で再送してください。"],
                        tasks_url,
                    ),
                )
```

- [ ] **Step 9: _show_window() で draft_queue を InputWindow に渡す**

`_show_window()` の `InputWindow(...)` 呼び出しを以下に変更する：

```python
win = InputWindow(
    self._root,
    self.config,
    self.ollama,
    self.backend,
    self.users,
    self.projects,
    clipboard=self._clipboard,
    vision=self._vision,
    connection_monitor=self._connection_monitor,
    draft_queue=self._draft_queue,
)
```

- [ ] **Step 10: 手動確認 — ウィジェットを起動する**

```bash
python -m widget.main
```

確認項目：
- [ ] 初回起動（`first_run_complete: false`）でウィザードが表示される
- [ ] ウィザード完了後、トレイに緑アイコンで常駐する
- [ ] バックエンドを停止するとトレイアイコンが赤に変わる（約10秒後）

- [ ] **Step 11: コミットする**

```bash
git add widget/main.py
git commit -m "feat(widget): main.py — ウィザード・ConnectionMonitor・DraftQueue 統合、トレイアイコン色対応"
```

---

## Task 8: input_window.py — オフライン時ドラフト保存 + UIテーマ適用

**Files:**
- Modify: `widget/windows/input_window.py`

- [ ] **Step 1: インポートを追加する**

`input_window.py` の既存 import ブロック末尾に追加：

```python
from widget.services.connection_monitor import ConnectionMonitor
from widget.services.draft_queue import DraftQueue
from widget.ui_constants import PRIMARY, DANGER, WARNING, FONT_H2, FONT_BODY, PAD_S, PAD_M, WIN_INPUT
```

- [ ] **Step 2: __init__ に connection_monitor と draft_queue パラメータを追加する**

`InputWindow.__init__` のシグネチャを変更する：

```python
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
    # 以降は変更なし
```

- [ ] **Step 3: 送信処理にオフライン分岐を追加する**

InputWindow 内の送信ボタン押下時のメソッド（`_on_submit` または `_submit`）を探して、送信前に以下の切断チェックを追加する。

既存の送信処理の先頭（payload を構築した後）に追加：

```python
# バックエンド切断チェック
if (
    self._connection_monitor is not None
    and not self._connection_monitor.is_connected()
    and self._draft_queue is not None
):
    self._show_offline_dialog(payload)
    return
```

- [ ] **Step 4: _show_offline_dialog メソッドを追加する**

InputWindow クラスに追加：

```python
def _show_offline_dialog(self, payload: dict) -> None:
    dialog = ctk.CTkToplevel(self)
    dialog.title("接続エラー")
    dialog.geometry("400x160")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.grab_set()

    ctk.CTkLabel(
        dialog,
        text="⚠️  バックエンドに接続できません",
        font=ctk.CTkFont(*FONT_H2),
    ).pack(pady=(PAD_M, PAD_S))
    ctk.CTkLabel(
        dialog,
        text="下書き保存すると、復旧後に自動送信されます。",
        font=ctk.CTkFont(*FONT_BODY),
        text_color=("gray40", "gray60"),
    ).pack(pady=(0, PAD_M))

    btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_row.pack()

    def _save_draft() -> None:
        assert self._draft_queue is not None
        self._draft_queue.add(payload)
        dialog.destroy()
        self._show_inline_message("📝 下書きに保存しました")
        self._reset_form()

    ctk.CTkButton(
        btn_row, text="下書き保存", width=110,
        fg_color=PRIMARY,
        command=_save_draft,
    ).pack(side="left", padx=PAD_S)

    ctk.CTkButton(
        btn_row, text="閉じる", width=80,
        fg_color="gray50", hover_color="gray40",
        command=dialog.destroy,
    ).pack(side="left", padx=PAD_S)
```

- [ ] **Step 5: ウィンドウサイズを WIN_INPUT 定数に変更する**

`__init__` 内の `self.geometry("480x250")` を以下に変更する：

```python
self.geometry(f"{WIN_INPUT[0]}x{WIN_INPUT[1]}")
```

- [ ] **Step 6: 手動確認**

バックエンドを停止した状態でウィジェットから起票を試みる。
- [ ] オフラインダイアログが表示される
- [ ] 「下書き保存」を押すとフォームがリセットされる
- [ ] バックエンドを起動すると自動再送される（Task 7 の ConnectionMonitor 経由）

- [ ] **Step 7: コミットする**

```bash
git add widget/windows/input_window.py
git commit -m "feat(widget): InputWindow — オフライン時ドラフト保存ダイアログと WIN_INPUT 定数を適用"
```

---

## Task 9: settings_window.py — 自動起動トグル + UIテーマ適用

**Files:**
- Modify: `widget/windows/settings_window.py`

- [ ] **Step 1: インポートを追加する**

`settings_window.py` の既存 import ブロック末尾に追加：

```python
from widget.services import autostart
from widget.ui_constants import PRIMARY, FONT_H1, FONT_BODY, FONT_SMALL, PAD_S, PAD_M, PAD_L, WIN_SETTINGS
```

- [ ] **Step 2: ウィンドウサイズを WIN_SETTINGS 定数に変更する**

`__init__` 内の `self.geometry("480x420")` を以下に変更する：

```python
self.geometry(f"{WIN_SETTINGS[0]}x{WIN_SETTINGS[1]}")
```

- [ ] **Step 3: _build_ui の末尾に自動起動トグルを追加する**

`_build_ui()` の `self._note_lbl = ctk.CTkLabel(...)` の前に追加：

```python
# 自動起動トグル
ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(fill="x", padx=PAD_L, pady=(PAD_S, 0))

autostart_row = ctk.CTkFrame(self, fg_color="transparent")
autostart_row.pack(fill="x", padx=PAD_L, pady=(PAD_S, 0))

self._autostart_var = ctk.BooleanVar(value=autostart.is_enabled())
autostart_switch = ctk.CTkSwitch(
    autostart_row,
    text="Windowsログイン時に自動起動",
    variable=self._autostart_var,
    font=ctk.CTkFont(*FONT_BODY),
)
autostart_switch.pack(side="left")

if not autostart.is_frozen():
    autostart_switch.configure(state="disabled")
    ctk.CTkLabel(
        autostart_row,
        text=" (.exe ビルド後に有効)",
        font=ctk.CTkFont(*FONT_SMALL),
        text_color=("gray40", "gray60"),
    ).pack(side="left")
```

- [ ] **Step 4: _on_save に自動起動の保存処理を追加する**

既存の `_on_save()` メソッド（またはそれに相当する保存ボタンのコールバック）の末尾に追加する。`settings_window.py` の末尾付近にある保存処理を探し、`save_config(new_cfg)` の直後に追加：

```python
# 自動起動の更新
if autostart.is_frozen():
    if self._autostart_var.get():
        autostart.enable(autostart.get_current_exe_path())
    else:
        autostart.disable()
```

- [ ] **Step 5: 手動確認**

設定画面を開く。
- [ ] 設定画面の末尾に「Windowsログイン時に自動起動」トグルが表示される
- [ ] `.py` 実行中はトグルがグレーアウトされる
- [ ] 保存ボタンを押すとレジストリが更新される（`autostart.is_enabled()` で確認）

- [ ] **Step 6: コミットする**

```bash
git add widget/windows/settings_window.py
git commit -m "feat(widget): SettingsWindow — 自動起動トグルと WIN_SETTINGS 定数を適用"
```

---

## Task 10: 全体テスト実行・進捗ドキュメント更新

- [ ] **Step 1: 全テストを実行する**

```bash
pytest widget/tests/ -v
```

期待: 65 passed 以上（既存 50 + 新規 ~15）

- [ ] **Step 2: progress.md を更新する**

`docs/progress.md` の先頭「現在のフェーズ」と「完了した作業」を更新：

```markdown
## 現在のフェーズ
**Phase: ウィジェット チーム配布対応 完成 → PyInstaller .exe ビルド**
ステータス: 初回ウィザード・ConnectionMonitor・DraftQueue・UIテーマ・自動起動の6機能実装完了（2026-06-xx）。次は PyInstaller でビルドしてチームへ配布。
```

- [ ] **Step 3: コミットする**

```bash
git add docs/progress.md
git commit -m "docs: progress.md を2026-06-xx時点に更新（ウィジェット チーム配布対応 完成）"
```
