# F-32 サブタスク自動作成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク詳細画面の「サブタスク」タブに「🤖 AI生成」ボタンを追加し、Gemini がタスクタイトル・説明から3〜6個のサブタスク候補を提案、ユーザーが選択して一括作成できるようにする。

**Architecture:** バックエンドは `GeminiProvider` に `generate_subtasks()` メソッドを追加し、`POST /api/v1/tasks/{task_id}/generate-subtasks` エンドポイントが提案リストを返す（作成はしない）。フロントエンドはチェックボックスリストで候補を表示し、選択されたものだけ既存の `POST /tasks` で作成する。

**Tech Stack:** Python/FastAPI + google-genai SDK（Gemini 2.5 Flash） / React + TanStack Query + Ant Design

---

## ファイル構成

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/providers/gemini.py` | 修正 | `_SUBTASK_SYSTEM` 定数・`generate_subtasks()` メソッド追加 |
| `src/models/task_web.py` | 修正 | `GenerateSubtasksResponse` Pydantic モデル追加 |
| `src/api/routers/tasks_crud.py` | 修正 | `POST /{task_id}/generate-subtasks` エンドポイント追加 |
| `tests/unit/test_generate_subtasks.py` | 新規 | エンドポイントのユニットテスト（Gemini モック） |
| `frontend/src/hooks/useTaskDetails.ts` | 修正 | `useGenerateSubtasks` フック追加 |
| `frontend/src/pages/Tasks/components/SubtasksPanel.tsx` | 修正 | AI生成UIの追加 |

---

## Task 1: GeminiProvider に generate_subtasks() を追加

**Files:**
- Modify: `src/providers/gemini.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_generate_subtasks.py` を新規作成:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")


def _make_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_generate_subtasks_route_exists() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = [r.path for r in app.routes]
    assert "/api/v1/tasks/{task_id}/generate-subtasks" in routes


def test_generate_subtasks_task_not_found() -> None:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/generate-subtasks")
    assert resp.status_code == 404


def test_generate_subtasks_returns_suggestions() -> None:
    from src.db.models import Task

    mock_task = MagicMock(spec=Task)
    mock_task.id = uuid.uuid4()
    mock_task.title = "議事録のまとめ"
    mock_task.description = "先週の会議内容を整理してチームに共有する"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)

    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.generate_subtasks = AsyncMock(
            return_value=["会議メモを収集する", "要点を箇条書きにする", "Teamsに投稿する"]
        )
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/generate-subtasks")

    assert resp.status_code == 200
    data = resp.json()
    assert "suggested_titles" in data
    assert data["suggested_titles"] == ["会議メモを収集する", "要点を箇条書きにする", "Teamsに投稿する"]


def test_generate_subtasks_requires_auth() -> None:
    app2 = FastAPI()
    app2.include_router(router)
    client = TestClient(app2, raise_server_exceptions=False)
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/generate-subtasks")
    assert resp.status_code == 401
```

- [ ] **Step 2: テストが失敗することを確認**

```powershell
python -m pytest tests/unit/test_generate_subtasks.py -v
```

期待: `FAILED` — `ImportError` または `AssertionError`（ルートが存在しない）

- [ ] **Step 3: `GenerateSubtasksResponse` を `task_web.py` に追加**

`src/models/task_web.py` の末尾に追記（`RescheduleResponse` の後）:

```python
# --- AI サブタスク生成 ---


class GenerateSubtasksResponse(BaseModel):
    suggested_titles: list[str]
```

- [ ] **Step 4: `_SUBTASK_SYSTEM` と `generate_subtasks()` を `gemini.py` に追加**

`src/providers/gemini.py` を以下のように変更:

