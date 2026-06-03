# 横断全文検索（Cmd+K コマンドパレット）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク名・説明・コメントを横断検索できる Cmd+K コマンドパレットをアプリ全体に追加する。

**Architecture:** 新規ルーター `src/api/routers/search.py` に `GET /api/v1/search?q=` エンドポイントを追加し、Task（title・description）と TaskComment（content）を 2 クエリで検索して task_id 単位に重複排除する。フロントエンドは `CommandPalette.tsx` コンポーネントと `useSearchStore.ts` を新規作成し、`App.tsx` ヘッダーに組み込む。

**Tech Stack:** React 18 + TypeScript + Ant Design 5.x + TanStack Query 5.x / FastAPI + SQLAlchemy 2.x + Pydantic v2

---

## ファイル構成

| 操作 | ファイル | 内容 |
|------|---------|------|
| 修正 | `src/models/task_web.py` | `SearchResultItem` / `SearchResponse` 追加 |
| 作成 | `src/api/routers/search.py` | 検索エンドポイント |
| 修正 | `src/api/main.py` | search ルーター登録 |
| 作成 | `tests/unit/test_search_router.py` | 5 テスト |
| 修正 | `frontend/src/lib/api.ts` | 型・`searchAll` 関数追加 |
| 作成 | `frontend/src/hooks/useSearch.ts` | TanStack Query フック |
| 作成 | `frontend/src/store/useSearchStore.ts` | Zustand 開閉状態ストア |
| 作成 | `frontend/src/components/CommandPalette.tsx` | モーダル UI |
| 修正 | `frontend/src/App.tsx` | 検索アイコン + CommandPalette 追加 |

---

### Task 1: Pydantic モデル + search ルーター + テスト 5 件

**Files:**
- Modify: `src/models/task_web.py`
- Create: `src/api/routers/search.py`
- Modify: `src/api/main.py`
- Create: `tests/unit/test_search_router.py`

- [ ] **Step 1: テストを先に書く（TDD）**

`tests/unit/test_search_router.py` を新規作成:

```python
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="User", email="u@u.com", roles=["member"], tid="t")


def _make_task(title: str = "テスト面接") -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.project_id = uuid.uuid4()
    t.title = title
    t.description = "説明文テキスト"
    t.visibility = "team"
    t.assignee_id = "other-user"
    return t


def _make_comment(task_id: uuid.UUID | None = None) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.task_id = task_id or uuid.uuid4()
    c.content = "コメントのテキスト"
    return c


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


def _make_client(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    from src.api.routers.search import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_search_task_title(mock_db: AsyncMock) -> None:
    task = _make_task()
    project_name = "採用プロジェクト"

    task_result = MagicMock()
    task_result.all.return_value = [(task, project_name)]
    comment_result = MagicMock()
    comment_result.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["title"] == "テスト面接"
    assert data["items"][0]["match_type"] in ("title", "description")


def test_search_comment(mock_db: AsyncMock) -> None:
    task = _make_task("別のタスク")
    comment = _make_comment(task.id)
    comment.content = "コメント内に面接という文言"
    project_name = "採用プロジェクト"

    task_result = MagicMock()
    task_result.all.return_value = []
    comment_result = MagicMock()
    comment_result.all.return_value = [(comment, task, project_name)]
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["match_type"] == "comment"


def test_search_deduplication(mock_db: AsyncMock) -> None:
    task = _make_task("面接の準備")
    comment = _make_comment(task.id)
    comment.content = "面接のフィードバック"
    project_name = "採用プロジェクト"

    task_result = MagicMock()
    task_result.all.return_value = [(task, project_name)]
    comment_result = MagicMock()
    comment_result.all.return_value = [(comment, task, project_name)]
    mock_db.execute = AsyncMock(side_effect=[task_result, comment_result])

    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=面接")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["match_type"] == "title"


def test_search_short_query(mock_db: AsyncMock) -> None:
    client = _make_client(_user, mock_db)
    resp = client.get("/api/v1/search?q=a")
    assert resp.status_code == 422


def test_search_unauthenticated() -> None:
    from src.api.routers.search import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/search?q=テスト")
    assert resp.status_code == 401
```

