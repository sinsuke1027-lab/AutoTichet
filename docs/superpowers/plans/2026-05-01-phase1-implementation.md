# AutoTicket Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Outlookメール・Teams会議議事録からLangGraphエージェントがタスクを自動抽出し、visibility（private/team/all）に応じてMicrosoft To Do / Planner へ自動起票するFastAPIサービスを構築する。

**Architecture:** FastAPIアプリがAPSchedulerでGraph APIをポーリングし、未処理メッセージをLangGraphエージェントへ渡す。エージェントは機密度分類→タスク抽出→担当者照合→信頼スコア算出→承認ルーティングの順に処理し、SQLiteで処理済みIDを管理する。LLMプロバイダーはProtocolインターフェースで抽象化し、.envの設定変更だけでOllama/Claude/Gemini/Azure OpenAIを切り替え可能にする。

**Tech Stack:** Python 3.11+, FastAPI, LangGraph 0.2+, Pydantic v2, pydantic-settings, MSAL, httpx, aiosqlite, APScheduler, anthropic, google-generativeai, openai, pytest, pytest-asyncio, ruff, mypy

---

## ⚠️ 実装の2段階構成

| Part | 内容 | 前提条件 |
|------|------|---------|
| **Part A** (Task 1〜15) | LLM・エージェント・FastAPI本体 | Python環境のみ（今すぐ実装可能） |
| **Part B** (Task 16〜23) | Graph API連携・Planner/To Do起票 | Azure ADアプリ登録完了 + .env設定済み |

---

## ファイル構造

```
src/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI + APScheduler
│   └── routers/
│       ├── __init__.py
│       ├── health.py
│       └── tasks.py
├── agents/
│   ├── __init__.py
│   ├── graph.py                 # LangGraph グラフ定義
│   └── nodes.py                 # 各ノード関数
├── connectors/
│   ├── __init__.py
│   ├── graph_api.py             # Graph API クライアント (Part B)
│   ├── planner.py               # Planner 起票 (Part B)
│   └── todo.py                  # To Do 起票 (Part B)
├── models/
│   ├── __init__.py
│   ├── task.py                  # ExtractedTask, SensitivityResult
│   └── config.py                # Settings (pydantic-settings)
├── providers/
│   ├── __init__.py
│   ├── base.py                  # LLMProvider Protocol
│   ├── ollama.py
│   ├── claude.py
│   ├── gemini.py
│   ├── azure_openai.py
│   └── factory.py
└── services/
    ├── __init__.py
    ├── approval.py              # 信頼スコア→承認フロー分岐
    ├── classifier.py            # 機密度分類
    ├── routing.py               # visibility → 起票先ルーティング
    └── state.py                 # SQLite 処理済みID管理

tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_state.py
│   ├── test_classifier.py
│   ├── test_providers.py
│   ├── test_approval.py
│   ├── test_routing.py
│   └── test_agent.py
└── integration/
    ├── __init__.py
    └── test_graph_api.py        # Graph API申請後に有効化
```

---

## Part A: Graph API非依存（今すぐ実装可能）

---

### Task 1: プロジェクトブートストラップ

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `src/__init__.py` (と全サブパッケージの `__init__.py`)
- Create: `tests/__init__.py` (と全サブパッケージの `__init__.py`)

- [ ] **Step 1: requirements.txt を作成する**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
langgraph>=0.2.28
langchain-core>=0.3.0
msal>=1.31.0
httpx>=0.27.0
aiosqlite>=0.20.0
apscheduler>=3.10.4
anthropic>=0.34.0
google-generativeai>=0.8.0
openai>=1.40.0
```

- [ ] **Step 2: requirements-dev.txt を作成する**

```
pytest>=8.3.0
pytest-asyncio>=0.23.0
pytest-mock>=3.14.0
mypy>=1.11.0
ruff>=0.6.0
```

- [ ] **Step 3: 全 __init__.py を作成する**

```powershell
$base = "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket"
$packages = @(
  "src","src\api","src\api\routers","src\agents",
  "src\connectors","src\models","src\providers","src\services",
  "tests","tests\unit","tests\integration"
)
foreach ($p in $packages) {
  New-Item -Force -Path "$base\$p\__init__.py" -ItemType File | Out-Null
}
Write-Host "Done"
```

- [ ] **Step 4: 仮想環境をセットアップして依存関係をインストールする**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 5: pytest が動くことを確認する**

```powershell
pytest tests/ -v
```

Expected: `no tests ran` または `0 passed`（エラーなし）

- [ ] **Step 6: コミット**

```powershell
git add requirements.txt requirements-dev.txt src/ tests/
git commit -m "chore: プロジェクト依存関係とパッケージ構造を初期化"
```

---

### Task 2: Pydantic モデル定義

**Files:**
- Create: `src/models/task.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_models.py`:
```python
import pytest
from datetime import date
from src.models.task import ExtractedTask, SensitivityResult


def test_extracted_task_defaults():
    task = ExtractedTask(
        is_task=True,
        title="資料を作成する",
        confidence_score=0.9,
        source_type="email",
        source_id="msg-001",
    )
    assert task.visibility == "team"
    assert task.priority == "medium"
    assert task.category == "その他"
    assert task.assignee_user_id is None


def test_extracted_task_rejects_invalid_score():
    with pytest.raises(ValueError):
        ExtractedTask(
            is_task=True,
            title="test",
            confidence_score=1.5,
            source_type="email",
            source_id="msg-001",
        )


def test_sensitivity_result_pattern_a():
    result = SensitivityResult(
        label="pattern_a",
        reason="一般業務連絡",
        detected_keywords=[],
    )
    assert result.label == "pattern_a"


def test_sensitivity_result_pattern_b():
    result = SensitivityResult(
        label="pattern_b",
        reason="給与情報を含む",
        detected_keywords=["給与"],
    )
    assert result.detected_keywords == ["給与"]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.models.task'`

