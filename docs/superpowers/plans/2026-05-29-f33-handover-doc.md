# F-33 引き継ぎドキュメント自動生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 未完了タスク一覧（コメント付き）を Gemini に渡し、Markdown 形式の引き継ぎ書を生成する `POST /api/v1/tasks/generate-handover` エンドポイントと、タスク一覧ページのボタン+モーダル UI を実装する。

**Architecture:** `HandoverRequest`/`GenerateHandoverResponse` モデルを `task_web.py` に追加 → `_HANDOVER_SYSTEM` プロンプトと `generate_handover_doc` メソッドを `GeminiProvider` に追加 → `tasks_crud.py` にエンドポイントを追加（leader 以上のロールを持つユーザーのみ他者を対象可） → フロントエンドでボタン+モーダルを追加。

**Tech Stack:** FastAPI, SQLAlchemy async (`selectinload`), Pydantic v2, Google Generative AI SDK, React, Ant Design, TanStack Query `useMutation`

---

## ファイル構成

| ファイル | 変更種別 | 担当内容 |
|---------|---------|---------|
| `src/models/task_web.py` | 修正 | `HandoverRequest` / `GenerateHandoverResponse` 追加 |
| `src/providers/gemini.py` | 修正 | `_HANDOVER_SYSTEM` + `generate_handover_doc` メソッド追加 |
| `src/api/routers/tasks_crud.py` | 修正 | `POST /generate-handover` エンドポイント追加・インポート更新 |
| `tests/unit/test_handover.py` | 新規 | 6 件のユニットテスト |
| `frontend/src/lib/api.ts` | 修正 | `HandoverResponse` インターフェース + `generateHandover` 関数 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | 引き継ぎ書ボタン + ユーザー Select + 結果モーダル |

---

### Task 1: バックエンドモデル + GeminiProvider メソッド

**Files:**
- Modify: `src/models/task_web.py` (末尾に追加)
- Modify: `src/providers/gemini.py` (`_CLARIFY_SYSTEM` の後、`class GeminiProvider` の前)

- [ ] **Step 1: `HandoverRequest` / `GenerateHandoverResponse` を `task_web.py` 末尾に追加する**

`src/models/task_web.py` の末尾（現在 line 492 の `HourEstimate` の後）に追記する:

```python
# --- 引き継ぎドキュメント生成 (F-33) ---


class HandoverRequest(BaseModel):
    assignee_id: str | None = None  # None = 自分自身


class GenerateHandoverResponse(BaseModel):
    document: str  # Markdown 形式の引き継ぎ書
```

- [ ] **Step 2: `_HANDOVER_SYSTEM` と `generate_handover_doc` を `gemini.py` に追加する**

`src/providers/gemini.py` の `_CLARIFY_SYSTEM` 定数の後（`class GeminiProvider` の直前）に追加する:

```python
_HANDOVER_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "以下の未完了タスク一覧（コメント付き）を読み、"
    "引き継ぎ者が状況を即座に把握できる引き継ぎ書をMarkdown形式で作成してください。"
    "以下を含めてください:\n"
    "1. 概要（未完了タスク数・緊急度の高いもの）\n"
    "2. タスク別の現状・残作業・注意事項\n"
    "3. 引き継ぎ先へのメッセージ\n"
    "簡潔かつ具体的に書いてください。"
)
```

そして `GeminiProvider` クラスの末尾（`clarify_requirements` メソッドの後）にメソッドを追加する:

```python
    async def generate_handover_doc(self, tasks_text: str) -> str:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=f"以下の未完了タスク情報から引き継ぎ書を生成してください:\n\n{tasks_text}",
            config=types.GenerateContentConfig(
                system_instruction=_HANDOVER_SYSTEM,
            ),
        )
        return resp.text or ""
```

- [ ] **Step 3: テスト（GeminiProvider のメソッドが存在するか確認）**

Run: `pytest tests/unit/test_providers.py -v`
Expected: PASS（既存テストが通ること）

- [ ] **Step 4: Commit**

```bash
git add src/models/task_web.py src/providers/gemini.py
git commit -m "feat: F-33 HandoverRequest/GenerateHandoverResponse モデル + GeminiProvider.generate_handover_doc 追加"
```

---

### Task 2: バックエンドエンドポイント + ユニットテスト（TDD）

**Files:**
- Create: `tests/unit/test_handover.py`
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: テストファイルを作成して失敗を確認する**

`tests/unit/test_handover.py` を新規作成する:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.models.config import Settings

_FAKE_SETTINGS = Settings(
    gemini_api_key="fake-key",
    database_url="postgresql+asyncpg://x:x@localhost/x",
)
_EMPTY_SETTINGS = Settings(
    gemini_api_key="",
    database_url="postgresql+asyncpg://x:x@localhost/x",
)

_member_user = TokenPayload(
    sub="user-1", name="Member", email="m@t.com", roles=["member"], tid="tid"
)
_leader_user = TokenPayload(
    sub="leader-1", name="Leader", email="l@t.com", roles=["leader"], tid="tid"
)