- [ ] **Step 2: テストが FAIL することを確認**

```
python -m pytest tests/unit/test_search_router.py -v
```

Expected: `ImportError` または全テスト FAILED（`search` モジュール未存在）

- [ ] **Step 3: Pydantic モデルを `src/models/task_web.py` に追加**

`# --- Weekly Summary ---` コメントの直前（MilestoneResponse の後）に追加:

```python
# --- Search ---


class SearchResultItem(BaseModel):
    task_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    title: str
    snippet: str
    match_type: Literal["title", "description", "comment"]

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
```

IMPORTANT: `Literal` は `task_web.py` の先頭 import 確認。現在 `from typing import Literal` が存在するか確認し、なければ追加する。

- [ ] **Step 4: `src/api/routers/search.py` を新規作成**

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Project, Task, TaskComment
from src.models.task_web import SearchResponse, SearchResultItem

router = APIRouter(prefix="/api/v1/search", tags=["search"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


def _make_snippet(text: str, keyword: str, context: int = 50) -> str:
    lower = text.lower()
    idx = lower.find(keyword.lower())
    if idx == -1:
        return text[: context * 2]
    start = max(0, idx - context)
    end = min(len(text), idx + len(keyword) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


@router.get("", response_model=SearchResponse)
async def search(
    q: str,
    db: DbDep,
    current_user: CurrentUser,
    limit: int = Query(default=20, le=50),
) -> SearchResponse:
    if len(q) < 2:
        raise HTTPException(status_code=422, detail="検索キーワードは2文字以上で入力してください")

    like = f"%{q}%"
    visibility_cond = or_(
        Task.visibility != "private",
        Task.assignee_id == current_user.sub,
        Task.created_by == current_user.sub,
    )

    # タスク検索（title + description）
    task_q = (
        select(Task, Project.name)
        .join(Project, Task.project_id == Project.id)
        .where(
            Task.title.ilike(like) | Task.description.ilike(like),
            visibility_cond,
        )
        .limit(limit * 2)
    )
    task_rows = (await db.execute(task_q)).all()

    # コメント検索
    comment_q = (
        select(TaskComment, Task, Project.name)
        .join(Task, TaskComment.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .where(
            TaskComment.content.ilike(like),
            visibility_cond,
        )
        .limit(limit * 2)
    )
    comment_rows = (await db.execute(comment_q)).all()

    # task_id 単位で重複排除（title > description > comment）
    seen: dict[uuid.UUID, SearchResultItem] = {}

    for task, project_name in task_rows:
        if task.id in seen:
            continue
        match_type = "title" if q.lower() in (task.title or "").lower() else "description"
        text = task.title if match_type == "title" else (task.description or task.title)
        seen[task.id] = SearchResultItem(
            task_id=task.id,
            project_id=task.project_id,
            project_name=project_name,
            title=task.title,
            snippet=_make_snippet(text, q),
            match_type=match_type,
        )

    for comment, task, project_name in comment_rows:
        if task.id in seen:
            continue
        seen[task.id] = SearchResultItem(
            task_id=task.id,
            project_id=task.project_id,
            project_name=project_name,
            title=task.title,
            snippet=_make_snippet(comment.content, q),
            match_type="comment",
        )

    items = list(seen.values())[:limit]
    return SearchResponse(items=items, total=len(seen))
```

- [ ] **Step 5: `src/api/main.py` にルーターを登録**

`from src.api.routers import (` ブロックに `search,` を追加（アルファベット順）:

```python
from src.api.routers import (
    admin,
    dashboard,
    dev,
    health,
    import_router,
    milestones,
    projects,
    search,
    sections,
    task_details,
    tasks,
    tasks_crud,
    templates,
    users,
)
```

`app.include_router(milestones.router)` の後に追加:

```python
app.include_router(search.router)
```

- [ ] **Step 6: テスト 5 件 PASS を確認**

```
python -m pytest tests/unit/test_search_router.py -v
```

Expected:
```
test_search_task_title PASSED
test_search_comment PASSED
test_search_deduplication PASSED
test_search_short_query PASSED
test_search_unauthenticated PASSED
5 passed
```

- [ ] **Step 7: フルテストスイート確認**

```
python -m pytest tests/ -q --tb=short
```

Expected: `250 passed`（245 + 5）

- [ ] **Step 8: コミット**

```
git add src/models/task_web.py src/api/routers/search.py src/api/main.py tests/unit/test_search_router.py
git commit -m "feat: 横断全文検索 GET /api/v1/search エンドポイント追加・テスト 5 件"
```

---

### Task 2: フロントエンド API 型・useSearch フック・useSearchStore

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useSearch.ts`
- Create: `frontend/src/store/useSearchStore.ts`

- [ ] **Step 1: `frontend/src/lib/api.ts` の末尾に追加**

ファイルの最後（`deleteMilestone` 関数の後）に追加:

```typescript
// --- Search ---

export interface SearchResultItem {
  task_id: string
  project_id: string
  project_name: string
  title: string
  snippet: string
  match_type: 'title' | 'description' | 'comment'
}

export interface SearchResponse {
  items: SearchResultItem[]
  total: number
}

export async function searchAll(q: string, limit = 20): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>('/search', { params: { q, limit } })
  return data
}
```

- [ ] **Step 2: `frontend/src/hooks/useSearch.ts` を新規作成**

```typescript
import { useDeferredValue } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type SearchResponse, searchAll } from '../lib/api'

export function useSearch(input: string) {
  const q = useDeferredValue(input)
  return useQuery<SearchResponse>({
    queryKey: ['search', q],
    queryFn: () => searchAll(q),
    enabled: q.length >= 2,
    staleTime: 0,
  })
}
```

- [ ] **Step 3: `frontend/src/store/useSearchStore.ts` を新規作成**

```typescript
import { create } from 'zustand'

interface SearchStore {
  open: boolean
  setOpen: (open: boolean) => void
}

export const useSearchStore = create<SearchStore>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
}))
```

- [ ] **Step 4: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 5: コミット**

```
git add frontend/src/lib/api.ts frontend/src/hooks/useSearch.ts frontend/src/store/useSearchStore.ts
git commit -m "feat: SearchResultItem 型・searchAll 関数・useSearch フック・useSearchStore 追加"
```

---

### Task 3: CommandPalette コンポーネント + App.tsx 統合

**Files:**
- Create: `frontend/src/components/CommandPalette.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: `frontend/src/components/CommandPalette.tsx` を新規作成**

```tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, List, Modal, Spin, Tag, Typography } from 'antd'
import { CommentOutlined, FileTextOutlined } from '@ant-design/icons'
import { useSearch } from '../hooks/useSearch'
import { useSearchStore } from '../store/useSearchStore'
import type { SearchResultItem } from '../lib/api'

const MATCH_TYPE_LABEL: Record<SearchResultItem['match_type'], string> = {
  title: 'タイトル',
  description: '説明',
  comment: 'コメント',
}

const MATCH_TYPE_COLOR: Record<SearchResultItem['match_type'], string> = {
  title: 'blue',
  description: 'cyan',
  comment: 'green',
}

export default function CommandPalette() {
  const { open, setOpen } = useSearchStore()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const { data, isFetching } = useSearch(input)

  // Ctrl+K / Cmd+K でトグル
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(true)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [setOpen])

  const handleClose = () => {
    setOpen(false)
    setInput('')
  }

  const handleSelect = (item: SearchResultItem) => {
    navigate(`/projects/${item.project_id}`)
    handleClose()
  }

  return (
    <Modal
      open={open}
      onCancel={handleClose}
      footer={null}
      width={600}
      style={{ top: 100 }}
      styles={{ body: { padding: 0 } }}
      title={null}
      closable={false}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Input
          autoFocus
          size="large"
          placeholder="タスク・コメントを検索… (Esc で閉じる)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          suffix={isFetching ? <Spin size="small" /> : null}
          bordered={false}
          style={{ fontSize: 16 }}
        />
      </div>

      {input.length >= 2 && (
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          {data && data.items.length > 0 ? (
            <List
              dataSource={data.items}
              renderItem={(item) => (
                <List.Item
                  onClick={() => handleSelect(item)}
                  style={{ padding: '10px 16px', cursor: 'pointer' }}
                  className="search-result-item"
                >
                  <List.Item.Meta
                    avatar={
                      item.match_type === 'comment' ? (
                        <CommentOutlined style={{ color: '#52c41a', fontSize: 16, marginTop: 4 }} />
                      ) : (
                        <FileTextOutlined style={{ color: '#1677ff', fontSize: 16, marginTop: 4 }} />
                      )
                    }
                    title={
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Typography.Text strong>{item.title}</Typography.Text>
                        <Tag color={MATCH_TYPE_COLOR[item.match_type]} style={{ margin: 0 }}>
                          {MATCH_TYPE_LABEL[item.match_type]}
                        </Tag>
                      </div>
                    }
                    description={
                      <div>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {item.project_name}
                        </Typography.Text>
                        <br />
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {item.snippet}
                        </Typography.Text>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          ) : !isFetching ? (
            <div style={{ padding: '24px 16px', textAlign: 'center' }}>
              <Typography.Text type="secondary">一致するタスクが見つかりません</Typography.Text>
            </div>
          ) : null}
        </div>
      )}
    </Modal>
  )
}
```

- [ ] **Step 2: `frontend/src/App.tsx` を変更**

import セクションに追加（既存の `import WorkloadAlertBadge` の次の行）:

```tsx
import { SearchOutlined } from '@ant-design/icons'
import CommandPalette from './components/CommandPalette'
import { useSearchStore } from './store/useSearchStore'
```

`return (` の直前（コンポーネント本体内）に追加:

```tsx
const { setOpen: openSearch } = useSearchStore()
```

ヘッダーの `<WorkloadAlertBadge />` の直前に追加:

```tsx
<Button
  icon={<SearchOutlined />}
  type="text"
  style={{ color: 'white' }}
  title="検索 (Ctrl+K)"
  onClick={() => openSearch(true)}
/>
```

`</Layout>` の直前（return の末尾付近）に追加:

```tsx
<CommandPalette />
```

具体的な変更後のヘッダー部分:

```tsx
<div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
  {DEV_BYPASS && (
    <>
      <span style={{ color: 'rgba(255,255,255,0.65)', fontSize: 13 }}>
        [DEV] {displayName}
      </span>
      <Button
        size="small"
        onClick={handleDevLogout}
        style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)' }}
      >
        ログアウト
      </Button>
    </>
  )}
  <Button
    icon={<SearchOutlined />}
    type="text"
    style={{ color: 'white' }}
    title="検索 (Ctrl+K)"
    onClick={() => openSearch(true)}
  />
  <WorkloadAlertBadge />
</div>
```

- [ ] **Step 3: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors。エラーが出た場合は修正する。

- [ ] **Step 4: バックエンドテスト確認**

```
python -m pytest tests/ -q --tb=short
```

Expected: `250 passed`

- [ ] **Step 5: コミット**

```
git add frontend/src/components/CommandPalette.tsx frontend/src/App.tsx
git commit -m "feat: CommandPalette コンポーネント追加・App.tsx ヘッダーに検索アイコン統合"
```
