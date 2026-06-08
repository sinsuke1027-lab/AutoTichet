# ローカルタスク入力ウィジェット MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows で Ctrl+Shift+Space を押すと即座にポップアップし、自然言語でタスクを入力 → Ollama が構造化 → FastAPI バックエンド経由で Supabase にタスクを起票する Python デスクトップウィジェットを作る。

**Architecture:** customtkinter で GUI を構築し、tkinter のメインループを維持しながら pynput でグローバルホットキーを別スレッドで監視、pystray でシステムトレイに常駐する。Ollama 呼び出しと HTTP 送信はどちらも別スレッドで実行して UI をブロックしない。バックエンドは既存 FastAPI（HuggingFace Spaces）、認証は DEV_MODE の `X-Dev-User` ヘッダー。

**Tech Stack:** Python 3.11+, customtkinter 5.2+, pynput 1.7+, httpx 0.27+, ollama 0.3+, pystray 0.19+, Pillow 10+, pytest 8+

---

## 変更ファイル一覧

| ファイル | 役割 |
|--------|------|
| `widget/__init__.py` | パッケージ宣言（空） |
| `widget/requirements.txt` | 依存ライブラリ |
| `widget/config.py` | config.json 読み書き |
| `widget/clients/__init__.py` | パッケージ宣言（空） |
| `widget/clients/backend_client.py` | FastAPI 呼び出し（ユーザー・プロジェクト取得、タスク作成） |
| `widget/clients/ollama_client.py` | Ollama 自然言語→JSON 解析 |
| `widget/windows/__init__.py` | パッケージ宣言（空） |
| `widget/windows/user_select_window.py` | 初回ユーザー選択ダイアログ |
| `widget/windows/input_window.py` | メイン入力ポップアップ + ConfirmPanel |
| `widget/main.py` | エントリーポイント・AppController |
| `widget/tests/__init__.py` | パッケージ宣言（空） |
| `widget/tests/test_config.py` | config.py テスト |
| `widget/tests/test_backend_client.py` | BackendClient テスト |
| `widget/tests/test_ollama_client.py` | OllamaClient テスト |
| `widget/tests/test_payload_builder.py` | ConfirmPanel のペイロード組み立てロジックテスト |

---

### Task 1: プロジェクト骨格 + config.py

**Files:**
- Create: `widget/__init__.py`
- Create: `widget/requirements.txt`
- Create: `widget/clients/__init__.py`
- Create: `widget/windows/__init__.py`
- Create: `widget/tests/__init__.py`
- Create: `widget/config.py`
- Create: `widget/tests/test_config.py`

- [ ] **Step 1: ディレクトリとパッケージ宣言を作成する**

PowerShell で実行:
```powershell
New-Item -ItemType Directory -Path widget/clients, widget/windows, widget/tests -Force
"" | Set-Content widget/__init__.py
"" | Set-Content widget/clients/__init__.py
"" | Set-Content widget/windows/__init__.py
"" | Set-Content widget/tests/__init__.py
```

- [ ] **Step 2: requirements.txt を作成する**

`widget/requirements.txt`:
```
customtkinter>=5.2
pynput>=1.7
httpx>=0.27
ollama>=0.3
pystray>=0.19
pillow>=10.0
pytest>=8.0
```

- [ ] **Step 3: テストを書く（先に失敗させる）**

`widget/tests/test_config.py`:
```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch


def test_load_config_creates_default_json_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        from widget.config import load_config, Config
        cfg = load_config()
    assert cfg.hotkey == "ctrl+shift+space"
    assert cfg.ollama_model == "gemma4:e4b"
    assert cfg.backend_url == ""
    assert cfg.selected_user_id == ""
    assert config_path.exists()


def test_save_and_load_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        from widget.config import load_config, save_config, Config
        cfg = Config(backend_url="https://example.hf.space", selected_user_id="alice")
        save_config(cfg)
        loaded = load_config()
    assert loaded.backend_url == "https://example.hf.space"
    assert loaded.selected_user_id == "alice"


def test_load_config_ignores_unknown_keys(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"backend_url": "https://x.com", "unknown_key": "ignore_me"}))
    with patch("widget.config.CONFIG_PATH", config_path):
        from widget.config import load_config
        cfg = load_config()
    assert cfg.backend_url == "https://x.com"
```

- [ ] **Step 4: テストが失敗することを確認する**

AutoTicket ルートで実行:
```powershell
python -m pytest widget/tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'widget.config'`

- [ ] **Step 5: config.py を実装する**

