# ウィジェット機能拡充 Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** デスクトップウィジェットに「起票成功通知・起票履歴・設定画面・テンプレート・D&D・音声入力」の6機能を追加し、日常タスク管理の入口として完成させる。

**Architecture:** 既存の AppController（main.py）とトレイメニューに新ウィンドウへのエントリーポイントを追加する。InputWindow は既存フローを壊さず機能を積み重ねる。履歴は SQLite（sqlite3 同期）で永続化し、GUI スレッドから threading でバックグラウンド実行する。

**Tech Stack:** customtkinter, winotify（既存）, sqlite3（標準ライブラリ）, tkinterdnd2（D&D）, sounddevice + scipy + faster-whisper（音声入力）

---

## ファイル構成

| ファイル | 種別 | 担当機能 |
|---------|------|---------|
| `widget/services/toast_notifier.py` | 修正 | `notify_success()` 追加 |
| `widget/services/history_store.py` | 新規 | 起票履歴 SQLite CRUD |
| `widget/services/audio_recorder.py` | 新規 | sounddevice 録音 + faster-whisper 文字起こし |
| `widget/windows/history_window.py` | 新規 | 起票履歴一覧ウィンドウ |
| `widget/windows/settings_window.py` | 新規 | 設定画面ウィンドウ |
| `widget/windows/input_window.py` | 修正 | 履歴保存・通知・テンプレート・D&D・音声入力 |
| `widget/main.py` | 修正 | 「起票履歴」「設定」トレイメニュー追加、HistoryWindow/SettingsWindow 開閉管理 |
| `widget/data/templates.json` | 新規 | テキストテンプレート定義 |
| `widget/requirements.txt` | 修正 | tkinterdnd2, sounddevice, scipy, faster-whisper 追加 |
| `widget/tests/test_history_store.py` | 新規 | history_store のユニットテスト |
| `widget/tests/test_toast_notifier.py` | 新規 | notify_success のユニットテスト |
| `widget/tests/test_audio_recorder.py` | 新規 | AudioRecorder のユニットテスト |

---

## Task 1: notify_success() の追加

**Files:**
- Modify: `widget/services/toast_notifier.py`
- Create: `widget/tests/test_toast_notifier.py`

- [ ] **Step 1: 失敗テストを書く**

`widget/tests/test_toast_notifier.py` を新規作成：

```python
from unittest.mock import patch, MagicMock


def _mock_notification():
    notif = MagicMock()
    notif.set_audio = MagicMock()
    notif.show = MagicMock()
    return notif


def test_notify_success_calls_show():
    from widget.services.toast_notifier import notify_success
    mock_notif = _mock_notification()
    with patch("widget.services.toast_notifier._WINOTIFY_AVAILABLE", True), \
         patch("widget.services.toast_notifier.Notification", return_value=mock_notif) as mock_cls:
        notify_success("テストタスク", launch_url="https://example.com/tasks/1")
    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["title"] == "✅ 起票しました"
    assert call_kwargs["msg"] == "テストタスク"
    assert call_kwargs["launch"] == "https://example.com/tasks/1"
    mock_notif.show.assert_called_once()


def test_notify_success_silent_when_winotify_unavailable():
    from widget.services.toast_notifier import notify_success
    with patch("widget.services.toast_notifier._WINOTIFY_AVAILABLE", False):
        notify_success("テストタスク")  # 例外が出ないこと


def test_notify_success_empty_launch_url():
    from widget.services.toast_notifier import notify_success
    mock_notif = _mock_notification()
    with patch("widget.services.toast_notifier._WINOTIFY_AVAILABLE", True), \
         patch("widget.services.toast_notifier.Notification", return_value=mock_notif) as mock_cls:
        notify_success("タスク名")
    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["launch"] == ""
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest widget/tests/test_toast_notifier.py -v
```
Expected: FAIL（`notify_success` が未定義）

- [ ] **Step 3: toast_notifier.py に notify_success() を追加**

`widget/services/toast_notifier.py` の末尾に追加：

