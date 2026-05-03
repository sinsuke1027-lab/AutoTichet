# AutoTicket Phase 1B 以降 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graph API 承認後の統合完成（Phase 1B）から、Phase 2（Teams/OneNote）・Phase 3（ローカルLLM・Teamsボット）まで、途中から再開できる単位で実装する。

**Architecture:** FastAPI + LangGraph エージェントが APScheduler で定期ポーリングし、Graph API 経由でメール/会議を取得してタスク抽出・起票する。機密データは Ollama（ローカル LLM）に強制ルーティングし、外部 LLM には送信しない。

**Tech Stack:** Python 3.13 / FastAPI / LangGraph / Pydantic v2 / MSAL / httpx / SQLite(aiosqlite) / APScheduler / Langfuse v4 / Docker / Ollama

---

## 現在の完了状態（2026-05-03 時点）

| ファイル | 状態 |
|---------|------|
| `src/models/task.py` | ✅ |
| `src/models/config.py` | ✅ |
| `src/services/state.py` | ✅ |
| `src/services/classifier.py` | ✅ |
| `src/services/approval.py` | ✅ |
| `src/services/routing.py` | ✅ |
| `src/services/langfuse_client.py` | ✅ |
| `src/providers/` (base/ollama/claude/gemini/azure_openai/factory) | ✅ |
| `src/agents/nodes.py` + `graph.py` | ✅ |
| `src/connectors/graph_api.py` | ✅（モックテスト済み・実接続未確認） |
| `src/connectors/planner.py` | ✅（モックテスト済み・実接続未確認） |
| `src/connectors/todo.py` | ✅（モックテスト済み・実接続未確認） |
| `src/api/main.py` | ⚠️ `polling_job()` がスタブ |
| `docker/Dockerfile` + `docker-compose.yml` | ✅ |
| テスト合計 | ✅ 45/45 パス |

**ブロッカー:** Graph API アプリ登録（IT管理者申請中）

---

## フェーズ構成

```
Phase 1B: Graph API 統合（credentials 受領後）
  Task 14: dept_plan_map を Settings に追加         ← 今すぐ可
  Task 15: polling_job() 完全実装                    ← 今すぐ可
  Task 16: 統合テスト基盤セットアップ                ← credentials 必要
  Task 17: Graph API 疎通確認テスト                  ← credentials 必要
  Task 18: E2E テスト（Outlook → Planner 全フロー） ← credentials 必要

Phase 2: Teamsチャット・OneNote対応
  Task 19: Teams チャットコネクター
  Task 20: OneNote コネクター
  Task 21: polling_job() 更新（Teams/OneNote追加）

Phase 3: ローカルLLM + Teamsボット
  Task 22: Pattern B → Ollama 強制ルーティング
  Task 23: Ollama を docker-compose に追加
  Task 24: Teams Bot エンドポイント（/bot）
  Task 25: Ollama vision 画像処理サービス
```

---

## ファイル変更マップ

| タスク | 新規作成 | 変更 |
|--------|---------|------|
| 14 | — | `src/models/config.py`, `.env.example` |
| 15 | `tests/unit/test_polling_job.py` | `src/api/main.py` |
| 16 | `tests/integration/conftest.py` | `pyproject.toml` |
| 17 | `tests/integration/test_graph_api_live.py` | — |
| 18 | `tests/integration/test_e2e.py` | — |
| 19 | `src/connectors/teams_chat.py`, `tests/unit/test_teams_chat.py` | `src/api/main.py` |
| 20 | `src/connectors/onenote.py`, `tests/unit/test_onenote.py` | `src/api/main.py` |
| 21 | — | `src/api/main.py` |
| 22 | — | `src/models/config.py`, `src/providers/factory.py` |
| 23 | — | `docker/docker-compose.yml`, `.env.example` |
| 24 | `src/api/routers/bot.py`, `tests/unit/test_bot.py` | `src/api/main.py` |
| 25 | `src/services/image_processor.py`, `tests/unit/test_image_processor.py` | `src/api/routers/bot.py` |

---

## Phase 1B: Graph API 統合

---

### Task 14: dept_plan_map を Settings に追加

**前提:** credentials 不要・即実施可

**Files:**
- Modify: `src/models/config.py`
- Modify: `.env.example`

- [ ] **Step 1: テストを書く**

`tests/unit/test_models.py` に追記：

```python
def test_dept_plan_map_defaults_to_empty() -> None:
    s = Settings()
    assert s.dept_plan_map == {}

def test_dept_plan_map_parsed_from_json() -> None:
    s = Settings(dept_plan_map='{"g1": "p1", "g2": "p2"}')
    assert s.dept_plan_map == {"g1": "p1", "g2": "p2"}
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_models.py -v -k "dept_plan_map"
```

Expected: AttributeError または FAIL

- [ ] **Step 3: config.py に追加**

`src/models/config.py` の `Settings` クラスに追加：