`widget/config.py`:
```python
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class Config:
    backend_url: str = ""
    selected_user_id: str = ""
    hotkey: str = "<ctrl>+<shift>+<space>"
    ollama_model: str = "gemma4:e4b"


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in known})


def save_config(cfg: Config) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
```

- [ ] **Step 6: テストが通ることを確認する**

```powershell
python -m pytest widget/tests/test_config.py -v
```
Expected:
```
test_config.py::test_load_config_creates_default_json_when_missing PASSED
test_config.py::test_save_and_load_roundtrip PASSED
test_config.py::test_load_config_ignores_unknown_keys PASSED
3 passed
```

- [ ] **Step 7: コミットする**

```powershell
git add widget/
git commit -m "feat: widget プロジェクト骨格と config.py を追加"
```

---

### Task 2: BackendClient

**Files:**
- Create: `widget/clients/backend_client.py`
- Create: `widget/tests/test_backend_client.py`

- [ ] **Step 1: テストを書く（先に失敗させる）**

`widget/tests/test_backend_client.py`:
```python
import pytest
from unittest.mock import MagicMock, patch


def _make_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


def test_get_users_returns_user_info_list():
    from widget.clients.backend_client import BackendClient, UserInfo
    raw = [
        {"user_id": "u1", "display_name": "山田 太郎", "role": "member"},
        {"user_id": "u2", "display_name": "田中 花子", "role": "admin"},
    ]
    with patch("httpx.get", return_value=_make_response(raw)):
        client = BackendClient("https://example.hf.space", "u1")
        users = client.get_users()
    assert len(users) == 2
    assert users[0] == UserInfo(user_id="u1", display_name="山田 太郎")
    assert users[1] == UserInfo(user_id="u2", display_name="田中 花子")


def test_get_projects_returns_project_info_list():
    from widget.clients.backend_client import BackendClient, ProjectInfo
    raw = [
        {"id": "p1", "name": "総務業務管理"},
        {"id": "p2", "name": "人事業務管理"},
    ]
    with patch("httpx.get", return_value=_make_response(raw)):
        client = BackendClient("https://example.hf.space", "u1")
        projects = client.get_projects()
    assert len(projects) == 2
    assert projects[0] == ProjectInfo(id="p1", name="総務業務管理")


def test_create_task_sends_correct_payload():
    from widget.clients.backend_client import BackendClient
    mock_resp = _make_response({"id": "task-uuid", "title": "テスト"})
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        client = BackendClient("https://example.hf.space", "u1")
        payload = {"title": "テスト", "priority": "medium", "source_type": "manual"}
        result = client.create_task(payload)
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["headers"]["X-Dev-User"] == "u1"
    assert call_kwargs.kwargs["json"]["title"] == "テスト"
    assert result["id"] == "task-uuid"


def test_get_projects_handles_paginated_response():
    from widget.clients.backend_client import BackendClient
    raw = {"items": [{"id": "p1", "name": "プロジェクトA"}], "total": 1}
    with patch("httpx.get", return_value=_make_response(raw)):
        client = BackendClient("https://example.hf.space", "u1")
        projects = client.get_projects()
    assert projects[0].name == "プロジェクトA"
```

- [ ] **Step 2: テストが失敗することを確認する**

```powershell
python -m pytest widget/tests/test_backend_client.py -v
```
Expected: `ModuleNotFoundError: No module named 'widget.clients.backend_client'`

- [ ] **Step 3: BackendClient を実装する**

`widget/clients/backend_client.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
import httpx


@dataclass(eq=True)
class UserInfo:
    user_id: str
    display_name: str


@dataclass(eq=True)
class ProjectInfo:
    id: str
    name: str


class BackendClient:
    def __init__(self, backend_url: str, user_id: str) -> None:
        self._base = backend_url.rstrip("/")
        self._headers = {
            "X-Dev-User": user_id,
            "Content-Type": "application/json",
        }

    def get_users(self) -> list[UserInfo]:
        resp = httpx.get(
            f"{self._base}/api/v1/users",
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return [UserInfo(u["user_id"], u["display_name"]) for u in resp.json()]

    def get_projects(self) -> list[ProjectInfo]:
        resp = httpx.get(
            f"{self._base}/api/v1/projects",
            params={"scope": "all"},
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return [ProjectInfo(p["id"], p["name"]) for p in items]

    def create_task(self, payload: dict) -> dict:
        resp = httpx.post(
            f"{self._base}/api/v1/tasks",
            json=payload,
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: テストが通ることを確認する**

```powershell
python -m pytest widget/tests/test_backend_client.py -v
```
Expected:
```
test_backend_client.py::test_get_users_returns_user_info_list PASSED
test_backend_client.py::test_get_projects_returns_project_info_list PASSED
test_backend_client.py::test_create_task_sends_correct_payload PASSED
test_backend_client.py::test_get_projects_handles_paginated_response PASSED
4 passed
```

- [ ] **Step 5: コミットする**

```powershell
git add widget/clients/backend_client.py widget/tests/test_backend_client.py
git commit -m "feat: widget BackendClient を追加"
```

---

### Task 3: OllamaClient

**Files:**
- Create: `widget/clients/ollama_client.py`
- Create: `widget/tests/test_ollama_client.py`

- [ ] **Step 1: テストを書く（先に失敗させる）**

`widget/tests/test_ollama_client.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import date