- [ ] **Step 3: モデルを実装する**

`src/models/task.py`:
```python
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class ExtractedTask(BaseModel):
    is_task: bool
    title: str = Field(min_length=1, max_length=200)
    assignee_user_id: str | None = None
    assignee_name: str | None = None
    department_id: str | None = None
    deadline: date | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    category: Literal["HR", "IT", "総務", "その他"] = "その他"
    visibility: Literal["private", "team", "all"] = "team"
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot"]
    source_id: str


class SensitivityResult(BaseModel):
    label: Literal["pattern_a", "pattern_b"]
    reason: str
    detected_keywords: list[str]
```

- [ ] **Step 4: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_models.py -v
```

Expected: `4 passed`

- [ ] **Step 5: コミット**

```powershell
git add src/models/task.py tests/unit/test_models.py
git commit -m "feat: ExtractedTask・SensitivityResultモデルを追加"
```

---

### Task 3: Config（pydantic-settings）

**Files:**
- Create: `src/models/config.py`

- [ ] **Step 1: config.py を実装する**（テスト不要：設定値の読み込みはE2Eで検証）

`src/models/config.py`:
```python
from typing import Literal
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Azure AD
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # Microsoft Planner
    planner_group_id: str = ""
    planner_plan_id: str = ""
    company_wide_plan_id: str = ""

    # Langfuse
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # ポーリング
    polling_interval_seconds: int = 300
    auto_create_threshold: float = 0.8
    manual_review_threshold: float = 0.5

    # LLMプロバイダー
    llm_provider: Literal["ollama", "claude", "gemini", "azure_openai"] = "ollama"
    llm_vision_provider: Literal["ollama", "claude", "gemini", "azure_openai"] = "ollama"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_vision_model: str = "llama3.2-vision"

    # Claude
    anthropic_api_key: str = ""

    # Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: コミット**

```powershell
git add src/models/config.py
git commit -m "feat: pydantic-settingsでSettings設定クラスを追加"
```

---

### Task 4: SQLite 処理済みID管理

**Files:**
- Create: `src/services/state.py`
- Create: `tests/unit/test_state.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_state.py`:
```python
import pytest
from pathlib import Path
from src.services.state import init_db, is_processed, mark_processed, unmark_processed

TEST_DB = Path("data/test_processed.db")


@pytest.fixture(autouse=True)
async def clean_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.services.state as state_mod
    monkeypatch.setattr(state_mod, "DB_PATH", tmp_path / "test.db")
    await init_db()


async def test_new_message_is_not_processed() -> None:
    assert not await is_processed("msg-001")


async def test_mark_and_check_processed() -> None:
    await mark_processed("msg-001", "email")
    assert await is_processed("msg-001")


async def test_unmark_processed() -> None:
    await mark_processed("msg-002", "email")
    await unmark_processed("msg-002")
    assert not await is_processed("msg-002")


async def test_double_mark_is_idempotent() -> None:
    await mark_processed("msg-003", "email")
    await mark_processed("msg-003", "email")  # 重複しても例外なし
    assert await is_processed("msg-003")
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.services.state'`

- [ ] **Step 3: state.py を実装する**

`src/services/state.py`:
```python
import aiosqlite
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/processed.db")


async def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def is_processed(message_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?",
            (message_id,),
        )
        return await cursor.fetchone() is not None


async def mark_processed(message_id: str, source_type: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO processed_messages VALUES (?, ?, ?)",
            (message_id, source_type, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def unmark_processed(message_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM processed_messages WHERE message_id = ?",
            (message_id,),
        )
        await db.commit()
```

- [ ] **Step 4: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_state.py -v
```

Expected: `4 passed`

- [ ] **Step 5: コミット**

```powershell
git add src/services/state.py tests/unit/test_state.py
git commit -m "feat: SQLite処理済みメッセージID管理サービスを追加"
```

---

### Task 5: LLMプロバイダー基底クラス + Ollamaプロバイダー

**Files:**
- Create: `src/providers/base.py`
- Create: `src/providers/ollama.py`
- Create: `tests/unit/test_providers.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_providers.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.ollama import OllamaProvider, OllamaVisionProvider


def test_ollama_provider_implements_protocol() -> None:
    provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:14b")
    assert isinstance(provider, LLMProvider)


def test_ollama_vision_provider_implements_protocol() -> None:
    provider = OllamaVisionProvider(host="http://localhost:11434", vision_model="llama3.2-vision")
    assert isinstance(provider, VisionLLMProvider)


async def test_ollama_extract_tasks_returns_list(respx_mock: pytest.fixture) -> None:
    import respx, httpx
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, json={
            "message": {
                "content": '[{"is_task":true,"title":"資料を作成する","assignee_name":null,'
                           '"deadline":null,"priority":"medium","category":"その他",'
                           '"visibility":"team","confidence_score":0.85}]'
            }
        })
    )
    provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:14b")
    tasks = await provider.extract_tasks("田中さん、来週までに資料を作成してください", "email")
    assert len(tasks) == 1
    assert tasks[0].title == "資料を作成する"
    assert tasks[0].confidence_score == 0.85
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_providers.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: base.py を実装する**

`src/providers/base.py`:
```python
from typing import Protocol, runtime_checkable
from src.models.task import ExtractedTask


@runtime_checkable
class LLMProvider(Protocol):
    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        ...


@runtime_checkable
class VisionLLMProvider(Protocol):
    async def analyze_image(self, image: bytes, comment: str) -> str:
        ...
```

- [ ] **Step 4: ollama.py を実装する**