```python
def notify_success(title: str, launch_url: str = "") -> None:
    """起票成功のトースト通知を表示する。"""
    if not _WINOTIFY_AVAILABLE:
        logging.warning("winotify が見つかりません。トースト通知をスキップします。")
        return
    try:
        toast = Notification(
            app_id="AutoTicket",
            title="✅ 起票しました",
            msg=title,
            duration="short",
            launch=launch_url,
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        logging.debug("notify_success: %s", title)
    except Exception as exc:
        logging.error("notify_success error: %s", exc)
```

- [ ] **Step 4: テストが通ることを確認**

```
pytest widget/tests/test_toast_notifier.py -v
```
Expected: 3 passed

- [ ] **Step 5: コミット**

```
git add widget/services/toast_notifier.py widget/tests/test_toast_notifier.py
git commit -m "feat(widget): notify_success() を toast_notifier に追加"
```

---

## Task 2: 起票履歴ストア

**Files:**
- Create: `widget/services/history_store.py`
- Create: `widget/tests/test_history_store.py`

- [ ] **Step 1: 失敗テストを書く**

`widget/tests/test_history_store.py` を新規作成：

```python
import pytest
import pathlib
import tempfile


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """テスト用に history.db をテンポラリディレクトリに向ける。"""
    import widget.services.history_store as hs
    monkeypatch.setattr(hs, "_DB_PATH", tmp_path / "history.db")
    return tmp_path / "history.db"


def test_add_and_get_history(tmp_db):
    from widget.services.history_store import add_history, get_history
    add_history("task-1", "タスクA", "プロジェクト1")
    add_history("task-2", "タスクB", None)
    items = get_history()
    assert len(items) == 2
    assert items[0].task_id == "task-2"   # 新しい順
    assert items[0].title == "タスクB"
    assert items[0].project_name is None
    assert items[1].task_id == "task-1"
    assert items[1].project_name == "プロジェクト1"


def test_history_capped_at_10(tmp_db):
    from widget.services.history_store import add_history, get_history
    for i in range(15):
        add_history(f"task-{i}", f"タスク{i}")
    items = get_history()
    assert len(items) == 10


def test_get_history_returns_empty_list_when_no_entries(tmp_db):
    from widget.services.history_store import get_history
    assert get_history() == []


def test_history_entry_has_created_at(tmp_db):
    from widget.services.history_store import add_history, get_history
    add_history("task-x", "テスト")
    entry = get_history()[0]
    assert entry.created_at  # 空でない
    assert "T" in entry.created_at  # ISO 形式
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest widget/tests/test_history_store.py -v
```
Expected: FAIL（`history_store` が未定義）

- [ ] **Step 3: history_store.py を実装**

`widget/services/history_store.py` を新規作成：

```python
from __future__ import annotations

import logging
import pathlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime

_DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "history.db"
_MAX_HISTORY = 10


@dataclass
class HistoryEntry:
    task_id: str
    title: str
    project_name: str | None
    created_at: str


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            title TEXT NOT NULL,
            project_name TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def add_history(task_id: str, title: str, project_name: str | None = None) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO history (task_id, title, project_name, created_at) VALUES (?, ?, ?, ?)",
            (task_id, title, project_name, datetime.now().isoformat()),
        )
        conn.execute(
            "DELETE FROM history WHERE id NOT IN "
            "(SELECT id FROM history ORDER BY id DESC LIMIT ?)",
            (_MAX_HISTORY,),
        )
        conn.commit()
    except Exception as exc:
        logging.error("history_store.add_history error: %s", exc)
    finally:
        conn.close()


def get_history() -> list[HistoryEntry]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT task_id, title, project_name, created_at "
            "FROM history ORDER BY id DESC LIMIT ?",
            (_MAX_HISTORY,),
        ).fetchall()
        return [HistoryEntry(r[0], r[1], r[2], r[3]) for r in rows]
    except Exception as exc:
        logging.error("history_store.get_history error: %s", exc)
        return []
    finally:
        conn.close()
```

- [ ] **Step 4: テストが通ることを確認**

```
pytest widget/tests/test_history_store.py -v
```
Expected: 4 passed

- [ ] **Step 5: コミット**