def _mock_ollama_response(content: str):
    return {"message": {"content": content}}


def test_parse_returns_structured_dict():
    from widget.clients.ollama_client import OllamaClient
    mock_content = '{"title": "〇〇の件をまとめる", "due_date": "2026-06-09", "assignee_name": "山田", "priority": "high"}'
    with patch("ollama.chat", return_value=_mock_ollama_response(mock_content)):
        client = OllamaClient(model="gemma4:e4b")
        result = client.parse("明日までに〇〇の件をまとめる 山田さんに頼む 急ぎで")
    assert result["title"] == "〇〇の件をまとめる"
    assert result["due_date"] == "2026-06-09"
    assert result["assignee_name"] == "山田"
    assert result["priority"] == "high"


def test_parse_extracts_json_from_noisy_response():
    from widget.clients.ollama_client import OllamaClient
    noisy = 'もちろんです。\n```json\n{"title": "報告書作成", "due_date": null, "assignee_name": null, "priority": "medium"}\n```'
    with patch("ollama.chat", return_value=_mock_ollama_response(noisy)):
        client = OllamaClient()
        result = client.parse("報告書を作る")
    assert result["title"] == "報告書作成"
    assert result["due_date"] is None


def test_parse_returns_empty_dict_on_ollama_error():
    from widget.clients.ollama_client import OllamaClient
    with patch("ollama.chat", side_effect=Exception("connection refused")):
        client = OllamaClient()
        result = client.parse("なんか作業する")
    assert result == {"title": None, "due_date": None, "assignee_name": None, "priority": None}


def test_parse_sends_today_date_in_system_prompt():
    from widget.clients.ollama_client import OllamaClient
    captured = {}
    def fake_chat(model, messages, options):
        captured["system"] = messages[0]["content"]
        return _mock_ollama_response('{"title": "test", "due_date": null, "assignee_name": null, "priority": null}')
    with patch("ollama.chat", side_effect=fake_chat):
        client = OllamaClient()
        client.parse("test")
    assert date.today().isoformat() in captured["system"]
```

- [ ] **Step 2: テストが失敗することを確認する**

```powershell
python -m pytest widget/tests/test_ollama_client.py -v
```
Expected: `ModuleNotFoundError: No module named 'widget.clients.ollama_client'`

- [ ] **Step 3: OllamaClient を実装する**

`widget/clients/ollama_client.py`:
```python
from __future__ import annotations
import json
from datetime import date
import ollama

_SYSTEM_PROMPT = """\
あなたはタスク管理システムへの入力を構造化するアシスタントです。
ユーザーの入力テキストから以下の JSON のみを出力してください（説明・コードブロック不要）。

今日の日付: {today}

出力形式:
{{
  "title": "タスクタイトル（必須、日本語で簡潔に）",
  "due_date": "YYYY-MM-DD または null",
  "assignee_name": "担当者の表示名または null",
  "priority": "low|medium|high|urgent または null"
}}\
"""

_EMPTY: dict = {"title": None, "due_date": None, "assignee_name": None, "priority": None}


class OllamaClient:
    def __init__(self, model: str = "gemma4:e4b") -> None:
        self.model = model

    def parse(self, text: str) -> dict:
        today = date.today().isoformat()
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT.format(today=today)},
                    {"role": "user", "content": text},
                ],
                options={"temperature": 0},
            )
            raw = response["message"]["content"].strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return dict(_EMPTY)
            return json.loads(raw[start:end])
        except Exception:
            return dict(_EMPTY)