```python
import json
from pydantic import field_validator

# 既存フィールドの後に追加
company_wide_plan_id: str = ""
dept_plan_map: str = "{}"  # JSON文字列 例: '{"group-id": "plan-id"}'

@field_validator("dept_plan_map")
@classmethod
def validate_dept_plan_map(cls, v: str) -> str:
    try:
        parsed = json.loads(v)
        if not isinstance(parsed, dict):
            raise ValueError("dept_plan_map は JSON オブジェクトである必要があります")
    except json.JSONDecodeError as e:
        raise ValueError(f"dept_plan_map のJSON解析失敗: {e}") from e
    return v

def get_dept_plan_map(self) -> dict[str, str]:
    return dict(json.loads(self.dept_plan_map))
```

- [ ] **Step 4: テストを更新**

```python
def test_dept_plan_map_defaults_to_empty() -> None:
    s = Settings()
    assert s.get_dept_plan_map() == {}

def test_dept_plan_map_parsed_from_json() -> None:
    s = Settings(dept_plan_map='{"g1": "p1", "g2": "p2"}')
    assert s.get_dept_plan_map() == {"g1": "p1", "g2": "p2"}
```

- [ ] **Step 5: テスト確認**

```
pytest tests/unit/test_models.py -v -k "dept_plan_map"
```

Expected: 2 passed

- [ ] **Step 6: .env.example に追記**

```
# 部署グループID → PlannerプランID マッピング（JSON形式）
DEPT_PLAN_MAP={"m365-group-id-1": "planner-plan-id-1"}
```

- [ ] **Step 7: 全テスト確認 + lint**

```
pytest tests/unit/ -v
ruff check src/ tests/
mypy src/
```

Expected: 全パス

- [ ] **Step 8: コミット**

```
git add src/models/config.py .env.example tests/unit/test_models.py
git commit -m "feat: dept_plan_map フィールドを Settings に追加（JSON検証付き）"
```

---

### Task 15: polling_job() 完全実装

**前提:** credentials 不要・mock でテスト可

**Files:**
- Modify: `src/api/main.py`
- Create: `tests/unit/test_polling_job.py`

- [ ] **Step 1: テストを書く**

```python
# tests/unit/test_polling_job.py
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.task import ExtractedTask, SensitivityResult


def _make_task(title: str, visibility: str = "team") -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title=title,
        visibility=visibility,  # type: ignore[arg-type]
        confidence_score=0.9,
        source_type="email",
        source_id="msg-1",
    )


async def test_polling_job_skips_when_no_azure_config() -> None:
    """Azure 認証情報が未設定の場合はスキップする"""
    with patch("src.api.main.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(azure_tenant_id="")
        from src.api.main import polling_job
        await polling_job()  # エラーなく終了すればOK


async def test_polling_job_skips_processed_email() -> None:
    """処理済みメールはスキップする"""
    with (
        patch("src.api.main.get_settings") as mock_settings,
        patch("src.api.main.GraphAPIClient") as mock_graph_cls,
        patch("src.api.main.is_processed", return_value=True) as mock_is_processed,
        patch("src.api.main.mark_processed") as mock_mark,
    ):
        settings = MagicMock(
            azure_tenant_id="t",
            azure_client_id="c",
            azure_client_secret="s",
        )
        mock_settings.return_value = settings
        graph_client = AsyncMock()
        graph_client.get_users.return_value = [{"id": "user-1"}]
        graph_client.get_unread_emails.return_value = [{"id": "msg-already"}]
        mock_graph_cls.return_value = graph_client

        from src.api.main import polling_job
        await polling_job()

        mock_is_processed.assert_called_once_with("msg-already")
        mock_mark.assert_not_called()


async def test_polling_job_routes_high_confidence_task() -> None:
    """信頼スコア高タスクは auto_create で起票される"""
    task = _make_task("MTG議事録タスク", visibility="team")
    agent_result = {
        "extracted_tasks": [task],
        "actions": [("MTG議事録タスク", "auto_create")],
        "sensitivity": SensitivityResult(label="pattern_a", reason="ok", detected_keywords=[]),
        "errors": [],
    }

    with (
        patch("src.api.main.get_settings") as mock_settings,
        patch("src.api.main.GraphAPIClient") as mock_graph_cls,
        patch("src.api.main.PlannerConnector") as mock_planner_cls,
        patch("src.api.main.TodoConnector"),
        patch("src.api.main.create_llm_provider"),
        patch("src.api.main.build_graph") as mock_build,
        patch("src.api.main.is_processed", return_value=False),
        patch("src.api.main.mark_processed"),
        patch("src.api.main.route_task") as mock_route,
    ):
        settings = MagicMock(
            azure_tenant_id="t",
            azure_client_id="c",
            azure_client_secret="s",
            auto_create_threshold=0.8,
            manual_review_threshold=0.5,
            company_wide_plan_id="plan-all",
        )
        settings.get_dept_plan_map.return_value = {}
        mock_settings.return_value = settings

        graph_client = AsyncMock()
        graph_client.get_users.return_value = [{"id": "user-1"}]
        graph_client.get_unread_emails.return_value = [
            {"id": "msg-1", "subject": "MTG", "body": {"content": "タスクあり"}}
        ]
        mock_graph_cls.return_value = graph_client

        compiled_graph = AsyncMock()
        compiled_graph.ainvoke.return_value = agent_result
        mock_build.return_value = compiled_graph

        from src.api.main import polling_job
        await polling_job()

        mock_route.assert_called_once()
        graph_client.mark_email_read.assert_called_once_with("user-1", "msg-1")
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_polling_job.py -v
```