```
git add widget/services/history_store.py widget/tests/test_history_store.py
git commit -m "feat(widget): 起票履歴ストア（SQLite）を実装"
```

---

## Task 3: 起票履歴ウィンドウ + main.py 統合

**Files:**
- Create: `widget/windows/history_window.py`
- Modify: `widget/main.py`

- [ ] **Step 1: history_window.py を実装**

`widget/windows/history_window.py` を新規作成：

```python
from __future__ import annotations

import logging
import threading
import webbrowser

import customtkinter as ctk

from widget.services.history_store import HistoryEntry, get_history


class HistoryWindow(ctk.CTkToplevel):
    """起票履歴一覧ウィンドウ（直近10件）。"""

    def __init__(self, parent: ctk.CTk, frontend_url: str) -> None:
        super().__init__(parent)
        self.title("AutoTicket - 起票履歴")
        self.geometry("500x400")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.minsize(380, 280)
        self._frontend_url = frontend_url.rstrip("/")
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            header, text="起票履歴（直近10件）", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(side="left")
        self._reload_btn = ctk.CTkButton(header, text="更新", width=72, command=self._load)
        self._reload_btn.pack(side="right")

        self._status_lbl = ctk.CTkLabel(
            self, text="読み込み中…", text_color=("gray30", "gray70"), font=ctk.CTkFont(size=12)
        )
        self._status_lbl.pack(pady=(0, 4))

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._scroll.columnconfigure(0, weight=1)
        self._scroll.columnconfigure(1, weight=0)

    def _load(self) -> None:
        self._reload_btn.configure(state="disabled", text="読込中…")
        for w in self._scroll.winfo_children():
            w.destroy()

        def _run() -> None:
            items = get_history()
            self.after(0, lambda it=items: self._on_loaded(it))

        threading.Thread(target=_run, daemon=True).start()

    def _on_loaded(self, items: list[HistoryEntry]) -> None:
        self._reload_btn.configure(state="normal", text="更新")
        if not items:
            self._status_lbl.configure(text="起票履歴がありません。")
            return
        self._status_lbl.configure(text=f"{len(items)} 件")
        for i, entry in enumerate(items):
            self._add_row(i, entry)

    def _add_row(self, row_idx: int, entry: HistoryEntry) -> None:
        proj = f"  [{entry.project_name}]" if entry.project_name else ""
        date_str = entry.created_at[:10] if len(entry.created_at) >= 10 else ""
        label_text = f"{date_str}  {entry.title}{proj}"
        lbl = ctk.CTkLabel(
            self._scroll,
            text=label_text,
            anchor="w",
            font=ctk.CTkFont(size=12),
            wraplength=320,
        )
        lbl.grid(row=row_idx, column=0, padx=(8, 4), pady=4, sticky="ew")

        if self._frontend_url:
            url = f"{self._frontend_url}/tasks/{entry.task_id}"
            btn = ctk.CTkButton(
                self._scroll,
                text="開く",
                width=60,
                height=26,
                command=lambda u=url: webbrowser.open(u),
            )
        else:
            btn = ctk.CTkLabel(self._scroll, text="", width=60)
        btn.grid(row=row_idx, column=1, padx=(0, 8), pady=4)
```

- [ ] **Step 2: main.py に「起票履歴」メニューと HistoryWindow 管理を追加**

`widget/main.py` の import 行に追加：

```python
from widget.windows.history_window import HistoryWindow
```

`AppController.__init__` の `self._todo_window_open = False` の直後に追加：
```python
self._history_window_open = False
```

`_show_todo_window` の直後に追加：

```python
def _show_history_window(self) -> None:
    if self._history_window_open or self._root is None:
        return
    self._history_window_open = True
    win = HistoryWindow(self._root, self.config.frontend_url)
    win.protocol("WM_DELETE_WINDOW", lambda: self._on_history_close(win))

def _on_history_close(self, win: HistoryWindow) -> None:
    self._history_window_open = False
    win.destroy()
```

pystray.Menu のメニュー定義を以下に変更（「今日のタスク」の後に「起票履歴」を追加）：