`src/providers/ollama.py`:
```python
import json
import httpx
from src.models.task import ExtractedTask
from src.providers.base import LLMProvider, VisionLLMProvider

_EXTRACT_SYSTEM = """あなたはタスク抽出の専門家です。与えられた日本語テキストからタスクを抽出し、JSONのみ返してください。

出力フォーマット:
[
  {
    "is_task": true,
    "title": "タスクタイトル（1〜200文字）",
    "assignee_name": "担当者名またはnull",
    "deadline": "YYYY-MM-DD形式またはnull",
    "priority": "high|medium|low",
    "category": "HR|IT|総務|その他",
    "visibility": "private|team|all",
    "confidence_score": 0.0〜1.0の数値
  }
]

タスクがない場合は空リスト [] を返してください。"""


class OllamaProvider:
    def __init__(self, host: str, model: str) -> None:
        self._host = host
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _EXTRACT_SYSTEM},
                        {"role": "user", "content": f"以下のテキストからタスクを抽出:\n\n{text}"},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            resp.raise_for_status()
            raw = json.loads(resp.json()["message"]["content"])
            return [
                ExtractedTask(**t, source_type=source_type, source_id="")
                for t in raw
                if t.get("is_task")
            ]


class OllamaVisionProvider:
    def __init__(self, host: str, vision_model: str) -> None:
        self._host = host
        self._vision_model = vision_model

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import base64
        b64 = base64.b64encode(image).decode()
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"画像の内容を説明してください。補足コメント: {comment}",
                            "images": [b64],
                        }
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return str(resp.json()["message"]["content"])
```

- [ ] **Step 5: respx をインストールしてテストを実行する**

```powershell
pip install respx
pytest tests/unit/test_providers.py::test_ollama_provider_implements_protocol tests/unit/test_providers.py::test_ollama_vision_provider_implements_protocol -v
```

Expected: `2 passed`

- [ ] **Step 6: コミット**

```powershell
git add src/providers/base.py src/providers/ollama.py tests/unit/test_providers.py
git commit -m "feat: LLMProvider基底Protocol + Ollamaプロバイダーを追加"
```

---

### Task 6: Claude / Gemini / Azure OpenAI プロバイダー

**Files:**
- Create: `src/providers/claude.py`
- Create: `src/providers/gemini.py`
- Create: `src/providers/azure_openai.py`

- [ ] **Step 1: claude.py を実装する**

`src/providers/claude.py`:
```python
import json
import anthropic
from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": f"以下のテキストからタスクを抽出:\n\n{text}"}],
        )
        raw = json.loads(msg.content[0].text)
        return [
            ExtractedTask(**t, source_type=source_type, source_id="")
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import base64
        b64 = base64.b64encode(image).decode()
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": f"画像の内容を説明してください。補足コメント: {comment}"},
                ],
            }],
        )
        return str(msg.content[0].text)
```

- [ ] **Step 2: gemini.py を実装する**

`src/providers/gemini.py`:
```python
import json
import google.generativeai as genai
from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro") -> None:
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model,
            system_instruction=_EXTRACT_SYSTEM,
        )

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._model.generate_content_async(
            f"以下のテキストからタスクを抽出:\n\n{text}",
            generation_config={"response_mime_type": "application/json"},
        )
        raw = json.loads(resp.text)
        return [
            ExtractedTask(**t, source_type=source_type, source_id="")
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import PIL.Image
        import io
        img = PIL.Image.open(io.BytesIO(image))
        resp = await self._model.generate_content_async(
            [img, f"画像の内容を説明してください。補足コメント: {comment}"]
        )
        return str(resp.text)
```

- [ ] **Step 3: azure_openai.py を実装する**

`src/providers/azure_openai.py`:
```python
import json
from openai import AsyncAzureOpenAI
from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM


class AzureOpenAIProvider:
    def __init__(self, api_key: str, endpoint: str, deployment: str) -> None:
        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2024-08-01-preview",
        )
        self._deployment = deployment

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": f"以下のテキストからタスクを抽出:\n\n{text}"},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content or "[]")
        if isinstance(raw, dict):
            raw = raw.get("tasks", [])
        return [
            ExtractedTask(**t, source_type=source_type, source_id="")
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        import base64
        b64 = base64.b64encode(image).decode()
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": f"画像の内容を説明してください。補足コメント: {comment}"},
                ],
            }],
        )
        return str(resp.choices[0].message.content)
```

- [ ] **Step 4: Protocolへの適合をテストに追加する**

`tests/unit/test_providers.py` に追記:
```python
from src.providers.claude import ClaudeProvider
from src.providers.gemini import GeminiProvider
from src.providers.azure_openai import AzureOpenAIProvider


def test_claude_provider_implements_protocol() -> None:
    provider = ClaudeProvider(api_key="dummy")
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, VisionLLMProvider)


def test_gemini_provider_implements_protocol() -> None:
    provider = GeminiProvider(api_key="dummy")
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, VisionLLMProvider)


def test_azure_openai_provider_implements_protocol() -> None:
    provider = AzureOpenAIProvider(api_key="dummy", endpoint="https://x.openai.azure.com/", deployment="gpt-4o")
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, VisionLLMProvider)
```

- [ ] **Step 5: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_providers.py -v
```

Expected: `5 passed`（Protocol適合テストのみ。実際のAPI呼び出しは行わない）

- [ ] **Step 6: コミット**

```powershell
git add src/providers/claude.py src/providers/gemini.py src/providers/azure_openai.py tests/unit/test_providers.py
git commit -m "feat: Claude/Gemini/AzureOpenAIプロバイダーを追加"
```

---

### Task 7: プロバイダーファクトリー

**Files:**
- Create: `src/providers/factory.py`

- [ ] **Step 1: 失敗するテストを追加する**

`tests/unit/test_providers.py` に追記:
```python
from src.providers.factory import create_llm_provider, create_vision_provider
from src.models.config import Settings


def test_factory_returns_ollama_by_default() -> None:
    settings = Settings(llm_provider="ollama")
    provider = create_llm_provider(settings)
    assert isinstance(provider, LLMProvider)


def test_factory_returns_claude_when_configured() -> None:
    settings = Settings(llm_provider="claude", anthropic_api_key="sk-ant-test")
    provider = create_llm_provider(settings)
    assert isinstance(provider, ClaudeProvider)