def _make_client(mock_db: AsyncMock, user: TokenPayload = _member_user) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_task(
    *,
    title: str = "テスト作業",
    status: str = "in_progress",
    priority: str = "medium",
    due_date: object = None,
    description: str | None = None,
    comments: list | None = None,
) -> MagicMock:
    from src.db.models import Task

    task = MagicMock(spec=Task)
    task.title = title
    task.status = status
    task.priority = priority
    task.due_date = due_date
    task.description = description
    task.comments = comments if comments is not None else []
    return task


def _make_db(tasks: list) -> AsyncMock:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def test_generate_handover_own_tasks() -> None:
    """assignee_id=None → 自分の未完了タスクで引き継ぎ書生成・200"""
    mock_task = _make_task(title="設計書を書く")
    mock_db = _make_db([mock_task])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(return_value="# 引き継ぎ書\n\n内容")
            resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 200
    data = resp.json()
    assert "document" in data
    assert data["document"] != ""


def test_generate_handover_for_member_by_leader() -> None:
    """leader ロールで他メンバーの assignee_id を指定 → 200"""
    mock_task = _make_task(title="レポート作成")
    mock_db = _make_db([mock_task])
    client = _make_client(mock_db, user=_leader_user)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(return_value="# 引き継ぎ書")
            resp = client.post(
                "/api/v1/tasks/generate-handover",
                json={"assignee_id": "other-user-999"},
            )
    assert resp.status_code == 200


def test_generate_handover_member_cannot_target_others() -> None:
    """member ロールで他人の assignee_id を指定 → 403"""
    mock_db = _make_db([])
    client = _make_client(mock_db, user=_member_user)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        resp = client.post(
            "/api/v1/tasks/generate-handover",
            json={"assignee_id": "other-user-999"},
        )
    assert resp.status_code == 403


def test_generate_handover_no_tasks() -> None:
    """未完了タスクなし → 200・document が空でない"""
    mock_db = _make_db([])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(return_value="未完了タスクはありません。")
            resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 200
    assert resp.json()["document"] != ""


def test_generate_handover_gemini_error() -> None:
    """GeminiProvider が例外 → 503"""
    mock_task = _make_task()
    mock_db = _make_db([mock_task])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_FAKE_SETTINGS):
        with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
            instance = MockProvider.return_value
            instance.generate_handover_doc = AsyncMock(side_effect=RuntimeError("API error"))
            resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 503


def test_generate_handover_no_api_key() -> None:
    """gemini_api_key="" → 503"""
    mock_db = _make_db([])
    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=_EMPTY_SETTINGS):
        resp = client.post("/api/v1/tasks/generate-handover", json={"assignee_id": None})
    assert resp.status_code == 503
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `pytest tests/unit/test_handover.py -v`
Expected: FAIL（`404 Not Found` または ImportError）

- [ ] **Step 3: `tasks_crud.py` のインポートを更新する**

`src/api/routers/tasks_crud.py` の `from src.models.task_web import (...)` ブロックを以下に更新する（`GenerateHandoverResponse` と `HandoverRequest` を追加）:

```python
from src.models.task_web import (
    ClarifyIssue,
    ClarifyRequirementsResponse,
    GenerateHandoverResponse,
    GenerateSubtasksResponse,
    HandoverRequest,
    HourEstimate,
    RescheduleRequest,
    RescheduleResponse,
    SimilarTaskResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
```

- [ ] **Step 4: `POST /generate-handover` エンドポイントを追加する**

`tasks_crud.py` の `/extract` エンドポイント（現在 line 335〜357）の直後、`GET /{task_id}` エンドポイントの直前に追加する:

```python
@router.post("/generate-handover", response_model=GenerateHandoverResponse)
async def generate_handover(
    body: HandoverRequest,
    db: DbDep,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),
) -> GenerateHandoverResponse:
    target_user_id = body.assignee_id or current_user.sub

    if body.assignee_id and body.assignee_id != current_user.sub:
        user_level = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
        if user_level < ROLE_HIERARCHY.get("leader", 1):
            raise HTTPException(status_code=403, detail="リーダー以上の権限が必要です")

    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini API キーが設定されていません")

    result = await db.execute(
        select(Task)
        .join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .where(
            TaskAssignee.user_id == target_user_id,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .options(selectinload(Task.comments))
        .order_by(Task.due_date.asc().nulls_last())
    )
    tasks = result.scalars().all()

    lines: list[str] = []
    for task in tasks:
        lines.append(f"## {task.title}")
        lines.append(f"- ステータス: {task.status}")
        lines.append(f"- 優先度: {task.priority}")
        lines.append(f"- 期限: {task.due_date or '未設定'}")
        if task.description:
            lines.append(f"- 説明: {task.description}")
        recent = sorted(task.comments, key=lambda c: c.created_at, reverse=True)[:3]
        if recent:
            lines.append("- 最近のコメント:")
            for c in recent:
                lines.append(f"  - {c.content}")
        lines.append("")
    tasks_text = "\n".join(lines)

    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    try:
        document = await provider.generate_handover_doc(tasks_text)
    except Exception:
        logger.exception("Gemini generate_handover_doc failed")
        raise HTTPException(
            status_code=503, detail="引き継ぎ書の生成に失敗しました。しばらく後に再試行してください"
        )

    return GenerateHandoverResponse(document=document)
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `pytest tests/unit/test_handover.py -v`
Expected: 6 件 PASS

- [ ] **Step 6: 既存テスト全体が壊れていないことを確認する**

Run: `pytest tests/unit/ -v --tb=short`
Expected: PASS（既存テストも含めて全件通過）

- [ ] **Step 7: Commit**

```bash
git add tests/unit/test_handover.py src/api/routers/tasks_crud.py
git commit -m "feat: F-33 POST /tasks/generate-handover エンドポイント追加・テスト 6 件"
```

---

### Task 3: フロントエンド API 関数 + UI

**Files:**
- Modify: `frontend/src/lib/api.ts` (末尾に追加)
- Modify: `frontend/src/pages/Tasks/index.tsx` (インポート・ステート・JSX を追加)

- [ ] **Step 1: `HandoverResponse` と `generateHandover` を `api.ts` 末尾に追加する**

`frontend/src/lib/api.ts` の末尾（現在 `extractTasksFromText` 関数の後）に追記する:

```typescript
export interface HandoverResponse {
  document: string
}

