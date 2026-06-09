# ウィジェット フェーズ2A 入力手段拡張 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** InputWindow にクリップボード貼り付けボタンとスクリーンショットボタンを追加し、テキスト入力以外の方法でタスクを起票できるようにする。

**Architecture:** `widget/services/` パッケージを新設して `ClipboardReader` と `ScreenshotCapture` を配置。`OllamaClient` に Vision 解析メソッドを追加。`InputWindow` に2つのボタンを追加し、各サービスを呼び出す。`AppController` がサービスを生成して `InputWindow` に渡す。

**Tech Stack:** Pillow（既存）の `ImageGrab.grab()`、`ollama.chat()` の `images` 引数（Vision）、`tkinter.clipboard_get()`。

---

## ファイル構成

```
新規作成:
  widget/services/__init__.py
  widget/services/clipboard_reader.py
  widget/services/screenshot_capture.py
  widget/tests/test_clipboard_reader.py
  widget/tests/test_screenshot_capture.py

変更:
  widget/clients/ollama_client.py     ← parse_image() 追加
  widget/tests/test_ollama_client.py  ← Vision テスト追加
  widget/windows/input_window.py      ← ボタン2つ・__init__ 引数追加
  widget/main.py                      ← サービス生成・InputWindow 呼び出し更新
```

---

## Task 1: ClipboardReader サービスを作成する

**Files:**
- Create: `widget/services/__init__.py`
- Create: `widget/services/clipboard_reader.py`
- Create: `widget/tests/test_clipboard_reader.py`

- [ ] **Step 1: `widget/services/__init__.py` を作成する**

```python
# widget/services/__init__.py
```

（空ファイル。パッケージとして認識させるだけ）

- [ ] **Step 2: `widget/services/clipboard_reader.py` を作成する**

```python
from __future__ import annotations
from typing import Callable

MAX_CHARS = 1000


class ClipboardReader:
    def __init__(self, get_clipboard: Callable[[], str]) -> None:
        self._get = get_clipboard

    def read(self) -> str:
        try:
            text = self._get()
            if not text:
                return ""
            return text[:MAX_CHARS]
        except Exception:
            return ""

    def has_content(self) -> bool:
        return bool(self.read())
```

- [ ] **Step 3: `widget/tests/test_clipboard_reader.py` を作成する（テスト先行）**

```python
import pytest
from widget.services.clipboard_reader import ClipboardReader, MAX_CHARS


def test_read_returns_clipboard_text():
    reader = ClipboardReader(get_clipboard=lambda: "タスクを確認する")
    assert reader.read() == "タスクを確認する"


def test_read_truncates_long_text():
    long_text = "a" * (MAX_CHARS + 100)
    reader = ClipboardReader(get_clipboard=lambda: long_text)
    result = reader.read()
    assert len(result) == MAX_CHARS


def test_read_returns_empty_on_exception():
    def raise_error() -> str:
        raise Exception("clipboard empty")
    reader = ClipboardReader(get_clipboard=raise_error)
    assert reader.read() == ""


def test_has_content_returns_true_when_text_present():
    reader = ClipboardReader(get_clipboard=lambda: "some text")
    assert reader.has_content() is True


def test_has_content_returns_false_when_empty():
    reader = ClipboardReader(get_clipboard=lambda: "")
    assert reader.has_content() is False
```

- [ ] **Step 4: テストを実行して全 PASS を確認する**

```
pytest widget/tests/test_clipboard_reader.py -v
```

期待出力:
```
PASSED widget/tests/test_clipboard_reader.py::test_read_returns_clipboard_text
PASSED widget/tests/test_clipboard_reader.py::test_read_truncates_long_text
PASSED widget/tests/test_clipboard_reader.py::test_read_returns_empty_on_exception
PASSED widget/tests/test_clipboard_reader.py::test_has_content_returns_true_when_text_present
PASSED widget/tests/test_clipboard_reader.py::test_has_content_returns_false_when_empty
5 passed
```

- [ ] **Step 5: コミット**

```bash
git add widget/services/__init__.py widget/services/clipboard_reader.py widget/tests/test_clipboard_reader.py
git commit -m "feat: ClipboardReader サービスを追加（テスト5件）"
```

---

## Task 2: OllamaClient に Vision パースを追加する

**Files:**
- Modify: `widget/clients/ollama_client.py`
- Modify: `widget/tests/test_ollama_client.py`

- [ ] **Step 1: `widget/clients/ollama_client.py` に Vision プロンプトと `parse_image()` を追加する**

既存の `import json` の次に `from pathlib import Path` を追加し、ファイル末尾に以下を追記する。

```python
# 既存 import の直下に追加
from pathlib import Path
```