```

- [ ] **Step 4: テストが通ることを確認する**

```powershell
python -m pytest widget/tests/test_ollama_client.py -v
```
Expected:
```
test_ollama_client.py::test_parse_returns_structured_dict PASSED
test_ollama_client.py::test_parse_extracts_json_from_noisy_response PASSED
test_ollama_client.py::test_parse_returns_empty_dict_on_ollama_error PASSED
test_ollama_client.py::test_parse_sends_today_date_in_system_prompt PASSED
4 passed
```

- [ ] **Step 5: コミットする**

```powershell
git add widget/clients/ollama_client.py widget/tests/test_ollama_client.py
git commit -m "feat: widget OllamaClient を追加"
```

---

### Task 4: ペイロード組み立てロジック（テスト可能な純粋関数として切り出し）

**Files:**
- Create: `widget/payload_builder.py`
- Create: `widget/tests/test_payload_builder.py`

InputWindow の ConfirmPanel から送信ペイロードを作る処理を、GUI に依存しない純粋関数として切り出してテストする。

- [ ] **Step 1: テストを書く（先に失敗させる）**

`widget/tests/test_payload_builder.py`:
```python
import pytest
from widget.clients.backend_client import UserInfo, ProjectInfo


def test_build_payload_basic():
    from widget.payload_builder import build_payload
    users = [UserInfo("u1", "山田 太郎"), UserInfo("u2", "田中 花子")]
    projects = [ProjectInfo("p1", "総務業務管理")]
    result = build_payload(
        title="報告書を書く",
        due_date_str="2026-06-10",
        assignee_display="山田 太郎",
        project_name="総務業務管理",
        priority_jp="高",
        users=users,
        projects=projects,
    )
    assert result["title"] == "報告書を書く"
    assert result["due_date"] == "2026-06-10"
    assert result["assignee_id"] == "u1"
    assert result["project_id"] == "p1"
    assert result["priority"] == "high"
    assert result["source_type"] == "manual"


def test_build_payload_no_assignee_no_project():
    from widget.payload_builder import build_payload
    result = build_payload(
        title="タスクA",
        due_date_str="",
        assignee_display="（なし）",
        project_name="（なし）",
        priority_jp="中",
        users=[],
        projects=[],
    )
    assert result["assignee_id"] is None
    assert result["project_id"] is None
    assert result["due_date"] is None
    assert result["priority"] == "medium"


def test_resolve_assignee_case_insensitive_partial_match():
    from widget.payload_builder import resolve_assignee
    users = [UserInfo("u1", "Tanaka Hanako"), UserInfo("u2", "Yamada Taro")]
    assert resolve_assignee("tanaka", users) == "u1"
    assert resolve_assignee("YAMADA", users) == "u2"
    assert resolve_assignee("存在しない", users) is None


def test_priority_map_all_values():
    from widget.payload_builder import jp_to_priority
    assert jp_to_priority("低") == "low"
    assert jp_to_priority("中") == "medium"
    assert jp_to_priority("高") == "high"
    assert jp_to_priority("緊急") == "urgent"
    assert jp_to_priority("不明") == "medium"
```

- [ ] **Step 2: テストが失敗することを確認する**

```powershell
python -m pytest widget/tests/test_payload_builder.py -v
```
Expected: `ModuleNotFoundError: No module named 'widget.payload_builder'`

- [ ] **Step 3: payload_builder.py を実装する**

`widget/payload_builder.py`:
```python
from __future__ import annotations
from widget.clients.backend_client import UserInfo, ProjectInfo

_PRIORITY_MAP = {"低": "low", "中": "medium", "高": "high", "緊急": "urgent"}


def jp_to_priority(jp: str) -> str:
    return _PRIORITY_MAP.get(jp, "medium")


def resolve_assignee(name: str, users: list[UserInfo]) -> str | None:
    lower = name.lower()
    for u in users:
        if lower in u.display_name.lower():
            return u.user_id
    return None


def resolve_project(name: str, projects: list[ProjectInfo]) -> str | None:
    for p in projects:
        if p.name == name:
            return p.id
    return None


def build_payload(
    title: str,
    due_date_str: str,
    assignee_display: str,
    project_name: str,
    priority_jp: str,
    users: list[UserInfo],
    projects: list[ProjectInfo],
) -> dict:
    assignee_id = (
        None
        if assignee_display in ("（なし）", "")
        else resolve_assignee(assignee_display, users)
    )
    project_id = (
        None
        if project_name in ("（なし）", "")
        else resolve_project(project_name, projects)
    )
    return {
        "title": title,
        "due_date": due_date_str.strip() or None,
        "assignee_id": assignee_id,
        "project_id": project_id,
        "priority": jp_to_priority(priority_jp),
        "source_type": "manual",
    }