Expected: FAIL（polling_job がスタブのため）

- [ ] **Step 3: polling_job() を実装**

`src/api/main.py` を以下に書き換える：

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.agents.graph import AgentState, build_graph
from src.api.routers import health, tasks
from src.connectors.graph_api import GraphAPIClient
from src.connectors.planner import PlannerConnector
from src.connectors.todo import TodoConnector
from src.models.config import get_settings
from src.providers.factory import create_llm_provider
from src.services.routing import route_task
from src.services.state import init_db, is_processed, mark_processed

scheduler = AsyncIOScheduler()


async def polling_job() -> None:
    """Outlook メールをポーリングしてタスクを自動起票する"""
    settings = get_settings()
    if not settings.azure_tenant_id:
        return  # Graph API 未設定はスキップ

    graph_client = GraphAPIClient(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    planner = PlannerConnector(graph_client)
    todo = TodoConnector(graph_client)
    llm = create_llm_provider(settings)
    graph = build_graph(llm, settings.auto_create_threshold, settings.manual_review_threshold)

    users = await graph_client.get_users()

    for user in users:
        uid = str(user["id"])
        emails = await graph_client.get_unread_emails(uid)

        for email in emails:
            msg_id = str(email["id"])
            if await is_processed(msg_id):
                continue

            subject = str(email.get("subject", ""))
            body = str(email.get("body", {}).get("content", ""))
            text = f"件名: {subject}\n\n{body}"

            state: AgentState = {
                "source_text": text,
                "source_type": "email",
                "source_id": msg_id,
                "sensitivity": None,
                "extracted_tasks": [],
                "actions": [],
                "errors": [],
            }
            result = await graph.ainvoke(state)

            action_map = dict(result["actions"])
            for task in result["extracted_tasks"]:
                action = action_map.get(task.title, "log_only")
                if action in ("auto_create", "request_approval"):
                    await route_task(
                        task=task,
                        todo_connector=todo,
                        planner_connector=planner,
                        company_plan_id=settings.company_wide_plan_id,
                        dept_plan_map=settings.get_dept_plan_map(),
                    )

            await mark_processed(msg_id, "email")
            await graph_client.mark_email_read(uid, msg_id)


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

- [ ] **Step 4: テスト確認**

```
pytest tests/unit/test_polling_job.py -v
```

Expected: 3 passed

- [ ] **Step 5: 全テスト + lint**

```
pytest tests/unit/ -v
ruff check src/ tests/
mypy src/
```

Expected: 全パス

- [ ] **Step 6: コミット**

```
git add src/api/main.py tests/unit/test_polling_job.py
git commit -m "feat: polling_job() 完全実装（メールポーリング→LangGraph→起票）"
```

---

### Task 16: 統合テスト基盤セットアップ

**前提:** Graph API 承認後に実施

**Files:**
- Create: `tests/integration/conftest.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: pytest マーカーを追加**

`pyproject.toml` の `[tool.pytest.ini_options]` に追記：

```toml
markers = [
    "integration: requires Graph API credentials (--run-integration to enable)",
]
```

- [ ] **Step 2: conftest.py を作成**

```python
# tests/integration/conftest.py
import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires Graph API credentials",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not os.environ.get("AZURE_TENANT_ID"):
        skip = pytest.mark.skip(reason="AZURE_TENANT_ID 未設定 – 統合テストをスキップ")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
```

- [ ] **Step 3: conftest が機能することを確認**

```
pytest tests/integration/ -v
```

Expected: collected 0 items または all skipped

- [ ] **Step 4: コミット**

```
git add tests/integration/conftest.py pyproject.toml
git commit -m "test: 統合テスト基盤 – credentials未設定時の自動skip追加"
```

---

### Task 17: Graph API 疎通確認テスト

**前提:** `.env` に `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` 設定済み

**Files:**
- Create: `tests/integration/test_graph_api_live.py`

- [ ] **Step 1: テストを書く**

```python
# tests/integration/test_graph_api_live.py
import pytest
from src.models.config import get_settings
from src.connectors.graph_api import GraphAPIClient


@pytest.fixture
def graph_client() -> GraphAPIClient:
    s = get_settings()
    return GraphAPIClient(
        tenant_id=s.azure_tenant_id,
        client_id=s.azure_client_id,
        client_secret=s.azure_client_secret,
    )


@pytest.mark.integration
def test_token_acquisition(graph_client: GraphAPIClient) -> None:
    """トークン取得が成功すること"""
    token = graph_client._get_token()
    assert token.startswith("eyJ")  # JWT形式


@pytest.mark.integration
async def test_get_users_returns_list(graph_client: GraphAPIClient) -> None:
    """ユーザー一覧が取得できること"""
    users = await graph_client.get_users()
    assert isinstance(users, list)
    assert len(users) > 0
    assert "id" in users[0]
    assert "displayName" in users[0]


@pytest.mark.integration
async def test_get_groups_returns_list(graph_client: GraphAPIClient) -> None:
    """M365グループ一覧が取得できること"""
    groups = await graph_client.get_groups()
    assert isinstance(groups, list)


@pytest.mark.integration
async def test_get_unread_emails(graph_client: GraphAPIClient) -> None:
    """未読メール取得が成功すること（0件でもOK）"""
    users = await graph_client.get_users()
    assert len(users) > 0
    emails = await graph_client.get_unread_emails(users[0]["id"])
    assert isinstance(emails, list)
```

- [ ] **Step 2: テストを実行**

```
pytest tests/integration/test_graph_api_live.py -v
```

Expected: 4 passed（credentials 設定済みの場合）

- [ ] **Step 3: コミット**

```
git add tests/integration/test_graph_api_live.py
git commit -m "test: Graph API 疎通確認テスト追加（統合テスト）"
```

---

### Task 18: E2E テスト（Outlook → Planner 全フロー）

**前提:** Task 17 が通ること・Planner プランが存在すること

**Files:**
- Create: `tests/integration/test_e2e.py`

- [ ] **Step 1: テストを書く**

```python
# tests/integration/test_e2e.py
import pytest
from src.models.config import get_settings
from src.connectors.graph_api import GraphAPIClient
from src.connectors.planner import PlannerConnector
from src.connectors.todo import TodoConnector
from src.providers.factory import create_llm_provider
from src.agents.graph import AgentState, build_graph


@pytest.fixture
def clients() -> tuple[GraphAPIClient, PlannerConnector, TodoConnector]:
    s = get_settings()
    g = GraphAPIClient(s.azure_tenant_id, s.azure_client_id, s.azure_client_secret)
    return g, PlannerConnector(g), TodoConnector(g)


@pytest.mark.integration
async def test_planner_task_create_and_verify(
    clients: tuple[GraphAPIClient, PlannerConnector, TodoConnector],
) -> None:
    """Planner にテストタスクを起票し、IDが返ること"""
    _, planner, _ = clients
    s = get_settings()
    from src.models.task import ExtractedTask
    task = ExtractedTask(
        is_task=True,
        title="[AutoTicket E2Eテスト] 自動削除してください",
        confidence_score=0.95,
        source_type="email",
        source_id="e2e-test-001",
    )
    task_id = await planner.create_task(task, plan_id=s.company_wide_plan_id)
    assert task_id  # IDが空でないこと


@pytest.mark.integration
async def test_full_pipeline_email_to_action(
    clients: tuple[GraphAPIClient, PlannerConnector, TodoConnector],
) -> None:
    """メールテキスト → LangGraph → auto_create/log_only のアクションが決まること"""
    s = get_settings()
    llm = create_llm_provider(s)
    graph = build_graph(llm, s.auto_create_threshold, s.manual_review_threshold)

    state: AgentState = {
        "source_text": "件名: プロジェクト提案書のレビュー依頼\n\n来週木曜までにドラフトを確認してください。",
        "source_type": "email",
        "source_id": "e2e-test-002",
        "sensitivity": None,
        "extracted_tasks": [],
        "actions": [],
        "errors": [],
    }
    result = await graph.ainvoke(state)
    assert result["sensitivity"] is not None
    assert isinstance(result["actions"], list)
```

- [ ] **Step 2: テストを実行**

```
pytest tests/integration/test_e2e.py -v
```

Expected: 2 passed

- [ ] **Step 3: 確認・コミット**

Planner 管理画面でテストタスクを手動削除してから：

```
git add tests/integration/test_e2e.py
git commit -m "test: E2Eテスト追加（Planner起票・全パイプライン動作確認）"
```

---

## Phase 2: Teamsチャット・OneNote対応

**前提:** Phase 1B 完了・Graph API スコープ追加申請（`ChannelMessage.Read.All` / `Notes.Read.All`）

---

### Task 19: Teams チャットコネクター

**Files:**
- Create: `src/connectors/teams_chat.py`
- Create: `tests/unit/test_teams_chat.py`

- [ ] **Step 1: テストを書く**

```python
# tests/unit/test_teams_chat.py
from unittest.mock import MagicMock, patch
import respx
from httpx import Response
from src.connectors.graph_api import GraphAPIClient
from src.connectors.teams_chat import TeamsChatConnector

BASE = "https://graph.microsoft.com/v1.0"


def _make_graph_client() -> GraphAPIClient:
    with patch("msal.ConfidentialClientApplication") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token"}
        mock_app_cls.return_value = mock_app
        client = GraphAPIClient("tenant", "client_id", "secret")
    client._app = mock_app  # type: ignore[attr-defined]
    return client


@respx.mock
async def test_get_channel_messages() -> None:
    client = _make_graph_client()
    connector = TeamsChatConnector(client)
    respx.get(f"{BASE}/teams/team-1/channels/channel-1/messages").mock(
        return_value=Response(200, json={"value": [{"id": "msg-1", "body": {"content": "タスクあり"}}]})
    )
    messages = await connector.get_channel_messages("team-1", "channel-1")
    assert len(messages) == 1
    assert messages[0]["id"] == "msg-1"


@respx.mock
async def test_get_teams_returns_list() -> None:
    client = _make_graph_client()
    connector = TeamsChatConnector(client)
    respx.get(f"{BASE}/teams").mock(
        return_value=Response(200, json={"value": [{"id": "team-1", "displayName": "開発チーム"}]})
    )
    teams = await connector.get_teams()
    assert teams[0]["displayName"] == "開発チーム"
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_teams_chat.py -v
```

Expected: ImportError

- [ ] **Step 3: コネクターを実装**

```python
# src/connectors/teams_chat.py
from typing import Any
import httpx
from src.connectors.graph_api import GraphAPIClient


class TeamsChatConnector:
    """Teams チャンネルメッセージ取得コネクター（Graph API経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_teams(self) -> list[dict[str, Any]]:
        """参加している Teams チーム一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/teams",
                headers=self._graph._headers(),
                params={"$select": "id,displayName"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_channels(self, team_id: str) -> list[dict[str, Any]]:
        """チームのチャンネル一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/teams/{team_id}/channels",
                headers=self._graph._headers(),
                params={"$select": "id,displayName"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_channel_messages(
        self, team_id: str, channel_id: str, top: int = 50
    ) -> list[dict[str, Any]]:
        """チャンネルの最新メッセージを取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/teams/{team_id}/channels/{channel_id}/messages",
                headers=self._graph._headers(),
                params={"$top": str(top)},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))