export const generateHandover = async (assigneeId?: string): Promise<HandoverResponse> => {
  const { data } = await api.post<HandoverResponse>('/tasks/generate-handover', {
    assignee_id: assigneeId ?? null,
  })
  return data
}
```

- [ ] **Step 2: `Tasks/index.tsx` のインポートを更新する**

**アイコンのインポート**（現在の行）:
```typescript
import { PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
```
を以下に変更する:
```typescript
import { CopyOutlined, FileTextOutlined, PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
```

**TanStack Query のインポートを追加**（`import { useTasks, ...` の前の行に追加）:
```typescript
import { useMutation } from '@tanstack/react-query'
```

**`generateHandover` のインポートを追加**（`import type { Task } from '../../lib/api'` の行を更新）:
```typescript
import type { Task } from '../../lib/api'
import { generateHandover } from '../../lib/api'
```

- [ ] **Step 3: 引き継ぎ書用のステートと mutation を追加する**

`Tasks/index.tsx` のコンポーネント内（`const [extractModalOpen, setExtractModalOpen] = useState(false)` の後）に追加する:

```typescript
const [handoverOpen, setHandoverOpen] = useState(false)
const [handoverDoc, setHandoverDoc] = useState('')
const [handoverTarget, setHandoverTarget] = useState<string | undefined>()
const generateHandoverMutation = useMutation({
  mutationFn: (assigneeId: string | undefined) => generateHandover(assigneeId),
})
```

- [ ] **Step 4: ヘッダーのボタン群を更新する**

現在のヘッダー `<Space style={{ width: '100%', justifyContent: 'space-between' }}>` 内を以下に変更する（タイトルはそのまま、ボタン 2 つを `<Space>` でまとめて引き継ぎ書ボタンと Select を追加）:

```tsx
<Space style={{ width: '100%', justifyContent: 'space-between' }}>
  <Typography.Title level={3} style={{ margin: 0 }}>
    タスク一覧
  </Typography.Title>
  <Space>
    {canFilterByAssignee && (
      <Select
        placeholder="引き継ぎ対象者（未選択 = 自分）"
        allowClear
        options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
        value={handoverTarget}
        onChange={setHandoverTarget}
        style={{ width: 180 }}
      />
    )}
    <Button
      icon={<FileTextOutlined />}
      loading={generateHandoverMutation.isPending}
      onClick={async () => {
        try {
          const res = await generateHandoverMutation.mutateAsync(handoverTarget)
          setHandoverDoc(res.document)
          setHandoverOpen(true)
        } catch {
          void message.error('引き継ぎ書の生成に失敗しました')
        }
      }}
    >
      引き継ぎ書を生成
    </Button>
    <Button icon={<RobotOutlined />} onClick={() => setExtractModalOpen(true)}>
      テキストから作成
    </Button>
    <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
      新規タスク
    </Button>
  </Space>
</Space>
```

- [ ] **Step 5: 結果モーダルを追加する**

`<ExtractModal .../>` の直前に引き継ぎ書モーダルを追加する:

```tsx
<Modal
  title="引き継ぎ書"
  open={handoverOpen}
  onCancel={() => setHandoverOpen(false)}
  width={720}
  footer={
    <Button
      icon={<CopyOutlined />}
      onClick={() => {
        void navigator.clipboard.writeText(handoverDoc)
        void message.success('コピーしました')
      }}
    >
      クリップボードにコピー
    </Button>
  }
>
  <Input.TextArea value={handoverDoc} rows={20} readOnly style={{ fontFamily: 'monospace' }} />
</Modal>
```

- [ ] **Step 6: TypeScript エラーがないことを確認する**

Run: `cd frontend && npx tsc --noEmit`
Expected: エラーなし（0 件）

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/Tasks/index.tsx
git commit -m "feat: F-33 引き継ぎ書ボタン + モーダル UI 追加"
```