```python
menu=pystray.Menu(
    pystray.MenuItem("タスク入力", lambda _i, _it: self._root.after(0, self._show_window)),
    pystray.MenuItem("今日のタスク", lambda _i, _it: self._root.after(0, self._show_todo_window)),
    pystray.MenuItem("起票履歴", lambda _i, _it: self._root.after(0, self._show_history_window)),
    pystray.MenuItem("設定", lambda _i, _it: self._root.after(0, self._show_settings_window)),
    pystray.MenuItem("終了", lambda _i, _it: self._root.after(0, self._quit)),
),
```

※ `_show_settings_window` は Task 5 で実装。いまは定義だけ仮置きしても OK（呼ばれてもエラーにならないよう `pass` だけの仮メソッドを置く）：

```python
def _show_settings_window(self) -> None:
    pass  # Task 5 で実装
```

- [ ] **Step 3: 既存テストが通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全 42 passed（既存 39 + test_toast_notifier 3 + test_history_store 4）

- [ ] **Step 4: コミット**

```
git add widget/windows/history_window.py widget/main.py
git commit -m "feat(widget): 起票履歴ウィンドウ + トレイメニュー追加"
```

---

## Task 4: 起票時の履歴保存・成功通知の統合

**Files:**
- Modify: `widget/windows/input_window.py`

`_on_send` メソッドと `_on_success` メソッドを変更して、起票成功時に履歴保存・トースト通知を行う。

- [ ] **Step 1: input_window.py の import に追加**

`widget/windows/input_window.py` の import 行の末尾に追加：

```python
from widget.services.history_store import add_history
from widget.services.toast_notifier import notify_success
```

- [ ] **Step 2: _on_send を修正して result と付随情報をスレッドから受け取る**

`_on_send` 内の `project_name_for_history` を取得してクロージャに渡すよう変更：

現在の `_on_send` の `def _run() -> None:` ブロックの直前に以下を追加し、`_run` 内部を変更：

```python
    def _on_send(self) -> None:
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
```

- [ ] **Step 3: _on_success シグネチャを変更して履歴保存・通知を追加**

現在の `_on_success(self) -> None:` を以下に置き換え：

```python
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
            self.after(3000, lambda: self._status_lbl.configure(text="", font=ctk.CTkFont(size=13)))
        except Exception:
            logging.error("_on_success failed:\n" + traceback.format_exc())
```

- [ ] **Step 4: 全テストが通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```
git add widget/windows/input_window.py
git commit -m "feat(widget): 起票成功時に履歴保存・トースト通知を追加"
```

---

## Task 5: 設定画面

**Files:**
- Create: `widget/windows/settings_window.py`
- Modify: `widget/main.py`

- [ ] **Step 1: settings_window.py を実装**

`widget/windows/settings_window.py` を新規作成：

```python
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from widget.config import Config, save_config


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
        self.geometry("480x420")
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
                ).grid(row=row[0], column=1, padx=(0, 10), pady=(0, 4), sticky="w")
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
        self._on_save(self._config)
        self._note_lbl.configure(text="✅ 保存しました（一部設定は再起動後に反映）")
        self.after(2500, self.destroy)
```

- [ ] **Step 2: main.py の _show_settings_window を実装**

`widget/main.py` の import 行に追加：

```python
from widget.windows.settings_window import SettingsWindow
```

`AppController.__init__` に追加：

```python
self._settings_window_open = False
```

`_show_settings_window` の `pass` を以下に置き換え：

```python
def _show_settings_window(self) -> None:
    if self._settings_window_open or self._root is None:
        return
    self._settings_window_open = True

    def _on_save(new_config: Config) -> None:
        self.config = new_config

    win = SettingsWindow(self._root, self.config, on_save=_on_save)
    win.protocol("WM_DELETE_WINDOW", lambda: self._on_settings_close(win))

def _on_settings_close(self, win: SettingsWindow) -> None:
    self._settings_window_open = False
    win.destroy()
```

- [ ] **Step 3: 全テストが通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 4: コミット**

```
git add widget/windows/settings_window.py widget/main.py
git commit -m "feat(widget): 設定画面を追加（ホットキー・モデル・URL変更）"
```

---

## Task 6: テキストテンプレート