```

- [ ] **Step 4: テストが通ることを確認する**

```powershell
python -m pytest widget/tests/test_payload_builder.py -v
```
Expected:
```
test_payload_builder.py::test_build_payload_basic PASSED
test_payload_builder.py::test_build_payload_no_assignee_no_project PASSED
test_payload_builder.py::test_resolve_assignee_case_insensitive_partial_match PASSED
test_payload_builder.py::test_priority_map_all_values PASSED
4 passed
```

- [ ] **Step 5: コミットする**

```powershell
git add widget/payload_builder.py widget/tests/test_payload_builder.py
git commit -m "feat: widget payload_builder を追加（テスト可能な純粋関数）"
```

---

### Task 5: UserSelectWindow

GUI コンポーネントはユニットテスト不可のため、手動確認で代替する。

**Files:**
- Create: `widget/windows/user_select_window.py`

- [ ] **Step 1: UserSelectWindow を実装する**

`widget/windows/user_select_window.py`:
```python
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
        self.grab_set()  # モーダル動作

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
```

- [ ] **Step 2: 手動で動作確認する（自動テストなし）**

`widget/` ディレクトリで以下のスクリプトを一時的に実行して確認:
```python
# widget/_test_user_select.py（実行後に削除）
import customtkinter as ctk
from widget.clients.backend_client import UserInfo
from widget.config import Config
from widget.windows.user_select_window import UserSelectWindow

ctk.set_appearance_mode("dark")
root = ctk.CTk()
root.withdraw()
dummy_users = [UserInfo("u1", "山田 太郎"), UserInfo("u2", "田中 花子")]
cfg = Config(backend_url="https://test.hf.space")
win = UserSelectWindow(root, cfg, dummy_users)
root.wait_window(win)
print(f"選択されたユーザーID: {cfg.selected_user_id}")
root.destroy()
```

```powershell
cd widget
python _test_user_select.py
```

確認項目:
- ダイアログが表示される ✅
- ドロップダウンにユーザーが表示される ✅
- 「決定」を押すと `selected_user_id` が設定されてウィンドウが閉じる ✅

確認後 `_test_user_select.py` を削除する。

- [ ] **Step 3: コミットする**

```powershell
git add widget/windows/user_select_window.py
git commit -m "feat: widget UserSelectWindow を追加"
```

---

### Task 6: InputWindow + ConfirmPanel

**Files:**
- Create: `widget/windows/input_window.py`

- [ ] **Step 1: InputWindow を実装する**

`widget/windows/input_window.py`:
```python
from __future__ import annotations
import threading
import customtkinter as ctk
from widget.clients.backend_client import BackendClient, UserInfo, ProjectInfo
from widget.clients.ollama_client import OllamaClient
from widget.config import Config
from widget.payload_builder import build_payload, jp_to_priority


_PRIORITY_OPTIONS = ["低", "中", "高", "緊急"]
_NO_SELECT = "（なし）"


class InputWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        config: Config,
        ollama: OllamaClient,
        backend: BackendClient,
        users: list[UserInfo],
        projects: list[ProjectInfo],
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._ollama = ollama
        self._backend = backend
        self._users = users
        self._projects = projects

        self.title("AutoTicket")
        self.geometry("440x190")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._build_input_panel()

    # ──────────────────────────────
    # 入力パネル（初期表示）
    # ──────────────────────────────
    def _build_input_panel(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("440x190")

        # ユーザー選択行
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(top, text="👤").pack(side="left")
        user_names = [u.display_name for u in self._users]
        current = next(
            (u.display_name for u in self._users if u.user_id == self._config.selected_user_id),
            user_names[0] if user_names else "",
        )
        self._user_combo = ctk.CTkComboBox(top, values=user_names, width=220, state="readonly")
        self._user_combo.set(current)
        self._user_combo.pack(side="left", padx=8)

        # テキスト入力欄
        self._text = ctk.CTkTextbox(self, height=70, width=410)
        self._text.pack(padx=16, pady=4)
        self._text.focus()

        # ボタン行
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))
        self._status_lbl = ctk.CTkLabel(btn_row, text="", text_color="gray")
        self._status_lbl.pack(side="left")
        self._submit_btn = ctk.CTkButton(btn_row, text="AIで起票する →", command=self._on_ai_submit)
        self._submit_btn.pack(side="right")

    # ──────────────────────────────
    # AI 解析 → ConfirmPanel 表示
    # ──────────────────────────────
    def _on_ai_submit(self) -> None:
        text = self._text.get("1.0", "end").strip()
        if not text:
            return
        self._submit_btn.configure(state="disabled", text="解析中…")
        self._status_lbl.configure(text="Ollama で解析しています…")

        def _run() -> None:
            parsed = self._ollama.parse(text)
            self.after(0, lambda: self._build_confirm_panel(parsed))

        threading.Thread(target=_run, daemon=True).start()

    # ──────────────────────────────
    # ConfirmPanel（インライン展開）
    # ──────────────────────────────
    def _build_confirm_panel(self, parsed: dict) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.geometry("440x330")
        self.title("AutoTicket - 確認")

        ctk.CTkLabel(
            self, text="✅ 解析結果（編集できます）", font=ctk.CTkFont(weight="bold")
        ).pack(pady=(12, 4))

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", padx=16, pady=4)

        def _row(label: str, widget: ctk.CTkBaseClass) -> ctk.CTkBaseClass:
            r = ctk.CTkFrame(frame, fg_color="transparent")
            r.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(r, text=label, width=90, anchor="w").pack(side="left")
            widget.pack(side="left", fill="x", expand=True)
            return widget

        # タイトル
        self._title_entry = ctk.CTkEntry(frame, placeholder_text="タスクタイトル（必須）")
        _row("タイトル", self._title_entry)
        title_val = parsed.get("title") or ""
        self._title_entry.insert(0, title_val)
        if not title_val:
            self._title_entry.configure(border_color="red")

        # 期限
        self._due_entry = ctk.CTkEntry(frame, placeholder_text="YYYY-MM-DD（空欄可）")
        _row("期限", self._due_entry)
        self._due_entry.insert(0, parsed.get("due_date") or "")

        # 担当者
        user_names = [_NO_SELECT] + [u.display_name for u in self._users]
        assignee_raw = parsed.get("assignee_name") or ""
        matched = next(
            (u.display_name for u in self._users if assignee_raw.lower() in u.display_name.lower()),
            _NO_SELECT,
        )
        self._assignee_combo = ctk.CTkComboBox(frame, values=user_names, state="readonly")
        _row("担当者", self._assignee_combo)
        self._assignee_combo.set(matched)

        # プロジェクト
        proj_names = [_NO_SELECT] + [p.name for p in self._projects]
        self._project_combo = ctk.CTkComboBox(frame, values=proj_names, state="readonly")
        _row("プロジェクト", self._project_combo)
        self._project_combo.set(_NO_SELECT)

        # 優先度
        priority_inv = {"low": "低", "medium": "中", "high": "高", "urgent": "緊急"}
        priority_jp = priority_inv.get(parsed.get("priority") or "", "中")
        self._priority_combo = ctk.CTkComboBox(frame, values=_PRIORITY_OPTIONS, state="readonly", width=120)
        _row("優先度", self._priority_combo)
        self._priority_combo.set(priority_jp)

        # ボタン行
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkButton(btn_row, text="キャンセル", width=100, command=self._build_input_panel).pack(side="left")
        self._send_btn = ctk.CTkButton(btn_row, text="送信する", command=self._on_send)
        self._send_btn.pack(side="right")

        self._error_lbl = ctk.CTkLabel(self, text="", text_color="red")
        self._error_lbl.pack(pady=(0, 8))

    # ──────────────────────────────
    # 送信
    # ──────────────────────────────
    def _on_send(self) -> None:
        title = self._title_entry.get().strip()
        if not title:
            self._title_entry.configure(border_color="red")
            self._error_lbl.configure(text="タイトルは必須です")
            return

        payload = build_payload(
            title=title,
            due_date_str=self._due_entry.get(),
            assignee_display=self._assignee_combo.get(),
            project_name=self._project_combo.get(),
            priority_jp=self._priority_combo.get(),
            users=self._users,
            projects=self._projects,
        )
        self._send_btn.configure(state="disabled", text="送信中…")

        def _run() -> None:
            try:
                self._backend.create_task(payload)
                self.after(0, self._on_success)
            except Exception as exc:
                self.after(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=_run, daemon=True).start()

    def _on_success(self) -> None:
        self.destroy()

    def _on_error(self, msg: str) -> None:
        self._error_lbl.configure(text=f"送信エラー: {msg}")
        self._send_btn.configure(state="normal", text="送信する")
```

- [ ] **Step 2: 手動で InputWindow を確認する**

`widget/_test_input_window.py`（確認後削除）:
```python
import customtkinter as ctk
from unittest.mock import MagicMock
from widget.clients.backend_client import UserInfo, ProjectInfo
from widget.clients.ollama_client import OllamaClient
from widget.clients.backend_client import BackendClient
from widget.config import Config
from widget.windows.input_window import InputWindow

ctk.set_appearance_mode("dark")
root = ctk.CTk()
root.withdraw()

users = [UserInfo("u1", "山田 太郎"), UserInfo("u2", "田中 花子")]
projects = [ProjectInfo("p1", "総務業務管理"), ProjectInfo("p2", "人事業務管理")]
cfg = Config(backend_url="https://test.hf.space", selected_user_id="u1")