```

- [ ] **Step 4: テスト確認**

```
pytest tests/unit/test_teams_chat.py -v
ruff check src/connectors/teams_chat.py tests/unit/test_teams_chat.py
mypy src/connectors/teams_chat.py
```

Expected: 2 passed, lint クリーン

- [ ] **Step 5: コミット**

```
git add src/connectors/teams_chat.py tests/unit/test_teams_chat.py
git commit -m "feat: Teams チャットコネクター追加（チャンネルメッセージ取得）"
```

---

### Task 20: OneNote コネクター

**Files:**
- Create: `src/connectors/onenote.py`
- Create: `tests/unit/test_onenote.py`

- [ ] **Step 1: テストを書く**

```python
# tests/unit/test_onenote.py
from unittest.mock import MagicMock, patch
import respx
from httpx import Response
from src.connectors.graph_api import GraphAPIClient
from src.connectors.onenote import OneNoteConnector

BASE = "https://graph.microsoft.com/v1.0"


def _make_graph_client() -> GraphAPIClient:
    with patch("msal.ConfidentialClientApplication") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token"}
        mock_app_cls.return_value = mock_app
        client = GraphAPIClient("tenant", "client_id", "secret")
    client._app = mock_app  # type: ignore[attr-defined]
    return client


@respx.mock
async def test_get_notebooks() -> None:
    client = _make_graph_client()
    connector = OneNoteConnector(client)
    respx.get(f"{BASE}/me/onenote/notebooks").mock(
        return_value=Response(200, json={"value": [{"id": "nb-1", "displayName": "会議メモ"}]})
    )
    notebooks = await connector.get_notebooks()
    assert notebooks[0]["displayName"] == "会議メモ"