**Files:**
- Create: `widget/data/templates.json`
- Modify: `widget/windows/input_window.py`

- [ ] **Step 1: templates.json を作成**

`widget/data/` ディレクトリを作成し、`widget/data/templates.json` を新規作成：

```json
[
  {"name": "確認依頼", "text": "〇〇の確認を担当者にお願いしたい。"},
  {"name": "報告書作成", "text": "〇〇の報告書を作成する。期限は〇月〇日。"},
  {"name": "MTG準備", "text": "〇〇のMTGの事前資料を準備する。"},
  {"name": "問題対応", "text": "〇〇で発生した問題を調査・対応する。"},
  {"name": "レビュー依頼", "text": "〇〇のレビューを担当者にお願いしたい。"}
]
```

- [ ] **Step 2: テンプレート読み込み関数を input_window.py に追加**

`widget/windows/input_window.py` の import の直後に関数を追加：

```python
import json as _json

def _load_templates() -> list[dict]:
    p = Path(__file__).parent.parent / "data" / "templates.json"
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
```

- [ ] **Step 3: _build_input_panel にテンプレート行を追加**

`_build_input_panel` メソッドの `tools` フレームの `pack` 後、ラベルの前に以下を追加：

```python
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
```

- [ ] **Step 4: _on_template_select メソッドを追加**

`_build_input_panel` の直後に追加：

```python
    def _on_template_select(self, name: str, templates: list[dict]) -> None:
        if name == "テンプレートを選択…":
            return
        tpl = next((t for t in templates if t["name"] == name), None)
        if tpl:
            self._text.delete("1.0", "end")
            self._text.insert("1.0", tpl["text"])
            self._text.focus()
```

- [ ] **Step 5: 全テストが通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```
git add widget/data/templates.json widget/windows/input_window.py
git commit -m "feat(widget): テキストテンプレート選択機能を追加"
```

---

## Task 7: ドラッグ＆ドロップ

**Files:**
- Modify: `widget/windows/input_window.py`
- Modify: `widget/requirements.txt`

`tkinterdnd2` を使って InputWindow のテキストエリアと画像エリアにファイルドロップを対応させる。
`.txt` → テキスト読み込み、`.png/.jpg/.jpeg/.bmp` → Vision 解析フロー（既存の `_open_image_file` と同じ）。

- [ ] **Step 1: tkinterdnd2 を requirements.txt に追加**

`widget/requirements.txt` の末尾に追加：

```
tkinterdnd2>=0.3
```

- [ ] **Step 2: tkinterdnd2 をインストール**

```
pip install tkinterdnd2
```

- [ ] **Step 3: input_window.py に D&D セットアップを追加**

`widget/windows/input_window.py` の import 末尾に追加：

```python
_DND_AVAILABLE = False
try:
    from tkinterdnd2 import DND_FILES  # type: ignore[import]
    _DND_AVAILABLE = True
except ImportError:
    pass
```

`_build_input_panel` の末尾（`self._text.focus()` の後）に追加：

```python
        self._setup_dnd()
```

`_on_template_select` の後に追加：

```python
    def _setup_dnd(self) -> None:
        if not _DND_AVAILABLE:
            return
        try:
            # CTkTextbox の内部 Text ウィジェットにバインド
            inner = self._text._textbox  # type: ignore[attr-defined]
            inner.drop_target_register(DND_FILES)
            inner.dnd_bind("<<Drop>>", self._on_drop)
        except Exception as exc:
            import logging
            logging.debug("D&D setup failed: %s", exc)

    def _on_drop(self, event: object) -> None:
        raw: str = getattr(event, "data", "")
        # tkinterdnd2 はスペース入りパスを {} で囲む
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
            self._status_lbl.configure(text="画像を解析中…", text_color=("gray30", "gray70"))
            self._start_elapsed_timer("画像を解析中")

            def _run() -> None:
                parsed = self._vision.parse_image(path)
                self.after(0, lambda p=parsed: self._on_image_parsed(p))

            threading.Thread(target=_run, daemon=True).start()
        else:
            self._status_lbl.configure(
                text=f"未対応のファイル形式: {suffix}", text_color=("gray30", "gray70")
            )
```