ollama = MagicMock()
ollama.parse.return_value = {"title": "報告書を書く", "due_date": "2026-06-10", "assignee_name": "山田", "priority": "high"}

backend = MagicMock()
backend.create_task.return_value = {"id": "task-uuid"}

win = InputWindow(root, cfg, ollama, backend, users, projects)
root.mainloop()
```

```powershell
cd .. # AutoTicket ルートから
python -m widget._test_input_window 2>$null
# または widget ディレクトリ内で
# python _test_input_window.py
```

確認項目:
- ポップアップが表示される ✅
- テキスト入力後「AIで起票する」押下で ConfirmPanel が展開される ✅
- 解析済み値がフィールドに反映される ✅
- 「キャンセル」で入力画面に戻る ✅
- 「送信する」でウィンドウが閉じる ✅
- タイトルが空のとき赤枠になりエラー表示される ✅

確認後 `_test_input_window.py` を削除する。

- [ ] **Step 3: コミットする**

```powershell
git add widget/windows/input_window.py
git commit -m "feat: widget InputWindow + ConfirmPanel を追加"
```

---

### Task 7: main.py（AppController・ホットキー・システムトレイ）

**Files:**
- Create: `widget/main.py`

- [ ] **Step 1: main.py を実装する**

`widget/main.py`:
```python
from __future__ import annotations
import sys
import threading
import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray
from pynput import keyboard

from widget.config import load_config, Config
from widget.clients.backend_client import BackendClient, UserInfo, ProjectInfo
from widget.clients.ollama_client import OllamaClient
from widget.windows.user_select_window import UserSelectWindow
from widget.windows.input_window import InputWindow


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

    # ──────────────────────────────
    # 起動
    # ──────────────────────────────
    def start(self) -> None:
        if not self.config.backend_url:
            print(
                "エラー: config.json の backend_url が未設定です。\n"
                "widget/config.json を編集して HuggingFace Spaces の URL を設定してください。"
            )
            sys.exit(1)

        # 初期接続（ユーザー一覧取得用に anonymous ヘッダーで OK）
        tmp_client = BackendClient(self.config.backend_url, self.config.selected_user_id or "anonymous")
        try:
            self.users = tmp_client.get_users()
            self.projects = tmp_client.get_projects()
        except Exception as exc:
            print(f"バックエンド接続エラー: {exc}")
            sys.exit(1)

        # tkinter メインループ用の隠し root
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._root = ctk.CTk()
        self._root.withdraw()

        # 初回ユーザー選択
        if not self.config.selected_user_id:
            win = UserSelectWindow(self._root, self.config, self.users)
            self._root.wait_window(win)
            if not self.config.selected_user_id:
                print("ユーザーが選択されませんでした。終了します。")
                sys.exit(0)

        self.backend = BackendClient(self.config.backend_url, self.config.selected_user_id)
        self.ollama = OllamaClient(model=self.config.ollama_model)

        # ホットキーリスナーをバックグラウンドで起動
        threading.Thread(target=self._start_hotkey_listener, daemon=True).start()

        # システムトレイをバックグラウンドで起動
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

    # ──────────────────────────────
    # ホットキー
    # ──────────────────────────────
    def _start_hotkey_listener(self) -> None:
        def on_activate() -> None:
            if self._root:
                self._root.after(0, self._show_window)

        with keyboard.GlobalHotKeys({self.config.hotkey: on_activate}) as h:
            h.join()

    # ──────────────────────────────
    # ウィンドウ表示
    # ──────────────────────────────
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
        )
        win.protocol("WM_DELETE_WINDOW", lambda: self._on_window_close(win))

    def _on_window_close(self, win: InputWindow) -> None:
        self._window_open = False
        win.destroy()

    # ──────────────────────────────
    # 終了
    # ──────────────────────────────
    def _quit(self) -> None:
        if self._root:
            self._root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    AppController().start()