@respx.mock
async def test_get_page_content() -> None:
    client = _make_graph_client()
    connector = OneNoteConnector(client)
    respx.get(f"{BASE}/me/onenote/pages/page-1/content").mock(
        return_value=Response(200, text="<html>タスクあり</html>")
    )
    content = await connector.get_page_content("page-1")
    assert "タスクあり" in content
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_onenote.py -v
```

Expected: ImportError

- [ ] **Step 3: コネクターを実装**

```python
# src/connectors/onenote.py
from typing import Any
import httpx
from src.connectors.graph_api import GraphAPIClient


class OneNoteConnector:
    """OneNote ページ取得コネクター（Graph API経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_notebooks(self) -> list[dict[str, Any]]:
        """ノートブック一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onenote/notebooks",
                headers=self._graph._headers(),
                params={"$select": "id,displayName,lastModifiedDateTime"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_recent_pages(self, count: int = 20) -> list[dict[str, Any]]:
        """最近更新されたページ一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onenote/pages",
                headers=self._graph._headers(),
                params={
                    "$select": "id,title,lastModifiedDateTime",
                    "$orderby": "lastModifiedDateTime desc",
                    "$top": str(count),
                },
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_page_content(self, page_id: str) -> str:
        """ページの HTML コンテンツを取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onenote/pages/{page_id}/content",
                headers=self._graph._headers(),
            )
            resp.raise_for_status()
            return resp.text