- [ ] **Step 4: 全テストが通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```
git add widget/windows/input_window.py widget/requirements.txt
git commit -m "feat(widget): ドラッグ＆ドロップでファイル入力に対応"
```

---

## Task 8: 音声入力

**Files:**
- Create: `widget/services/audio_recorder.py`
- Create: `widget/tests/test_audio_recorder.py`
- Modify: `widget/windows/input_window.py`
- Modify: `widget/requirements.txt`

- [ ] **Step 1: requirements.txt に追加**

`widget/requirements.txt` の末尾に追加：

```
sounddevice>=0.4
scipy>=1.13
faster-whisper>=1.0
```

- [ ] **Step 2: パッケージをインストール**

```
pip install sounddevice scipy faster-whisper
```

- [ ] **Step 3: 失敗テストを書く**

`widget/tests/test_audio_recorder.py` を新規作成：

```python
import pathlib
import tempfile
from unittest.mock import patch, MagicMock
import numpy as np


def test_stop_and_save_creates_wav_file():
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    recorder._frames = [np.zeros((1600, 1), dtype=np.float32)]
    with tempfile.TemporaryDirectory() as tmp:
        out_path = pathlib.Path(tmp) / "test.wav"
        with patch("scipy.io.wavfile.write") as mock_write:
            result = recorder.stop_and_save(out_path)
        mock_write.assert_called_once()
        assert result == out_path


def test_stop_and_save_returns_none_when_no_frames():
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    recorder._frames = []
    result = recorder.stop_and_save()
    assert result is None


def test_transcribe_calls_faster_whisper():
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "テストテキスト"
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())
    with patch("widget.services.audio_recorder.WhisperModel", return_value=mock_model):
        result = recorder.transcribe(pathlib.Path("dummy.wav"))
    assert result == "テストテキスト"


def test_transcribe_returns_empty_on_error():
    from widget.services.audio_recorder import AudioRecorder
    recorder = AudioRecorder()
    with patch("widget.services.audio_recorder.WhisperModel", side_effect=Exception("load error")):
        result = recorder.transcribe(pathlib.Path("dummy.wav"))
    assert result == ""
```

- [ ] **Step 4: テストが失敗することを確認**

```
pytest widget/tests/test_audio_recorder.py -v
```
Expected: FAIL（`audio_recorder` が未定義）

- [ ] **Step 5: audio_recorder.py を実装**

`widget/services/audio_recorder.py` を新規作成：

```python
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd  # type: ignore[import]
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False

try:
    from faster_whisper import WhisperModel  # type: ignore[import]
    _WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]
    _WHISPER_AVAILABLE = False

_SAMPLERATE = 16000
_CHANNELS = 1
_WHISPER_MODEL_SIZE = "small"


class AudioRecorder:
    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._stream: object | None = None

    @property
    def is_available(self) -> bool:
        return _SD_AVAILABLE and _WHISPER_AVAILABLE

    def start(self) -> None:
        if not _SD_AVAILABLE:
            logging.warning("sounddevice が利用できません")
            return
        self._frames = []
        self._recording = True

        def _callback(indata: np.ndarray, frames: int, time: object, status: object) -> None:
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(  # type: ignore[attr-defined]
            samplerate=_SAMPLERATE,
            channels=_CHANNELS,
            dtype="float32",
            callback=_callback,
        )
        self._stream.start()  # type: ignore[union-attr]
        logging.debug("AudioRecorder: 録音開始")

    def stop_and_save(self, out_path: Path | None = None) -> Path | None:
        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()  # type: ignore[union-attr]
                self._stream.close()  # type: ignore[union-attr]
            except Exception as exc:
                logging.warning("AudioRecorder stream stop error: %s", exc)
            self._stream = None

        if not self._frames:
            logging.debug("AudioRecorder: 録音データなし")
            return None

        audio = np.concatenate(self._frames, axis=0)
        if out_path is None:
            out_path = Path(tempfile.mktemp(suffix=".wav"))

        import scipy.io.wavfile as wav_io  # type: ignore[import]
        wav_io.write(str(out_path), _SAMPLERATE, audio)
        logging.debug("AudioRecorder: 保存 %s", out_path)
        return out_path

    def transcribe(self, audio_path: Path, model_size: str = _WHISPER_MODEL_SIZE) -> str:
        if not _WHISPER_AVAILABLE or WhisperModel is None:
            logging.warning("faster-whisper が利用できません")
            return ""
        try:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(audio_path), language="ja")
            return "".join(s.text for s in segments).strip()
        except Exception as exc:
            logging.error("AudioRecorder.transcribe error: %s", exc)
            return ""
```