`_EMPTY` 定数（`_EMPTY: dict = {"title": None, ...}` の行）の直後に追加:

```python
_VISION_EMPTY: dict = {
    "title": None,
    "due_date": None,
    "assignee_name": None,
    "priority": None,
    "description_hint": None,
}

_VISION_PROMPT = """\
画像からタスク管理に関連する情報を抽出してください。
今日の日付: {today}

以下の JSON のみを出力してください（説明・コードブロック不要）:
{{
  "title": "タスクタイトル（日本語で簡潔に、必須）",
  "due_date": "YYYY-MM-DD または null",
  "assignee_name": "担当者の表示名または null",
  "priority": "low|medium|high|urgent または null",
  "description_hint": "画像から読み取れる補足情報（1〜2文）または null"
}}\
"""
```

`OllamaClient` クラスの末尾（`parse` メソッドの後）に追加:

```python
    def parse_image(self, image_path: Path) -> dict:
        today = date.today().isoformat()
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": _VISION_PROMPT.format(today=today),
                    "images": [str(image_path)],
                }],
                options={"temperature": 0},
            )
            raw = response["message"]["content"].strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return dict(_VISION_EMPTY)
            return json.loads(raw[start:end])
        except Exception:
            return dict(_VISION_EMPTY)
```

- [ ] **Step 2: `widget/tests/test_ollama_client.py` に Vision テストを追記する**

ファイル末尾に追記:

```python
# --- Vision テスト ---

def test_parse_image_returns_structured_dict():
    from widget.clients.ollama_client import OllamaClient
    from pathlib import Path

    mock_content = (
        '{"title": "報告書作成", "due_date": "2026-06-20", '
        '"assignee_name": "田中", "priority": "high", '
        '"description_hint": "月次報告書の作成が必要"}'
    )
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient(model="gemma4:e4b")
        result = client.parse_image(Path("/tmp/screen.png"))
    assert result["title"] == "報告書作成"
    assert result["due_date"] == "2026-06-20"
    assert result["description_hint"] == "月次報告書の作成が必要"


def test_parse_image_returns_empty_on_error():
    from widget.clients.ollama_client import OllamaClient
    from pathlib import Path

    with patch("ollama.chat", side_effect=Exception("vision error")):
        client = OllamaClient()
        result = client.parse_image(Path("/tmp/screen.png"))
    assert result["title"] is None
    assert result["description_hint"] is None


def test_parse_image_passes_image_path_to_ollama():
    from widget.clients.ollama_client import OllamaClient
    from pathlib import Path

    captured: dict = {}

    def fake_chat(model: str, messages: list, options: dict) -> dict:
        captured["images"] = messages[0]["images"]
        return _mock_ollama_response(
            '{"title": "test", "due_date": null, "assignee_name": null, '
            '"priority": null, "description_hint": null}'
        )

    with patch("ollama.chat", side_effect=fake_chat):
        client = OllamaClient()
        client.parse_image(Path("/tmp/test.png"))

    assert captured["images"] == ["/tmp/test.png"]
```

- [ ] **Step 3: テストを実行して全 PASS を確認する**

```
pytest widget/tests/test_ollama_client.py -v
```

期待出力（既存4件 + 新規3件 = 7件 passed）:
```
PASSED ...::test_parse_returns_structured_dict
PASSED ...::test_parse_extracts_json_from_noisy_response
PASSED ...::test_parse_returns_empty_dict_on_ollama_error
PASSED ...::test_parse_sends_today_date_in_system_prompt
PASSED ...::test_parse_image_returns_structured_dict
PASSED ...::test_parse_image_returns_empty_on_error
PASSED ...::test_parse_image_passes_image_path_to_ollama
7 passed
```

- [ ] **Step 4: コミット**

```bash
git add widget/clients/ollama_client.py widget/tests/test_ollama_client.py
git commit -m "feat: OllamaClient に Vision パース(parse_image)を追加（テスト3件）"
```

---

## Task 3: ScreenshotCapture サービスを作成する

**Files:**
- Create: `widget/services/screenshot_capture.py`
- Create: `widget/tests/test_screenshot_capture.py`

- [ ] **Step 1: `widget/services/screenshot_capture.py` を作成する**

```python
from __future__ import annotations
import tempfile
from pathlib import Path
from PIL import ImageGrab


class ScreenshotCapture:
    def capture(self) -> Path:
        img = ImageGrab.grab()
        tmp = Path(tempfile.mktemp(suffix=".png"))
        img.save(str(tmp), "PNG")
        return tmp

    def cleanup(self, path: Path) -> None:
        path.unlink(missing_ok=True)
```