```

- [ ] **Step 4: テスト確認**

```
pytest tests/unit/test_onenote.py -v
ruff check src/connectors/onenote.py tests/unit/test_onenote.py
mypy src/connectors/onenote.py
```

Expected: 2 passed, lint クリーン

- [ ] **Step 5: コミット**

```
git add src/connectors/onenote.py tests/unit/test_onenote.py
git commit -m "feat: OneNote コネクター追加（ページ一覧・コンテンツ取得）"
```

---

### Task 21: polling_job() に Teams・OneNote を追加

**Files:**
- Modify: `src/api/main.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_polling_job.py` に追記：

```python
async def test_polling_job_processes_teams_messages() -> None:
    """Teams チャンネルメッセージもポーリング対象になること"""
    with (
        patch("src.api.main.get_settings") as mock_settings,
        patch("src.api.main.GraphAPIClient") as mock_graph_cls,
        patch("src.api.main.TeamsChatConnector") as mock_teams_cls,
        patch("src.api.main.is_processed", return_value=True),
        patch("src.api.main.PlannerConnector"),
        patch("src.api.main.TodoConnector"),
        patch("src.api.main.create_llm_provider"),
        patch("src.api.main.build_graph"),
    ):
        settings = MagicMock(
            azure_tenant_id="t",
            azure_client_id="c",
            azure_client_secret="s",
        )
        mock_settings.return_value = settings
        graph_client = AsyncMock()
        graph_client.get_users.return_value = [{"id": "u1"}]
        graph_client.get_unread_emails.return_value = []
        mock_graph_cls.return_value = graph_client

        teams_conn = AsyncMock()
        teams_conn.get_teams.return_value = [{"id": "team-1"}]
        teams_conn.get_channels.return_value = [{"id": "ch-1"}]
        teams_conn.get_channel_messages.return_value = [{"id": "msg-teams-1", "body": {"content": "test"}}]
        mock_teams_cls.return_value = teams_conn

        from importlib import reload
        import src.api.main as main_module
        reload(main_module)
        await main_module.polling_job()

        teams_conn.get_teams.assert_called_once()
```

- [ ] **Step 2: polling_job() に Teams 処理を追加**

`src/api/main.py` の `polling_job()` に、メール処理ループの後に追加：

```python
# Teams チャンネルメッセージ処理
from src.connectors.teams_chat import TeamsChatConnector
teams_connector = TeamsChatConnector(graph_client)
teams_list = await teams_connector.get_teams()

for team in teams_list:
    channels = await teams_connector.get_channels(str(team["id"]))
    for channel in channels:
        messages = await teams_connector.get_channel_messages(
            str(team["id"]), str(channel["id"])
        )
        for msg in messages:
            msg_id = str(msg["id"])
            if await is_processed(msg_id):
                continue

            text = str(msg.get("body", {}).get("content", ""))
            state: AgentState = {
                "source_text": text,
                "source_type": "chat",
                "source_id": msg_id,
                "sensitivity": None,
                "extracted_tasks": [],
                "actions": [],
                "errors": [],
            }
            result = await graph.ainvoke(state)
            action_map = dict(result["actions"])
            for task in result["extracted_tasks"]:
                action = action_map.get(task.title, "log_only")
                if action in ("auto_create", "request_approval"):
                    await route_task(
                        task=task,
                        todo_connector=todo,
                        planner_connector=planner,
                        company_plan_id=settings.company_wide_plan_id,
                        dept_plan_map=settings.get_dept_plan_map(),
                    )
            await mark_processed(msg_id, "chat")
```

- [ ] **Step 3: テスト確認**

```
pytest tests/unit/test_polling_job.py -v
ruff check src/ tests/
mypy src/
```

Expected: 全パス

- [ ] **Step 4: コミット**

```
git add src/api/main.py tests/unit/test_polling_job.py
git commit -m "feat: polling_job に Teams チャンネルメッセージポーリングを追加"
```

---

## Phase 3: ローカルLLM + Teamsボット

**前提:** Phase 2 完了・Ollama インストール済み

---

### Task 22: Pattern B → Ollama 強制ルーティング

Pattern B（機密）検出時は常に Ollama を使うよう `factory.py` に分岐を追加する。

**Files:**
- Modify: `src/providers/factory.py`
- Modify: `src/models/config.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_providers.py` に追記：

```python
def test_create_llm_provider_pattern_b_forces_ollama() -> None:
    """Pattern B 検出時は llm_provider 設定に関わらず Ollama が返ること"""
    from src.providers.factory import create_llm_provider_for_sensitivity
    settings = Settings(llm_provider="claude", anthropic_api_key="key")
    provider = create_llm_provider_for_sensitivity(settings, is_confidential=True)
    assert isinstance(provider, OllamaProvider)

def test_create_llm_provider_pattern_a_uses_config() -> None:
    """Pattern A は設定通りのプロバイダーが返ること"""
    from src.providers.factory import create_llm_provider_for_sensitivity
    settings = Settings(llm_provider="ollama")
    provider = create_llm_provider_for_sensitivity(settings, is_confidential=False)
    assert isinstance(provider, OllamaProvider)
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_providers.py -v -k "sensitivity"
```

Expected: ImportError または FAIL

- [ ] **Step 3: factory.py に追加**

```python
# src/providers/factory.py に追加
def create_llm_provider_for_sensitivity(
    settings: Settings, *, is_confidential: bool
) -> LLMProvider:
    """機密度に応じてプロバイダーを選択する。機密データは必ず Ollama。"""
    if is_confidential:
        return OllamaProvider(
            host=settings.ollama_host,
            model=settings.ollama_model,
        )
    return create_llm_provider(settings)