```python
import json

from google import genai
from google.genai import types

from src.models.task import ExtractedTask
from src.providers.ollama import _EXTRACT_SYSTEM

_SUBTASK_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "タスクのタイトルと説明から、そのタスクを完了するために必要なサブタスクを3〜6個提案してください。"
    "各サブタスクは具体的で実行可能な短いアクション（30文字以内）にしてください。"
    "以下のJSON形式のみで返してください。説明文は不要です:\n"
    '{"subtasks": ["サブタスク名1", "サブタスク名2", "サブタスク名3"]}'
)


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=f"以下のテキストからタスクを抽出:\n\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=_EXTRACT_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        raw: list[dict[str, object]] = json.loads(resp.text or "[]")
        return [
            ExtractedTask.model_validate({**t, "source_type": source_type, "source_id": ""})
            for t in raw
            if t.get("is_task")
        ]

    async def analyze_image(self, image: bytes, comment: str) -> str:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image, mime_type="image/jpeg"),
                f"画像の内容を説明してください。補足コメント: {comment}",
            ],
        )
        return resp.text or ""

    async def generate_subtasks(self, title: str, description: str | None) -> list[str]:
        prompt = f"タスクタイトル: {title}"
        if description:
            prompt += f"\n説明: {description}"
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SUBTASK_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        data: dict[str, list[str]] = json.loads(resp.text or '{"subtasks": []}')
        return data.get("subtasks", [])
```

---

## Task 2: バックエンドエンドポイント追加

**Files:**
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: エンドポイントを `tasks_crud.py` に追加**

`tasks_crud.py` の import ブロックを更新（ファイル先頭部分）:

```python
import re
import uuid
from collections import deque
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskAssignee, TaskDependency, TaskTag, UserProfile
from src.models.config import get_settings
from src.models.task_web import (
    GenerateSubtasksResponse,
    RescheduleRequest,
    RescheduleResponse,
    SimilarTaskResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
from src.providers.gemini import GeminiProvider
```

次に、ファイル末尾（`reschedule_task` 関数の後）に以下を追記:

```python
@router.post("/{task_id}/generate-subtasks", response_model=GenerateSubtasksResponse)
async def generate_subtasks(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> GenerateSubtasksResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    settings = get_settings()
    provider = GeminiProvider(api_key=settings.google_api_key, model=settings.gemini_model)
    titles = await provider.generate_subtasks(task.title, task.description)
    return GenerateSubtasksResponse(suggested_titles=titles)
```

- [ ] **Step 2: テストを実行して全件 PASS を確認**

```powershell
python -m pytest tests/unit/test_generate_subtasks.py -v
```

期待出力:
```
tests/unit/test_generate_subtasks.py::test_generate_subtasks_route_exists PASSED
tests/unit/test_generate_subtasks.py::test_generate_subtasks_task_not_found PASSED
tests/unit/test_generate_subtasks.py::test_generate_subtasks_returns_suggestions PASSED
tests/unit/test_generate_subtasks.py::test_generate_subtasks_requires_auth PASSED

4 passed
```

- [ ] **Step 3: 既存テスト全件が引き続き PASS することを確認**

```powershell
python -m pytest tests/unit/test_auth.py tests/unit/test_tasks_crud_router.py -v
```

期待: 全件 PASSED

- [ ] **Step 4: コミット**

```powershell
git add src/providers/gemini.py src/models/task_web.py src/api/routers/tasks_crud.py tests/unit/test_generate_subtasks.py
git commit -m "feat: F-32 サブタスク自動生成バックエンド（POST /tasks/{id}/generate-subtasks）"
```

---

## Task 3: フロントエンド hook 追加

**Files:**
- Modify: `frontend/src/hooks/useTaskDetails.ts`

- [ ] **Step 1: `useGenerateSubtasks` フックを追加**

`frontend/src/hooks/useTaskDetails.ts` の末尾に追記:

```typescript
export function useGenerateSubtasks(taskId: string) {
  return useMutation<{ suggested_titles: string[] }, Error>({
    mutationFn: () =>
      api.post(`/tasks/${taskId}/generate-subtasks`).then((r) => r.data),
  })
}
```

- [ ] **Step 2: TypeScript 型チェック**

```powershell
cd frontend
npx tsc --noEmit
```

期待: エラーなし

---

## Task 4: フロントエンド UI 追加（SubtasksPanel）

**Files:**
- Modify: `frontend/src/pages/Tasks/components/SubtasksPanel.tsx`

- [ ] **Step 1: SubtasksPanel を以下に置き換える**