```

- [ ] **Step 2: 全テストが通ることを確認する**

AutoTicket ルートで実行:
```powershell
python -m pytest widget/tests/ -v
```
Expected:
```
widget/tests/test_config.py::test_load_config_creates_default_json_when_missing PASSED
widget/tests/test_config.py::test_save_and_load_roundtrip PASSED
widget/tests/test_config.py::test_load_config_ignores_unknown_keys PASSED
widget/tests/test_backend_client.py::test_get_users_returns_user_info_list PASSED
widget/tests/test_backend_client.py::test_get_projects_returns_project_info_list PASSED
widget/tests/test_backend_client.py::test_create_task_sends_correct_payload PASSED
widget/tests/test_backend_client.py::test_get_projects_handles_paginated_response PASSED
widget/tests/test_ollama_client.py::test_parse_returns_structured_dict PASSED
widget/tests/test_ollama_client.py::test_parse_extracts_json_from_noisy_response PASSED
widget/tests/test_ollama_client.py::test_parse_returns_empty_dict_on_ollama_error PASSED
widget/tests/test_ollama_client.py::test_parse_sends_today_date_in_system_prompt PASSED
widget/tests/test_payload_builder.py::test_build_payload_basic PASSED
widget/tests/test_payload_builder.py::test_build_payload_no_assignee_no_project PASSED
widget/tests/test_payload_builder.py::test_resolve_assignee_case_insensitive_partial_match PASSED
widget/tests/test_payload_builder.py::test_priority_map_all_values PASSED
15 passed
```

- [ ] **Step 3: コミットする**

```powershell
git add widget/main.py
git commit -m "feat: widget main.py を追加（AppController・ホットキー・システムトレイ）"
```

---

### Task 8: 依存インストール + エンドツーエンド動作確認

**Files:** なし（インストールと手動確認のみ）

- [ ] **Step 1: 依存ライブラリをインストールする**

```powershell
cd widget
pip install -r requirements.txt
```

Expected: 全パッケージが正常にインストールされる。

- [ ] **Step 2: config.json に backend_url を設定する**

`widget/config.json` が存在しない場合は `python -m widget.main` を一度実行すると自動生成される（すぐ `Ctrl+C` で終了）。その後 `backend_url` を実際の HuggingFace Spaces の URL に書き換える:

```json
{
  "backend_url": "https://YOUR-SPACE.hf.space",
  "selected_user_id": "",
  "hotkey": "<ctrl>+<shift>+<space>",
  "ollama_model": "gemma4:e4b"
}
```

**注意:** pynput のホットキー形式は `<ctrl>+<shift>+<space>` （山括弧あり）。

- [ ] **Step 3: バックエンドが起動していることを確認する**

PowerShell で確認:
```powershell
curl "https://YOUR-SPACE.hf.space/api/v1/users" -H "X-Dev-User: your-user-id"
```
Expected: ユーザー一覧の JSON が返る。

- [ ] **Step 4: ウィジェットを起動する**

AutoTicket ルートで実行:
```powershell
python -m widget.main
```

初回起動確認:
- ユーザー選択ダイアログが表示される ✅
- ユーザーを選択して「決定」を押すと消える ✅
- タスクバーにトレイアイコンが表示される ✅
- コンソールに `AutoTicket 起動完了。<ctrl>+<shift>+<space> でタスク入力ウィンドウを開けます。` と表示される ✅

- [ ] **Step 5: タスク起票フローをテストする**

1. `Ctrl+Shift+Space` を押す → InputWindow がポップアップする ✅
2. 「明日までに報告書をまとめる、山田さんに頼む」と入力して「AIで起票する」を押す ✅
3. ConfirmPanel が展開され、解析結果が表示される ✅
4. 担当者・プロジェクトを確認して「送信する」を押す ✅
5. ウィンドウが閉じる ✅
6. AutoTicket の `/board` または `/schedule` で新しいタスクが表示される ✅

- [ ] **Step 6: Ollama 未起動時のフォールバックをテストする**

Ollama を停止した状態でフロー実行。
確認: ConfirmPanel が空フォームで表示され、手動入力→送信ができる ✅

- [ ] **Step 7: 最終コミット**

```powershell
git add widget/config.json  # .gitignore に追加する場合はスキップ
git commit -m "feat: widget MVP 完成"
```

**補足: config.json を .gitignore に追加する場合**（推奨。backend_url などの情報をリポジトリに含めない）:
```powershell
Add-Content .gitignore "`nwidget/config.json"
git add .gitignore
git commit -m "chore: widget/config.json を .gitignore に追加"
```

---

## 動作確認チェックリスト（完了基準）

| 確認項目 | 方法 |
|---------|------|
| 全ユニットテスト 15 件パス | `python -m pytest widget/tests/ -v` |
| 初回起動でユーザー選択ダイアログが出る | 手動 |
| Ctrl+Shift+Space でポップアップする | 手動 |
| 自然言語からタイトル・期限・担当者が解析される | 手動 |
| ConfirmPanel で編集・送信できる | 手動 |
| バックエンドにタスクが作成される | AutoTicket の Board で確認 |
| Ollama 未起動でも手動フォームで送信できる | 手動 |
| システムトレイから終了できる | 手動 |