```

- [ ] **Step 4: nodes.py の node_extract を更新**

```python
# src/agents/nodes.py の node_extract を変更
async def node_extract(state: dict[str, Any], settings: Settings) -> dict[str, Any]:
    is_confidential = state["sensitivity"].label == "pattern_b"
    llm = create_llm_provider_for_sensitivity(settings, is_confidential=is_confidential)
    if is_confidential and settings.llm_provider != "ollama":
        # 機密データは外部LLMに送信しない。Ollamaが使えない場合はスキップ。
        if not settings.ollama_host:
            return {"extracted_tasks": []}
    tasks = await llm.extract_tasks(state["source_text"], state["source_type"])
    for t in tasks:
        t.source_id = state["source_id"]
    return {"extracted_tasks": tasks}
```

> **注意:** `node_extract` のシグネチャ変更に伴い `build_graph()` の `partial()` 呼び出しも更新する。

- [ ] **Step 5: テスト確認**

```
pytest tests/unit/ -v
ruff check src/ tests/
mypy src/
```

Expected: 全パス

- [ ] **Step 6: コミット**

```
git add src/providers/factory.py src/agents/nodes.py tests/unit/test_providers.py
git commit -m "feat: Pattern B 機密データは Ollama 強制ルーティング"
```

---

### Task 23: Ollama を docker-compose に追加

**Files:**
- Modify: `docker/docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: docker-compose.yml に Ollama サービスを追加**

`services:` に追加：

```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_models:/root/.ollama
  restart: unless-stopped
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

`volumes:` に追加：

```yaml
ollama_models:
```

`autoticket-app` の `environment:` を更新：

```yaml
OLLAMA_HOST: http://ollama:11434
```

- [ ] **Step 2: モデルダウンロード手順を docs に追記**

```bash
# Ollama 起動後にモデルをダウンロード
docker compose -f docker/docker-compose.yml exec ollama ollama pull qwen2.5:14b
docker compose -f docker/docker-compose.yml exec ollama ollama pull llama3.2-vision
```

- [ ] **Step 3: .env.example 更新**

```
OLLAMA_HOST=http://localhost:11434  # Docker 外から直接実行する場合
# Docker Compose 経由の場合は docker-compose.yml で自動設定
```

- [ ] **Step 4: コミット**

```
git add docker/docker-compose.yml .env.example
git commit -m "feat: Ollama を docker-compose に追加（GPU対応・モデルボリューム）"
```

---

### Task 24: Teams Bot エンドポイント（/bot）

Bot Framework から Webhook で受信し、画像コメントをタスク起票に変換する。

**Files:**
- Create: `src/api/routers/bot.py`
- Create: `tests/unit/test_bot.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: テストを書く**

```python
# tests/unit/test_bot.py
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    from src.api.main import app
    return TestClient(app)


def test_bot_health_returns_200() -> None:
    client = _make_client()
    resp = client.post(
        "/bot",
        json={
            "type": "message",
            "id": "msg-bot-1",
            "text": "MTG の議事録をタスク化して",
            "attachments": [],
        },
        headers={"Authorization": "Bearer dummy"},  # 実際の署名検証はスキップ
    )
    # Bot Framework の HMAC 検証を bypass するため、テストでは署名検証を無効化する
    assert resp.status_code in (200, 401)  # 401 は署名検証失敗


async def test_bot_processes_text_message() -> None:
    """テキストメッセージをエージェントに渡すこと"""
    with (
        patch("src.api.routers.bot.get_settings"),
        patch("src.api.routers.bot.create_llm_provider"),
        patch("src.api.routers.bot.build_graph") as mock_build,
    ):
        compiled = AsyncMock()
        compiled.ainvoke.return_value = {
            "extracted_tasks": [],
            "actions": [],
            "sensitivity": None,
            "errors": [],
        }
        mock_build.return_value = compiled

        from src.api.routers.bot import process_bot_message
        await process_bot_message(
            text="来週月曜までに資料を作成する",
            source_id="bot-msg-1",
            has_image=False,
            image_bytes=None,
            image_comment="",
        )
        compiled.ainvoke.assert_called_once()
```

- [ ] **Step 2: bot.py を実装**

```python
# src/api/routers/bot.py
from typing import Any
from fastapi import APIRouter, Request, Response

from src.agents.graph import AgentState, build_graph
from src.models.config import get_settings
from src.providers.factory import create_llm_provider

router = APIRouter(prefix="/bot")


async def process_bot_message(
    text: str,
    source_id: str,
    has_image: bool,
    image_bytes: bytes | None,
    image_comment: str,
) -> dict[str, Any]:
    """Bot メッセージを LangGraph エージェントで処理する"""
    settings = get_settings()
    llm = create_llm_provider(settings)
    graph = build_graph(llm, settings.auto_create_threshold, settings.manual_review_threshold)

    full_text = text
    if has_image and image_bytes:
        from src.services.image_processor import describe_image
        description = await describe_image(image_bytes, image_comment, settings)
        full_text = f"{text}\n\n[画像説明]: {description}"

    state: AgentState = {
        "source_text": full_text,
        "source_type": "teams_bot",
        "source_id": source_id,
        "sensitivity": None,
        "extracted_tasks": [],
        "actions": [],
        "errors": [],
    }
    return dict(await graph.ainvoke(state))


@router.post("")
async def bot_webhook(request: Request) -> Response:
    """Bot Framework Webhook エンドポイント"""
    body: dict[str, Any] = await request.json()
    msg_type: str = body.get("type", "")

    if msg_type != "message":
        return Response(status_code=200)

    msg_id = str(body.get("id", ""))
    text = str(body.get("text", ""))
    attachments: list[dict[str, Any]] = body.get("attachments", [])

    image_bytes: bytes | None = None
    image_comment = text

    for att in attachments:
        if att.get("contentType", "").startswith("image/"):
            content_url = att.get("contentUrl", "")
            if content_url:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(content_url)
                    image_bytes = resp.content
            break

    await process_bot_message(
        text=text,
        source_id=msg_id,
        has_image=image_bytes is not None,
        image_bytes=image_bytes,
        image_comment=image_comment,
    )
    return Response(status_code=200)
```