- [ ] **Step 2: `widget/tests/test_screenshot_capture.py` を作成する（テスト先行）**

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_capture_saves_png_and_returns_path(tmp_path):
    from widget.services.screenshot_capture import ScreenshotCapture

    mock_img = MagicMock()
    expected_path = str(tmp_path / "screen.png")

    with patch("PIL.ImageGrab.grab", return_value=mock_img):
        with patch("tempfile.mktemp", return_value=expected_path):
            capture = ScreenshotCapture()
            result = capture.capture()

    assert result == Path(expected_path)
    mock_img.save.assert_called_once_with(expected_path, "PNG")


def test_cleanup_removes_existing_file(tmp_path):
    from widget.services.screenshot_capture import ScreenshotCapture

    test_file = tmp_path / "screen.png"
    test_file.write_bytes(b"dummy")

    ScreenshotCapture().cleanup(test_file)

    assert not test_file.exists()


def test_cleanup_does_not_raise_if_file_missing(tmp_path):
    from widget.services.screenshot_capture import ScreenshotCapture

    missing = tmp_path / "nonexistent.png"
    ScreenshotCapture().cleanup(missing)  # 例外が出なければ OK
```

- [ ] **Step 3: テストを実行して全 PASS を確認する**

```
pytest widget/tests/test_screenshot_capture.py -v
```

期待出力:
```
PASSED widget/tests/test_screenshot_capture.py::test_capture_saves_png_and_returns_path
PASSED widget/tests/test_screenshot_capture.py::test_cleanup_removes_existing_file
PASSED widget/tests/test_screenshot_capture.py::test_cleanup_does_not_raise_if_file_missing
3 passed
```

- [ ] **Step 4: コミット**

```bash
git add widget/services/screenshot_capture.py widget/tests/test_screenshot_capture.py
git commit -m "feat: ScreenshotCapture サービスを追加（テスト3件）"
```

---

## Task 4: InputWindow にクリップボードボタンを追加する

**Files:**
- Modify: `widget/windows/input_window.py`
- Modify: `widget/main.py`

- [ ] **Step 1: `InputWindow.__init__` に `clipboard` と `screenshot` 引数を追加する**

`widget/windows/input_window.py` の import に追加:

```python
from widget.services.clipboard_reader import ClipboardReader
from widget.services.screenshot_capture import ScreenshotCapture
```

`__init__` のシグネチャを変更（`projects: list[ProjectInfo]` の後に2引数追加）:

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
        screenshot: ScreenshotCapture,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._ollama = ollama
        self._backend = backend
        self._users = users
        self._projects = projects
        self._clipboard = clipboard
        self._screenshot = screenshot

        self.title("AutoTicket")
        self.geometry("440x230")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._build_input_panel()
```

- [ ] **Step 2: `_build_input_panel` にツールボタン行とクリップボードロジックを追加する**

`_build_input_panel` メソッドを以下で置き換える:

```python
    def _build_input_panel(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("440x230")

        # Row 1: ユーザー選択
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(top, text="👤").pack(side="left")
        user_names = [u.display_name for u in self._users]
        current = next(
            (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
            user_names[0] if user_names else "",
        )
        self._user_combo = ctk.CTkComboBox(top, values=user_names, width=220, state="readonly")
        self._user_combo.set(current)
        self._user_combo.pack(side="left", padx=8)

        # Row 2: 入力ツールボタン
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=16, pady=(0, 2))
        ctk.CTkButton(
            tools, text="📋 クリップボード", width=160, height=28,
            command=self._paste_clipboard,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            tools, text="📸 スクリーンショット", width=170, height=28,
            command=self._capture_screenshot,
        ).pack(side="left")

        # Row 3: テキストボックス
        self._text = ctk.CTkTextbox(self, height=70, width=410)
        self._text.pack(padx=16, pady=2)
        self._text.focus()

        # Row 4: ステータス + 送信ボタン
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(2, 12))
        self._status_lbl = ctk.CTkLabel(btn_row, text="", text_color="gray")
        self._status_lbl.pack(side="left")
        self._submit_btn = ctk.CTkButton(btn_row, text="AIで起票する →", command=self._on_ai_submit)
        self._submit_btn.pack(side="right")
```

- [ ] **Step 3: `_paste_clipboard` メソッドを追加する**

`_on_ai_submit` メソッドの直前に追加:

```python
    def _paste_clipboard(self) -> None:
        text = self._clipboard.read()
        if text:
            self._text.delete("1.0", "end")
            self._text.insert("1.0", text)
            self._status_lbl.configure(text="")
        else:
            self._status_lbl.configure(text="クリップボードが空です", text_color="gray")
```

- [ ] **Step 4: `widget/main.py` の `AppController` を更新する**

ファイル先頭のimportブロック（既存 `from widget.windows.input_window import InputWindow` の後）に追加:

```python
from widget.services.clipboard_reader import ClipboardReader
from widget.services.screenshot_capture import ScreenshotCapture
```

`AppController.__init__` のインスタンス変数に追加（`self.ollama: OllamaClient | None = None` の後）:

```python
        self._clipboard: ClipboardReader | None = None
        self._screenshot: ScreenshotCapture | None = None
```

`start()` メソッドの `self.ollama = OllamaClient(...)` の直後に追加:

```python
        self._clipboard = ClipboardReader(
            get_clipboard=lambda: self._root.clipboard_get() if self._root else ""
        )
        self._screenshot = ScreenshotCapture()
```

`_show_window()` の `InputWindow(...)` 呼び出しに引数を追加:

```python
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
```

- [ ] **Step 5: ウィジェットを手動で起動してクリップボードボタンを確認する**

1. 何かのテキストをコピーしておく
2. `python -m widget.main` で起動
3. `Ctrl+Shift+Space` でウィンドウを開く
4. 「📋 クリップボード」ボタンを押してテキストボックスに内容が入ることを確認
5. 「AIで起票する →」を押して起票まで動作確認

- [ ] **Step 6: コミット**

```bash
git add widget/windows/input_window.py widget/main.py
git commit -m "feat: InputWindow にクリップボードボタンを追加"
```

---

## Task 5: InputWindow にスクリーンショットボタンを追加する

**Files:**
- Modify: `widget/windows/input_window.py`

（ボタン自体は Task 4 で配置済み。ここでは `_capture_screenshot` の実装を追加する）

- [ ] **Step 1: `_capture_screenshot` / `_do_capture` / `_on_capture_done` メソッドを追加する**

`_paste_clipboard` メソッドの直後に追加:

```python
    def _capture_screenshot(self) -> None:
        self._submit_btn.configure(state="disabled")
        self._status_lbl.configure(text="撮影中…", text_color="gray")
        self.withdraw()
        self.after(500, self._do_capture)

    def _do_capture(self) -> None:
        def _run() -> None:
            path = self._screenshot.capture()
            try:
                parsed = self._ollama.parse_image(path)
            finally:
                self._screenshot.cleanup(path)
            self.after(0, lambda p=parsed: self._on_capture_done(p))

        self.deiconify()
        threading.Thread(target=_run, daemon=True).start()

    def _on_capture_done(self, parsed: dict) -> None:
        self._submit_btn.configure(state="normal")
        self._status_lbl.configure(text="")
        self._build_confirm_panel(parsed)
```

- [ ] **Step 2: ウィジェットを手動で起動してスクリーンショットボタンを確認する**

1. デスクトップに何かテキストが見える状態にする（メモ帳など）
2. `python -m widget.main` で起動
3. `Ctrl+Shift+Space` でウィンドウを開く
4. 「📸 スクリーンショット」ボタンを押す
5. ウィンドウが0.5秒消え → 復帰後「解析中…」→ ConfirmPanel が開くことを確認
6. Ollamaが画面内容からタスク情報を抽出できることを確認

- [ ] **Step 3: コミット**

```bash
git add widget/windows/input_window.py
git commit -m "feat: InputWindow にスクリーンショット起票ボタンを追加"
```

---

## Task 6: 全テストを実行して確認する

- [ ] **Step 1: widget/ 配下のテストを全件実行する**

```
pytest widget/tests/ -v
```

期待出力（既存 + 新規 = 合計 28 件以上 passed）:
```
PASSED widget/tests/test_clipboard_reader.py::test_read_returns_clipboard_text
PASSED widget/tests/test_clipboard_reader.py::test_read_truncates_long_text
PASSED widget/tests/test_clipboard_reader.py::test_read_returns_empty_on_exception
PASSED widget/tests/test_clipboard_reader.py::test_has_content_returns_true_when_text_present
PASSED widget/tests/test_clipboard_reader.py::test_has_content_returns_false_when_empty
PASSED widget/tests/test_ollama_client.py::test_parse_image_returns_structured_dict
PASSED widget/tests/test_ollama_client.py::test_parse_image_returns_empty_on_error
PASSED widget/tests/test_ollama_client.py::test_parse_image_passes_image_path_to_ollama
PASSED widget/tests/test_screenshot_capture.py::test_capture_saves_png_and_returns_path
PASSED widget/tests/test_screenshot_capture.py::test_cleanup_removes_existing_file
PASSED widget/tests/test_screenshot_capture.py::test_cleanup_does_not_raise_if_file_missing
（既存 17 件も全 PASSED）
```

- [ ] **Step 2: 最終コミット**

```bash
git add -u
git commit -m "test: フェーズ2A 全テスト通過確認"
```