```tsx
import { RobotOutlined } from '@ant-design/icons'
import { Button, Checkbox, Input, Space, Spin, Tag, Typography } from 'antd'
import { useState } from 'react'
import {
  useCreateSubtask,
  useGenerateSubtasks,
  useSubtasks,
  useUpdateSubtaskStatus,
} from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
}

export default function SubtasksPanel({ taskId }: Props) {
  const { data: subtasks = [] } = useSubtasks(taskId)
  const createSubtask = useCreateSubtask(taskId)
  const updateStatus = useUpdateSubtaskStatus(taskId)
  const generateSubtasks = useGenerateSubtasks(taskId)
  const [newTitle, setNewTitle] = useState('')
  const [suggestions, setSuggestions] = useState<string[] | null>(null)
  const [checked, setChecked] = useState<Set<string>>(new Set())

  const handleAdd = async () => {
    if (!newTitle.trim()) return
    await createSubtask.mutateAsync(newTitle.trim())
    setNewTitle('')
  }

  const handleGenerate = async () => {
    const result = await generateSubtasks.mutateAsync()
    setSuggestions(result.suggested_titles)
    setChecked(new Set(result.suggested_titles))
  }

  const toggleChecked = (title: string) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(title)) next.delete(title)
      else next.add(title)
      return next
    })
  }

  const handleCreateChecked = async () => {
    for (const title of suggestions ?? []) {
      if (checked.has(title)) {
        await createSubtask.mutateAsync(title)
      }
    }
    setSuggestions(null)
    setChecked(new Set())
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {subtasks.map((s) => (
        <Space key={s.id}>
          <Checkbox
            checked={s.status === 'completed'}
            onChange={(e) =>
              updateStatus.mutate({
                id: s.id,
                status: e.target.checked ? 'completed' : 'not_started',
              })
            }
          />
          <Typography.Text delete={s.status === 'completed'}>{s.title}</Typography.Text>
          <Tag>{s.status}</Tag>
        </Space>
      ))}

      <Space.Compact style={{ width: '100%' }}>
        <Input
          placeholder="サブタスクを追加..."
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onPressEnter={handleAdd}
        />
        <Button onClick={handleAdd} loading={createSubtask.isPending}>
          追加
        </Button>
      </Space.Compact>

      {suggestions === null ? (
        <Button
          icon={<RobotOutlined />}
          onClick={handleGenerate}
          loading={generateSubtasks.isPending}
        >
          AI でサブタスクを提案
        </Button>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text type="secondary">提案されたサブタスク（追加するものを選択）</Typography.Text>
          {generateSubtasks.isPending ? (
            <Spin />
          ) : (
            suggestions.map((title) => (
              <Checkbox
                key={title}
                checked={checked.has(title)}
                onChange={() => toggleChecked(title)}
              >
                {title}
              </Checkbox>
            ))
          )}
          <Space>
            <Button
              type="primary"
              onClick={handleCreateChecked}
              loading={createSubtask.isPending}
              disabled={checked.size === 0}
            >
              選択して追加（{checked.size}件）
            </Button>
            <Button onClick={() => { setSuggestions(null); setChecked(new Set()) }}>
              キャンセル
            </Button>
          </Space>
        </Space>
      )}
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript 型チェック**

```powershell
cd frontend
npx tsc --noEmit
```

期待: エラーなし

- [ ] **Step 3: 動作確認**

1. `uvicorn src.api.main:app --reload --port 8000` でバックエンド起動
2. `cd frontend && npm run dev` でフロントエンド起動
3. `http://localhost:5173` にアクセスしてログイン（DEV_MODE=true の場合は開発用ログイン）
4. 任意のタスク詳細 → 「サブタスク」タブ
5. 「AI でサブタスクを提案」ボタンをクリック
6. チェックボックスリストが表示されることを確認
7. 任意のチェックを外して「選択して追加」→ サブタスクが作成されることを確認

- [ ] **Step 4: コミット**

```powershell
git add frontend/src/hooks/useTaskDetails.ts frontend/src/pages/Tasks/components/SubtasksPanel.tsx
git commit -m "feat: F-32 サブタスク自動生成UI（AI提案→チェックボックス選択→一括作成）"
```

---

## 完了確認チェックリスト

- [ ] `python -m pytest tests/unit/test_generate_subtasks.py -v` — 4 passed
- [ ] `python -m pytest tests/unit/test_auth.py tests/unit/test_tasks_crud_router.py -v` — 全件 passed
- [ ] `npx tsc --noEmit` — エラーなし
- [ ] ブラウザで AI提案 → 選択 → 作成の一連フローが動作する