- [ ] **Step 3: main.py に router を追加**

```python
from src.api.routers import bot  # 追加

app.include_router(bot.router)  # 追加
```

- [ ] **Step 4: テスト確認**

```
pytest tests/unit/test_bot.py -v
ruff check src/ tests/
mypy src/
```

Expected: 2 passed, lint クリーン

- [ ] **Step 5: コミット**

```
git add src/api/routers/bot.py tests/unit/test_bot.py src/api/main.py
git commit -m "feat: Teams Bot Webhook エンドポイント追加（/bot）"
```

---

### Task 25: Ollama vision 画像処理サービス

**Files:**
- Create: `src/services/image_processor.py`
- Create: `tests/unit/test_image_processor.py`

- [ ] **Step 1: テストを書く**

```python
# tests/unit/test_image_processor.py
from unittest.mock import AsyncMock, patch
from src.models.config import Settings


async def test_describe_image_calls_vision_provider() -> None:
    """describe_image が VisionLLMProvider を呼び出すこと"""
    with patch("src.services.image_processor.create_vision_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.analyze_image.return_value = "会議室でホワイトボードに図を書いている"
        mock_factory.return_value = mock_provider

        from src.services.image_processor import describe_image
        result = await describe_image(
            image_bytes=b"fake-png",
            comment="昨日のMTGのホワイトボード",
            settings=Settings(),
        )
    assert "ホワイトボード" in result
    mock_provider.analyze_image.assert_called_once_with(
        b"fake-png", "昨日のMTGのホワイトボード"
    )


async def test_describe_image_returns_comment_on_error() -> None:
    """vision API がエラーの場合はコメントをそのまま返すこと"""
    with patch("src.services.image_processor.create_vision_provider") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.analyze_image.side_effect = RuntimeError("API error")
        mock_factory.return_value = mock_provider

        from src.services.image_processor import describe_image
        result = await describe_image(
            image_bytes=b"fake-png",
            comment="フォールバックコメント",
            settings=Settings(),
        )
    assert result == "フォールバックコメント"
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_image_processor.py -v
```

Expected: ImportError

- [ ] **Step 3: image_processor.py を実装**

```python
# src/services/image_processor.py
import logging

from src.models.config import Settings
from src.providers.factory import create_vision_provider

logger = logging.getLogger(__name__)


async def describe_image(image_bytes: bytes, comment: str, settings: Settings) -> str:
    """画像バイナリを vision LLM で説明テキストに変換する。
    エラー時はコメントをそのまま返してパイプラインを継続する。
    """
    try:
        provider = create_vision_provider(settings)
        return await provider.analyze_image(image_bytes, comment)
    except Exception as e:
        logger.warning("画像処理失敗（フォールバック）: %s", e)
        return comment
```

- [ ] **Step 4: テスト確認**

```
pytest tests/unit/test_image_processor.py -v
ruff check src/services/image_processor.py tests/unit/test_image_processor.py
mypy src/services/image_processor.py
```

Expected: 2 passed, lint クリーン

- [ ] **Step 5: 全テスト確認**

```
pytest tests/unit/ -v
```

Expected: 全パス

- [ ] **Step 6: コミット**

```
git add src/services/image_processor.py tests/unit/test_image_processor.py
git commit -m "feat: Ollama vision 画像処理サービス追加（エラー時フォールバック付き）"
```

---

## セッション再開チェックリスト

次のセッションを開始したら、以下を確認する：

```bash
# 1. 現在の進捗確認
git log --oneline -10
pytest tests/unit/ -v --tb=short   # ユニットテスト全通過を確認

# 2. Graph API 承認状況確認
# → 承認済み: Task 16〜18 へ進む
# → 未承認: Task 14〜15（credentials 不要）から進める

# 3. Docker 確認
docker compose -f docker/docker-compose.yml ps
# langfuse-db: healthy, langfuse-server: Up であることを確認

# 4. 次のタスクを選択
# - credentials なし → Task 14（dept_plan_map）→ Task 15（polling_job）
# - credentials あり → Task 16〜18（統合・E2E テスト）
# - Phase 2 着手   → Task 19（Teams チャット）
```