- [ ] **Step 6: テストが通ることを確認**

```
pytest widget/tests/test_audio_recorder.py -v
```
Expected: 4 passed

- [ ] **Step 7: InputWindow に音声入力ボタンを追加**

`widget/windows/input_window.py` の `__init__` で `AudioRecorder` を初期化：

import 末尾に追加：
```python
from widget.services.audio_recorder import AudioRecorder
```

`__init__` の `self._last_input_text: str = ""` の直後に追加：
```python
        self._recorder = AudioRecorder()
        self._recording = False
```

`_build_input_panel` の `tools` フレームの `.pack(side="left")` の後（クリップボード・画像ボタンの後）に追加：

```python
        if self._recorder.is_available:
            self._mic_btn = ctk.CTkButton(
                tools, text="🎤 音声入力", width=110, height=28,
                command=self._toggle_recording,
            )
            self._mic_btn.pack(side="left", padx=(8, 0))
```

`_on_template_select` の後に追加：

```python
    def _toggle_recording(self) -> None:
        if not self._recording:
            self._recording = True
            self._mic_btn.configure(text="⏹ 録音停止", fg_color="red", hover_color="#cc0000")
            self._status_lbl.configure(text="🎤 録音中…", text_color="red")
            self._recorder.start()
        else:
            self._recording = False
            self._mic_btn.configure(
                text="🎤 音声入力", fg_color=["#3B8ED0", "#1F6AA5"],
                hover_color=["#36719F", "#144870"],
            )
            self._status_lbl.configure(text="文字起こし中…", text_color=("gray30", "gray70"))
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
            self.after(0, lambda: self._status_lbl.configure(
                text="文字起こし失敗", text_color=("gray30", "gray70")
            ))

    def _insert_transcribed(self, text: str) -> None:
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.focus()
        self._status_lbl.configure(text="")
```

- [ ] **Step 8: 全テストが通ることを確認**

```
pytest widget/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 9: コミット**

```
git add widget/services/audio_recorder.py widget/tests/test_audio_recorder.py widget/windows/input_window.py widget/requirements.txt
git commit -m "feat(widget): 音声入力（sounddevice + faster-whisper）を追加"
```

---

## 完了確認チェックリスト

- [ ] `notify_success()` が winotify トーストを表示し、クリックでタスク詳細を開く
- [ ] 起票成功時に history.db に記録される
- [ ] トレイ「起票履歴」からウィンドウが開き、直近10件が表示される
- [ ] 各履歴の「開く」ボタンでブラウザのタスク詳細ページが開く
- [ ] トレイ「設定」からウィンドウが開き、保存が config.json に反映される
- [ ] InputWindow にテンプレートコンボが表示され、選択するとテキストが入力される
- [ ] .txt ファイルをドロップするとテキストエリアに内容が入る
- [ ] 画像ファイルをドロップすると Vision 解析フローに進む
- [ ] 「🎤 音声入力」ボタンで録音 → 文字起こし → テキストエリアに挿入される
- [ ] `pytest widget/tests/ -v` が全件 PASS

---

## 依存関係まとめ

```
Task 1 (notify_success)
    └─→ Task 4 に必要

Task 2 (history_store)
    └─→ Task 3, Task 4 に必要

Task 3 (history_window + main.py) ← Task 2 完了後
Task 4 (input_window 統合)       ← Task 1, 2 完了後
Task 5 (settings_window)          ← 独立
Task 6 (テンプレート)              ← 独立
Task 7 (D&D)                      ← 独立
Task 8 (音声入力)                  ← 独立
```

推奨実施順: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8**