def test_vision_factory_returns_ollama_by_default() -> None:
    settings = Settings(llm_vision_provider="ollama")
    provider = create_vision_provider(settings)
    assert isinstance(provider, VisionLLMProvider)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_providers.py::test_factory_returns_ollama_by_default -v
```

Expected: `ImportError`

- [ ] **Step 3: factory.py を実装する**

`src/providers/factory.py`:
```python
from src.models.config import Settings
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.ollama import OllamaProvider, OllamaVisionProvider
from src.providers.claude import ClaudeProvider
from src.providers.gemini import GeminiProvider
from src.providers.azure_openai import AzureOpenAIProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider:
        case "ollama":
            return OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)
        case "claude":
            return ClaudeProvider(api_key=settings.anthropic_api_key)
        case "gemini":
            return GeminiProvider(api_key=settings.google_api_key, model=settings.gemini_model)
        case "azure_openai":
            return AzureOpenAIProvider(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def create_vision_provider(settings: Settings) -> VisionLLMProvider:
    match settings.llm_vision_provider:
        case "ollama":
            return OllamaVisionProvider(
                host=settings.ollama_host, vision_model=settings.ollama_vision_model
            )
        case "claude":
            return ClaudeProvider(api_key=settings.anthropic_api_key)
        case "gemini":
            return GeminiProvider(api_key=settings.google_api_key, model=settings.gemini_model)
        case "azure_openai":
            return AzureOpenAIProvider(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment,
            )
        case _:
            raise ValueError(f"Unknown vision provider: {settings.llm_vision_provider}")
```

- [ ] **Step 4: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_providers.py -v
```

Expected: `8 passed`

- [ ] **Step 5: コミット**

```powershell
git add src/providers/factory.py tests/unit/test_providers.py
git commit -m "feat: LLMプロバイダーファクトリーを追加（設定値で切り替え）"
```

---

### Task 8: 機密度分類器

**Files:**
- Create: `src/services/classifier.py`
- Create: `tests/unit/test_classifier.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_classifier.py`:
```python
import pytest
from src.services.classifier import classify_sensitivity


def test_general_text_is_pattern_a() -> None:
    result = classify_sensitivity("来週の会議の議題について確認します")
    assert result.label == "pattern_a"
    assert result.detected_keywords == []


def test_salary_text_is_pattern_b() -> None:
    result = classify_sensitivity("今月の給与について田中さんに連絡してください")
    assert result.label == "pattern_b"
    assert "給与" in result.detected_keywords


def test_customer_info_is_pattern_b() -> None:
    result = classify_sensitivity("A社との契約金額を山田さんに共有してください")
    assert result.label == "pattern_b"
    assert "契約" in result.detected_keywords


def test_personal_info_is_pattern_b() -> None:
    result = classify_sensitivity("山田さんのマイナンバーを確認してください")
    assert result.label == "pattern_b"


def test_evaluation_is_pattern_b() -> None:
    result = classify_sensitivity("今期の人事評価を部長に提出する")
    assert result.label == "pattern_b"


def test_empty_text_is_pattern_a() -> None:
    result = classify_sensitivity("")
    assert result.label == "pattern_a"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_classifier.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: classifier.py を実装する**

`src/services/classifier.py`:
```python
from src.models.task import SensitivityResult

_CONFIDENTIAL_KEYWORDS: list[str] = [
    # 人事
    "給与", "報酬", "賞与", "ボーナス", "評価", "採用", "解雇", "懲戒", "昇進", "降格",
    "人事", "退職", "休職",
    # 個人情報
    "マイナンバー", "住所", "生年月日", "健康診断", "病歴",
    # 顧客・財務
    "顧客名", "取引金額", "契約金額", "契約", "見積", "受注", "売上", "利益",
    "決算", "予算", "コスト",
]


def classify_sensitivity(text: str) -> SensitivityResult:
    if not text:
        return SensitivityResult(label="pattern_a", reason="空テキスト", detected_keywords=[])

    found = [kw for kw in _CONFIDENTIAL_KEYWORDS if kw in text]
    if found:
        return SensitivityResult(
            label="pattern_b",
            reason=f"機密キーワードを検出: {', '.join(found)}",
            detected_keywords=found,
        )
    return SensitivityResult(
        label="pattern_a",
        reason="機密キーワードなし",
        detected_keywords=[],
    )
```

- [ ] **Step 4: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_classifier.py -v
```

Expected: `6 passed`

- [ ] **Step 5: コミット**

```powershell
git add src/services/classifier.py tests/unit/test_classifier.py
git commit -m "feat: キーワードベースの機密度分類器を追加"
```

---

### Task 9: 承認ルーターサービス

**Files:**
- Create: `src/services/approval.py`
- Create: `tests/unit/test_approval.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_approval.py`:
```python
import pytest
from src.services.approval import decide_action
from src.models.task import ExtractedTask


def _make_task(score: float) -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title="テストタスク",
        confidence_score=score,
        source_type="email",
        source_id="msg-001",
    )


def test_high_score_is_auto_create() -> None:
    assert decide_action(_make_task(0.9), auto_threshold=0.8, review_threshold=0.5) == "auto_create"


def test_boundary_auto_create() -> None:
    assert decide_action(_make_task(0.8), auto_threshold=0.8, review_threshold=0.5) == "auto_create"


def test_mid_score_is_request_approval() -> None:
    assert decide_action(_make_task(0.65), auto_threshold=0.8, review_threshold=0.5) == "request_approval"


def test_boundary_review() -> None:
    assert decide_action(_make_task(0.5), auto_threshold=0.8, review_threshold=0.5) == "request_approval"


def test_low_score_is_log_only() -> None:
    assert decide_action(_make_task(0.3), auto_threshold=0.8, review_threshold=0.5) == "log_only"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_approval.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: approval.py を実装する**

`src/services/approval.py`:
```python
from typing import Literal
from src.models.task import ExtractedTask

Action = Literal["auto_create", "request_approval", "log_only"]


def decide_action(
    task: ExtractedTask,
    auto_threshold: float,
    review_threshold: float,
) -> Action:
    if task.confidence_score >= auto_threshold:
        return "auto_create"
    if task.confidence_score >= review_threshold:
        return "request_approval"
    return "log_only"
```

- [ ] **Step 4: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_approval.py -v
```

Expected: `5 passed`

- [ ] **Step 5: コミット**

```powershell
git add src/services/approval.py tests/unit/test_approval.py
git commit -m "feat: 信頼スコアベースの承認アクション決定サービスを追加"
```

---

### Task 10: タスクルーティングサービス（モック）

**Files:**
- Create: `src/services/routing.py`
- Create: `tests/unit/test_routing.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_routing.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.routing import route_task
from src.models.task import ExtractedTask


def _make_task(visibility: str, assignee_user_id: str | None = "user-001") -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title="テストタスク",
        confidence_score=0.9,
        source_type="email",
        source_id="msg-001",
        visibility=visibility,  # type: ignore[arg-type]
        assignee_user_id=assignee_user_id,
        department_id="group-sales",
    )


async def test_private_task_goes_to_todo() -> None:
    todo_mock = AsyncMock()
    planner_mock = AsyncMock()
    await route_task(
        task=_make_task("private"),
        todo_connector=todo_mock,
        planner_connector=planner_mock,
        company_plan_id="plan-all",
        dept_plan_map={"group-sales": "plan-sales"},
    )
    todo_mock.create_task.assert_awaited_once()
    planner_mock.create_task.assert_not_awaited()


async def test_team_task_goes_to_dept_planner() -> None:
    todo_mock = AsyncMock()
    planner_mock = AsyncMock()
    await route_task(
        task=_make_task("team"),
        todo_connector=todo_mock,
        planner_connector=planner_mock,
        company_plan_id="plan-all",
        dept_plan_map={"group-sales": "plan-sales"},
    )
    planner_mock.create_task.assert_awaited_once_with(
        task=_make_task("team"), plan_id="plan-sales"
    )


async def test_all_task_goes_to_company_planner() -> None:
    todo_mock = AsyncMock()
    planner_mock = AsyncMock()
    await route_task(
        task=_make_task("all"),
        todo_connector=todo_mock,
        planner_connector=planner_mock,
        company_plan_id="plan-all",
        dept_plan_map={"group-sales": "plan-sales"},
    )
    planner_mock.create_task.assert_awaited_once_with(
        task=_make_task("all"), plan_id="plan-all"
    )
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_routing.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: routing.py を実装する**

`src/services/routing.py`:
```python
from typing import Any
from src.models.task import ExtractedTask


async def route_task(
    task: ExtractedTask,
    todo_connector: Any,
    planner_connector: Any,
    company_plan_id: str,
    dept_plan_map: dict[str, str],
) -> None:
    match task.visibility:
        case "private":
            await todo_connector.create_task(task=task)
        case "team":
            plan_id = dept_plan_map.get(task.department_id or "", company_plan_id)
            await planner_connector.create_task(task=task, plan_id=plan_id)
        case "all":
            await planner_connector.create_task(task=task, plan_id=company_plan_id)
```

- [ ] **Step 4: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_routing.py -v
```

Expected: `3 passed`

- [ ] **Step 5: コミット**

```powershell
git add src/services/routing.py tests/unit/test_routing.py
git commit -m "feat: visibility→起票先ルーティングサービスを追加"
```

---

### Task 11: LangGraph エージェント

**Files:**
- Create: `src/agents/nodes.py`
- Create: `src/agents/graph.py`
- Create: `tests/unit/test_agent.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_agent.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.graph import build_graph, AgentState
from src.models.task import ExtractedTask, SensitivityResult


async def test_pattern_b_text_skips_external_llm() -> None:
    mock_provider = AsyncMock()
    graph = build_graph(
        llm_provider=mock_provider,
        auto_threshold=0.8,
        review_threshold=0.5,
    )
    result = await graph.ainvoke(AgentState(
        source_text="今月の給与について確認してください",
        source_type="email",
        source_id="msg-001",
        sensitivity=None,
        extracted_tasks=[],
        actions=[],
        errors=[],
    ))
    mock_provider.extract_tasks.assert_not_awaited()
    assert result["sensitivity"].label == "pattern_b"


async def test_low_confidence_task_is_log_only() -> None:
    mock_provider = AsyncMock(return_value=[
        ExtractedTask(
            is_task=True,
            title="何かしてください",
            confidence_score=0.3,
            source_type="email",
            source_id="msg-001",
        )
    ])
    graph = build_graph(
        llm_provider=mock_provider,
        auto_threshold=0.8,
        review_threshold=0.5,
    )
    result = await graph.ainvoke(AgentState(
        source_text="何かしてください",
        source_type="email",
        source_id="msg-001",
        sensitivity=None,
        extracted_tasks=[],
        actions=[],
        errors=[],
    ))
    assert result["actions"] == [("何かしてください", "log_only")]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```powershell
pytest tests/unit/test_agent.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: nodes.py を実装する**

`src/agents/nodes.py`:
```python
from typing import Any
from src.models.task import ExtractedTask, SensitivityResult
from src.services.classifier import classify_sensitivity
from src.services.approval import decide_action
from src.providers.base import LLMProvider


async def node_classify(state: dict[str, Any]) -> dict[str, Any]:
    result = classify_sensitivity(state["source_text"])
    return {"sensitivity": result}


async def node_extract(
    state: dict[str, Any], llm_provider: LLMProvider
) -> dict[str, Any]:
    if state["sensitivity"].label == "pattern_b":
        return {"extracted_tasks": []}
    tasks = await llm_provider.extract_tasks(
        state["source_text"], state["source_type"]
    )
    for t in tasks:
        t.source_id = state["source_id"]
    return {"extracted_tasks": tasks}


async def node_route(
    state: dict[str, Any],
    auto_threshold: float,
    review_threshold: float,
) -> dict[str, Any]:
    actions = [
        (t.title, decide_action(t, auto_threshold, review_threshold))
        for t in state["extracted_tasks"]
    ]
    return {"actions": actions}
```

- [ ] **Step 4: graph.py を実装する**

`src/agents/graph.py`:
```python
from typing import TypedDict, Annotated
import operator
from functools import partial
from langgraph.graph import StateGraph, END
from src.models.task import ExtractedTask, SensitivityResult
from src.providers.base import LLMProvider
from src.agents import nodes


class AgentState(TypedDict):
    source_text: str
    source_type: str
    source_id: str
    sensitivity: SensitivityResult | None
    extracted_tasks: list[ExtractedTask]
    actions: list[tuple[str, str]]
    errors: Annotated[list[str], operator.add]


def build_graph(
    llm_provider: LLMProvider,
    auto_threshold: float,
    review_threshold: float,
) -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("classify", nodes.node_classify)
    builder.add_node(
        "extract",
        partial(nodes.node_extract, llm_provider=llm_provider),
    )
    builder.add_node(
        "route",
        partial(nodes.node_route, auto_threshold=auto_threshold, review_threshold=review_threshold),
    )

    builder.set_entry_point("classify")
    builder.add_edge("classify", "extract")
    builder.add_edge("extract", "route")
    builder.add_edge("route", END)

    return builder.compile()
```

- [ ] **Step 5: テストを実行してパスを確認する**

```powershell
pytest tests/unit/test_agent.py -v
```

Expected: `2 passed`

- [ ] **Step 6: コミット**

```powershell
git add src/agents/nodes.py src/agents/graph.py tests/unit/test_agent.py
git commit -m "feat: LangGraphタスク抽出エージェントを追加（classify→extract→route）"
```

---

### Task 12: FastAPI アプリ

**Files:**
- Create: `src/api/routers/health.py`
- Create: `src/api/routers/tasks.py`
- Create: `src/api/main.py`

- [ ] **Step 1: health.py を実装する**

`src/api/routers/health.py`:
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 2: tasks.py を実装する（手動起票エンドポイント）**

`src/api/routers/tasks.py`:
```python
from fastapi import APIRouter, Depends
from src.models.task import ExtractedTask
from src.models.config import get_settings, Settings

router = APIRouter(prefix="/tasks")


@router.post("/extract")
async def extract_from_text(
    text: str,
    source_type: str = "email",
    settings: Settings = Depends(get_settings),
) -> dict[str, list[dict[str, object]]]:
    from src.providers.factory import create_llm_provider
    from src.services.classifier import classify_sensitivity

    sensitivity = classify_sensitivity(text)
    if sensitivity.label == "pattern_b":
        return {"tasks": [], "skipped_reason": "機密データ（Pattern B）"}  # type: ignore[return-value]

    provider = create_llm_provider(settings)
    tasks = await provider.extract_tasks(text, source_type)
    return {"tasks": [t.model_dump() for t in tasks]}
```

- [ ] **Step 3: main.py を実装する**

`src/api/main.py`:
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.api.routers import health, tasks
from src.services.state import init_db
from src.models.config import get_settings


scheduler = AsyncIOScheduler()


async def polling_job() -> None:
    """Graph API申請後に実装（Part B Task 21で接続）"""
    pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    settings = get_settings()
    scheduler.add_job(
        polling_job,
        "interval",
        seconds=settings.polling_interval_seconds,
        id="polling",
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="AutoTicket API", lifespan=lifespan)
app.include_router(health.router)
app.include_router(tasks.router)
```

- [ ] **Step 4: サーバーを起動して動作確認する**

```powershell
uvicorn src.api.main:app --reload --port 8000
```

ブラウザで `http://localhost:8000/health` を開く。

Expected: `{"status": "ok"}`

- [ ] **Step 5: コミット**

```powershell
git add src/api/ 
git commit -m "feat: FastAPI アプリ + APSchedulerポーリング基盤を追加"
```

---

### Task 13: Part A 全テスト実行・ruff・mypy チェック

- [ ] **Step 1: 全ユニットテストを実行する**

```powershell
pytest tests/unit/ -v --tb=short
```

Expected: 全テスト PASS

- [ ] **Step 2: ruff チェックを実行する**

```powershell
ruff check src/ tests/
ruff format src/ tests/
```

Expected: エラーなし（警告は修正する）

- [ ] **Step 3: mypy チェックを実行する**

```powershell
mypy src/
```

Expected: `Success: no issues found`（型エラーがあれば修正する）

- [ ] **Step 4: コミット**

```powershell
git add -A
git commit -m "chore: Part A 全テスト・ruff・mypy パス確認"
```

---

## Part B: Graph API依存（認証情報受け取り後に実装）

> **前提条件**: `.env` に `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` が設定済みであること。

---

### Task 14: Graph API クライアント（認証 + メールポーリング）

**Files:**
- Create: `src/connectors/graph_api.py`
- Create: `tests/integration/test_graph_api.py`

- [ ] **Step 1: graph_api.py の認証部分を実装する**

`src/connectors/graph_api.py`:
```python
import msal
import httpx
from src.models.config import Settings


class GraphAPIClient:
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._app = msal.ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        )

    def _get_token(self) -> str:
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Token acquisition failed: {result.get('error_description')}")
        return str(result["access_token"])

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    async def get_unread_emails(self, user_id: str) -> list[dict[str, object]]:
        url = f"{self.GRAPH_BASE}/users/{user_id}/messages"
        params = {
            "$filter": "isRead eq false",
            "$select": "id,subject,body,from,receivedDateTime",
            "$top": "50",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def mark_email_read(self, user_id: str, message_id: str) -> None:
        url = f"{self.GRAPH_BASE}/users/{user_id}/messages/{message_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                url, headers=self._headers(), json={"isRead": True}
            )
            resp.raise_for_status()

    async def get_meeting_transcripts(self, user_id: str) -> list[dict[str, object]]:
        url = f"{self.GRAPH_BASE}/users/{user_id}/onlineMeetings"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            meetings: list[dict[str, object]] = resp.json().get("value", [])
        transcripts = []
        for meeting in meetings:
            meeting_id = meeting["id"]
            t_url = f"{self.GRAPH_BASE}/users/{user_id}/onlineMeetings/{meeting_id}/transcripts"
            async with httpx.AsyncClient() as client:
                t_resp = await client.get(t_url, headers=self._headers())
                if t_resp.status_code == 200:
                    transcripts.extend(t_resp.json().get("value", []))
        return transcripts

    async def get_users(self) -> list[dict[str, object]]:
        url = f"{self.GRAPH_BASE}/users"
        params = {"$select": "id,displayName,mail,department"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_groups(self) -> list[dict[str, object]]:
        url = f"{self.GRAPH_BASE}/groups"
        params = {"$select": "id,displayName"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return list(resp.json().get("value", []))
```

- [ ] **Step 2: 統合テストを書く**

`tests/integration/test_graph_api.py`:
```python
"""
統合テスト: 実際のGraph APIに接続します。
.envにAZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRETが必要です。
"""
import pytest
from src.connectors.graph_api import GraphAPIClient
from src.models.config import get_settings

pytestmark = pytest.mark.integration


async def test_get_token_succeeds() -> None:
    client = GraphAPIClient(get_settings())
    token = client._get_token()
    assert token.startswith("ey")  # JWTトークンはeyで始まる


async def test_get_users_returns_list() -> None:
    client = GraphAPIClient(get_settings())
    users = await client.get_users()
    assert isinstance(users, list)
    assert len(users) > 0
    assert "id" in users[0]
    assert "displayName" in users[0]


async def test_get_groups_returns_list() -> None:
    client = GraphAPIClient(get_settings())
    groups = await client.get_groups()
    assert isinstance(groups, list)
```

- [ ] **Step 3: 統合テストを実行する（.env設定済みの場合）**

```powershell
pytest tests/integration/test_graph_api.py -v -m integration
```

Expected: `3 passed`

- [ ] **Step 4: コミット**

```powershell
git add src/connectors/graph_api.py tests/integration/test_graph_api.py
git commit -m "feat: Graph APIクライアント（MSAL認証・メール・会議・ユーザー・グループ取得）を追加"
```

---

### Task 15: Planner コネクター

**Files:**
- Create: `src/connectors/planner.py`

- [ ] **Step 1: planner.py を実装する**

`src/connectors/planner.py`:
```python
import httpx
from src.models.task import ExtractedTask
from src.connectors.graph_api import GraphAPIClient


class PlannerConnector:
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def create_task(self, task: ExtractedTask, plan_id: str) -> str:
        url = f"{self.GRAPH_BASE}/planner/tasks"
        body: dict[str, object] = {
            "planId": plan_id,
            "title": task.title,
            "assignments": {},
        }
        if task.assignee_user_id:
            body["assignments"] = {
                task.assignee_user_id: {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "orderHint": " !",
                }
            }
        if task.deadline:
            body["dueDateTime"] = task.deadline.isoformat() + "T00:00:00Z"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, headers=self._graph._headers(), json=body
            )
            resp.raise_for_status()
            created_id: str = resp.json()["id"]
            return created_id
```

- [ ] **Step 2: コミット**

```powershell
git add src/connectors/planner.py
git commit -m "feat: Microsoft Plannerタスク起票コネクターを追加"
```

---

### Task 16: To Do コネクター

**Files:**
- Create: `src/connectors/todo.py`

- [ ] **Step 1: todo.py を実装する**

`src/connectors/todo.py`:
```python
import httpx
from src.models.task import ExtractedTask
from src.connectors.graph_api import GraphAPIClient


class TodoConnector:
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_default_list_id(self, user_id: str) -> str:
        url = f"{self.GRAPH_BASE}/users/{user_id}/todo/lists"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._graph._headers())
            resp.raise_for_status()
            lists: list[dict[str, object]] = resp.json().get("value", [])
        default = next(
            (lst for lst in lists if lst.get("wellknownListName") == "defaultList"), None
        )
        if default is None and lists:
            default = lists[0]
        if default is None:
            raise RuntimeError(f"No To Do list found for user {user_id}")
        return str(default["id"])

    async def create_task(self, task: ExtractedTask) -> str:
        user_id = task.assignee_user_id
        if user_id is None:
            raise ValueError("private タスクには assignee_user_id が必要です")
        list_id = await self.get_default_list_id(user_id)
        url = f"{self.GRAPH_BASE}/users/{user_id}/todo/lists/{list_id}/tasks"
        body: dict[str, object] = {"title": task.title}
        if task.deadline:
            body["dueDateTime"] = {
                "dateTime": task.deadline.isoformat() + "T00:00:00",
                "timeZone": "Asia/Tokyo",
            }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, headers=self._graph._headers(), json=body
            )
            resp.raise_for_status()
            created_id: str = resp.json()["id"]
            return created_id
```

- [ ] **Step 2: コミット**

```powershell
git add src/connectors/todo.py
git commit -m "feat: Microsoft To Doプライベートタスク起票コネクターを追加"
```

---

### Task 17: フルパイプライン結合（ポーリング → 抽出 → 起票）

**Files:**
- Modify: `src/api/main.py`

- [ ] **Step 1: polling_job を完全実装する**

`src/api/main.py` の `polling_job` 関数を以下で置き換える:
```python
async def polling_job() -> None:
    from src.connectors.graph_api import GraphAPIClient
    from src.connectors.planner import PlannerConnector
    from src.connectors.todo import TodoConnector
    from src.services.state import is_processed, mark_processed
    from src.services.routing import route_task
    from src.providers.factory import create_llm_provider
    from src.agents.graph import build_graph, AgentState

    settings = get_settings()
    graph_client = GraphAPIClient(settings)
    planner = PlannerConnector(graph_client)
    todo = TodoConnector(graph_client)
    llm_provider = create_llm_provider(settings)
    agent = build_graph(
        llm_provider=llm_provider,
        auto_threshold=settings.auto_create_threshold,
        review_threshold=settings.manual_review_threshold,
    )
    dept_plan_map: dict[str, str] = {}  # Phase 2で動的取得に変更

    users = await graph_client.get_users()
    for user in users:
        user_id = str(user["id"])
        emails = await graph_client.get_unread_emails(user_id)
        for email in emails:
            msg_id = str(email["id"])
            if await is_processed(msg_id):
                continue
            body_content = str(email.get("body", {}).get("content", ""))
            result = await agent.ainvoke(AgentState(
                source_text=body_content,
                source_type="email",
                source_id=msg_id,
                sensitivity=None,
                extracted_tasks=[],
                actions=[],
                errors=[],
            ))
            for task, action in result["actions"]:
                if action == "auto_create":
                    task_obj = next(
                        t for t in result["extracted_tasks"] if t.title == task
                    )
                    await route_task(
                        task=task_obj,
                        todo_connector=todo,
                        planner_connector=planner,
                        company_plan_id=settings.company_wide_plan_id,
                        dept_plan_map=dept_plan_map,
                    )
            await mark_processed(msg_id, "email")
```

- [ ] **Step 2: サーバーを再起動して動作確認する**

```powershell
uvicorn src.api.main:app --reload --port 8000
```

ログに `polling_job` が5分ごとに実行されることを確認する。

- [ ] **Step 3: コミット**

```powershell
git add src/api/main.py
git commit -m "feat: Graph APIポーリング→LangGraph→Planner/To Doフルパイプラインを接続"
```

---

### Task 18: Docker（Langfuse 監査ログ）

**Files:**
- Create: `docker/docker-compose.yml`

- [ ] **Step 1: docker-compose.yml を作成する**

`docker/docker-compose.yml`:
```yaml
version: "3.9"

services:
  langfuse-server:
    image: langfuse/langfuse:latest
    depends_on:
      - langfuse-db
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_SECRET: your-secret-change-me
      SALT: your-salt-change-me
      NEXTAUTH_URL: http://localhost:3000
      TELEMETRY_ENABLED: "false"

  langfuse-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_db:/var/lib/postgresql/data

volumes:
  langfuse_db:
```

- [ ] **Step 2: Langfuse を起動する**

```powershell
docker compose -f docker/docker-compose.yml up -d
```

- [ ] **Step 3: http://localhost:3000 にアクセスしてUIを確認する**

初回アクセス時にアカウントを作成し、プロジェクトを作成してAPIキーを取得する。
`.env` の `LANGFUSE_SECRET_KEY` と `LANGFUSE_PUBLIC_KEY` に設定する。

- [ ] **Step 4: コミット**

```powershell
git add docker/docker-compose.yml
git commit -m "feat: Langfuse監査ログ用docker-compose設定を追加"
```

---

### Task 19: Part B 全テスト実行・E2E動作確認

- [ ] **Step 1: 全テストを実行する**

```powershell
pytest tests/ -v --ignore=tests/integration -tb=short
```

Expected: 全ユニットテスト PASS

- [ ] **Step 2: 統合テストを実行する（Graph API接続確認）**

```powershell
pytest tests/integration/ -v -m integration
```

Expected: `3 passed`

- [ ] **Step 3: E2E動作確認（手動）**

1. Outlookで自分宛にテストメールを送信：「田中さん、来週金曜までにA社向け提案資料を作成してください。優先度高です。」
2. ポーリングが実行されるのを待つ（または `polling_interval_seconds=30` に変更して早める）
3. Microsoft Plannerで「A社向け提案資料を作成」タスクが作成されていることを確認する
4. Langfuse（`http://localhost:3000`）でトレースが記録されていることを確認する

- [ ] **Step 4: progress.md を更新する**

`docs/progress.md` の「現在のフェーズ」と「完了した作業」を更新する。

- [ ] **Step 5: 最終コミット**

```powershell
git add docs/progress.md docs/tasks.md
git commit -m "chore: Phase 1 実装完了・進捗ドキュメントを更新"
```

---

## セルフレビュー

### 仕様書カバレッジ

| 仕様要件 | 対応タスク |
|---------|----------|
| Outlookメールポーリング | Task 14, 17 |
| Teams会議文字起こし | Task 14（`get_meeting_transcripts`） |
| 機密度分類（Pattern A/B） | Task 8 |
| LLMプロバイダー抽象化（4種） | Task 5, 6, 7 |
| 処理済みID管理（SQLite） | Task 4 |
| LangGraph状態マシン | Task 11 |
| 信頼スコア→承認分岐 | Task 9 |
| visibility→起票先ルーティング | Task 10 |
| Planner起票 | Task 15 |
| To Do（privateタスク）起票 | Task 16 |
| マルチユーザー（user_id別処理） | Task 17 |
| Langfuse監査ログ | Task 18 |
| FastAPI + APScheduler | Task 12 |

### 型一貫性チェック
- `ExtractedTask.assignee_user_id` → Task 2で定義、Task 15/16で使用 ✅
- `AgentState.extracted_tasks: list[ExtractedTask]` → Task 11で定義、Task 17で使用 ✅
- `decide_action` → `Action = Literal["auto_create", "request_approval", "log_only"]` → Task 9で定義、Task 17で使用 ✅
- `route_task(todo_connector, planner_connector, ...)` → Task 10で定義、Task 17で使用 ✅
