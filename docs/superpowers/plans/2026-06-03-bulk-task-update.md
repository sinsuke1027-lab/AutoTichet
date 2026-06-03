# タスク一括操作 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク一覧でチェックボックス複数選択 → ステータス/担当者を一括変更する機能を追加する。

**Architecture:** バックエンドに `PATCH /api/v1/tasks/bulk` を1本追加（1トランザクション・権限チェック付き）し、フロントエンドはテーブルに `rowSelection` と画面下部固定の一括操作バーを追加する。既存の D&D 並び替えとは独立して動作する。

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Pydantic v2 / React 18 + TypeScript + Ant Design 5.x + TanStack Query 5.x

**Design doc:** `docs/superpowers/specs/2026-06-03-bulk-task-update-design.md`

---

## ファイル構成

```
# 変更するファイル
src/models/task_web.py                     ← TaskBulkUpdate / BulkUpdateResponse モデル追加
src/api/routers/tasks_crud.py              ← PATCH /tasks/bulk エンドポイント追加
frontend/src/lib/api.ts                    ← TaskBulkUpdate 型・bulkUpdateTasks 関数追加
frontend/src/hooks/useTasks.ts             ← useBulkUpdateTasks フック追加
frontend/src/pages/Tasks/index.tsx         ← rowSelection・一括操作バー追加

# 新規作成するファイル
tests/unit/test_bulk_update.py
```

---

### Task 1: Pydantic モデル追加

**Files:**
- Modify: `src/models/task_web.py`（`# --- Weekly Summary ---` の前、`UserProfileUpdate` クラスの直後）

- [ ] **Step 1: モデルを追加する**

`src/models/task_web.py` の `UserProfileUpdate` クラス（約 319 行目）の直後に追記:

```python
class TaskBulkUpdate(BaseModel):
    task_ids: list[uuid.UUID]
    status: TaskStatus | None = None
    assignee_id: str | None = None


class BulkUpdateResponse(BaseModel):
    updated_count: int
```

`uuid` はファイル先頭に既に `import uuid` があることを確認する（既存）。`TaskStatus` も既存 import 済み。

- [ ] **Step 2: 構文チェック**

Run:
```
python -c "from src.models.task_web import TaskBulkUpdate, BulkUpdateResponse; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: コミット**

```bash
git add src/models/task_web.py
git commit -m "feat: TaskBulkUpdate / BulkUpdateResponse Pydantic モデル追加"
```

---

### Task 2: バックエンド API + テスト

**Files:**
- Modify: `src/api/routers/tasks_crud.py`（`@router.get("/{task_id}"` の直前・約 767 行目に挿入）
- Create: `tests/unit/test_bulk_update.py`

#### 2-A: テストを先に書く（TDD）

- [ ] **Step 1: テストファイルを作成する**

`tests/unit/test_bulk_update.py`:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_manager = TokenPayload(
    sub="mgr-1", name="Manager", email="m@m.com", roles=["manager"], tid="t"
)
_member = TokenPayload(
    sub="mem-1", name="Member", email="mem@m.com", roles=["member"], tid="t"
)


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


def _make_client(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_task(task_id: str, assignee_id: str = "mgr-1") -> MagicMock:
    t = MagicMock()
    t.id = uuid.UUID(task_id)
    t.assignee_id = assignee_id
    t.recurrence_rule = None
    t.status = "not_started"
    return t


def test_bulk_status_update(mock_db: AsyncMock) -> None:
    tid1 = str(uuid.uuid4())
    tid2 = str(uuid.uuid4())
    tasks = [_make_task(tid1), _make_task(tid2)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()

    client = _make_client(_manager, mock_db)
    resp = client.patch(
        "/api/v1/tasks/bulk",
        json={"task_ids": [tid1, tid2], "status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 2


def test_bulk_assignee_update(mock_db: AsyncMock) -> None:
    tid1 = str(uuid.uuid4())
    tasks = [_make_task(tid1)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()

    client = _make_client(_manager, mock_db)
    resp = client.patch(
        "/api/v1/tasks/bulk",
        json={"task_ids": [tid1], "assignee_id": "new-user"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1


def test_bulk_forbidden_task(mock_db: AsyncMock) -> None:
    """member ロールが他人のタスクを一括更新しようとすると 403"""
    tid1 = str(uuid.uuid4())
    tasks = [_make_task(tid1, assignee_id="other-user")]  # 別ユーザーのタスク
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    mock_db.execute = AsyncMock(return_value=result)

    client = _make_client(_member, mock_db)
    resp = client.patch(
        "/api/v1/tasks/bulk",
        json={"task_ids": [tid1], "status": "completed"},
    )
    assert resp.status_code == 403


def test_bulk_unauthenticated() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.patch(
        "/api/v1/tasks/bulk",
        json={"task_ids": [str(uuid.uuid4())], "status": "completed"},
    )
    assert resp.status_code in (401, 422)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run:
```
python -m pytest tests/unit/test_bulk_update.py -v
```
Expected: FAIL（エンドポイント未実装のため 404/405）

#### 2-B: エンドポイントを実装する

- [ ] **Step 3: `src/api/routers/tasks_crud.py` に import を追加する**

ファイル先頭の `from src.models.task_web import (` ブロックに `BulkUpdateResponse` と `TaskBulkUpdate` を追加する。既存のアルファベット順に合わせて挿入:

```python
from src.models.task_web import (
    BulkUpdateResponse,          # ← 追加
    ClarifyIssue,
    ClarifyRequirementsResponse,
    GenerateHandoverResponse,
    GenerateSubtasksResponse,
    HandoverRequest,
    HourEstimate,
    RescheduleRequest,
    RescheduleResponse,
    SimilarTaskResponse,
    TaskBulkUpdate,              # ← 追加
    TaskCreate,
    TaskListResponse,
    TaskReorderRequest,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
```

- [ ] **Step 4: エンドポイントを `@router.get("/{task_id}"` の直前（約 767 行目）に挿入する**

```python
@router.patch("/bulk", response_model=BulkUpdateResponse)
async def bulk_update_tasks(
    body: TaskBulkUpdate, db: DbDep, current_user: CurrentUser
) -> BulkUpdateResponse:
    if not body.task_ids:
        raise HTTPException(status_code=422, detail="task_ids は1件以上必要です")
    if len(body.task_ids) > 100:
        raise HTTPException(status_code=422, detail="task_ids は100件以内にしてください")
    if body.status is None and body.assignee_id is None:
        raise HTTPException(status_code=422, detail="status または assignee_id のいずれかを指定してください")

    result = await db.execute(
        select(Task).where(Task.id.in_(body.task_ids))
    )
    tasks = result.scalars().all()

    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    for task in tasks:
        if task.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
            raise HTTPException(status_code=403, detail="操作権限のないタスクが含まれています")

    for task in tasks:
        if body.status is not None:
            task.status = body.status
        if body.assignee_id is not None:
            task.assignee_id = body.assignee_id
        if body.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            await _spawn_next_recurrence(task, db)

    await db.commit()
    return BulkUpdateResponse(updated_count=len(tasks))
```

- [ ] **Step 5: テストが通ることを確認する**

Run:
```
python -m pytest tests/unit/test_bulk_update.py -v
```
Expected: 4 passed

- [ ] **Step 6: 全テストが通ることを確認する**

Run:
```
python -m pytest tests/ -q
```
Expected: 240 passed 以上, 0 failed

- [ ] **Step 7: コミット**

```bash
git add src/api/routers/tasks_crud.py tests/unit/test_bulk_update.py
git commit -m "feat: PATCH /tasks/bulk 一括更新エンドポイント追加"
```

---

### Task 3: フロントエンド型定義・フック追加

**Files:**
- Modify: `frontend/src/lib/api.ts`（末尾に追記）
- Modify: `frontend/src/hooks/useTasks.ts`（末尾に追記）

- [ ] **Step 1: `frontend/src/lib/api.ts` の末尾に追記する**

```typescript
export interface TaskBulkUpdate {
  task_ids: string[]
  status?: string | null
  assignee_id?: string | null
}

export async function bulkUpdateTasks(body: TaskBulkUpdate): Promise<{ updated_count: number }> {
  const { data } = await api.patch<{ updated_count: number }>('/tasks/bulk', body)
  return data
}
```

- [ ] **Step 2: `frontend/src/hooks/useTasks.ts` の import 行を更新する**

ファイル先頭の import に `TaskBulkUpdate` と `bulkUpdateTasks` を追加:

```typescript
import api, {
  type Task,
  type TaskListResponse,
  type HourEstimate,
  type ExtractResult,
  type TaskBulkUpdate,
  getEstimateHours,
  extractTasksFromText,
  deleteRecurrence,
  bulkUpdateTasks,
} from '../lib/api'
```

- [ ] **Step 3: `frontend/src/hooks/useTasks.ts` の末尾に `useBulkUpdateTasks` を追加する**

```typescript
export function useBulkUpdateTasks() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: TaskBulkUpdate) => bulkUpdateTasks(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
```

- [ ] **Step 4: TypeScript 型チェック**

Run:
```
cd frontend && npx tsc --noEmit
```
Expected: エラーなし

- [ ] **Step 5: コミット**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useTasks.ts
git commit -m "feat: bulkUpdateTasks API 関数・useBulkUpdateTasks フック追加"
```

---

### Task 4: タスク一覧 UI に rowSelection と一括操作バー追加

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

**事前確認:** このファイルは約 630 行。`useBulkUpdateTasks` を import し、`selectedRowKeys` 状態と `handleBulkApply` 関数を追加し、`<Table>` に `rowSelection` を追加し、一括操作バー JSX を追加する。

- [ ] **Step 1: import を更新する**

`frontend/src/pages/Tasks/index.tsx` の useTasks import 行に `useBulkUpdateTasks` を追加:

```typescript
import { useTasks, useCreateTask, useEstimateHours, useRecordEstimatedHours, useReorderTask, useBulkUpdateTasks } from '../../hooks/useTasks'
```

- [ ] **Step 2: 状態変数を追加する**

既存の `const [localItems, setLocalItems] = useState<Task[]>([])` の直後に追加:

```typescript
const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
const [bulkStatus, setBulkStatus] = useState<string | undefined>()
const [bulkAssignee, setBulkAssignee] = useState<string | undefined>()
const bulkUpdate = useBulkUpdateTasks()
```

- [ ] **Step 3: `handleBulkApply` 関数を追加する**

既存の `handleSearch` 関数（`const handleSearch = () => setSearchQ(keyword)`）の直後に追加:

```typescript
const handleBulkApply = async () => {
  try {
    const res = await bulkUpdate.mutateAsync({
      task_ids: selectedRowKeys,
      ...(bulkStatus ? { status: bulkStatus } : {}),
      ...(bulkAssignee ? { assignee_id: bulkAssignee } : {}),
    })
    void message.success(`${res.updated_count}件を更新しました`)
    setSelectedRowKeys([])
    setBulkStatus(undefined)
    setBulkAssignee(undefined)
  } catch {
    void message.error('一括更新に失敗しました')
  }
}
```

- [ ] **Step 4: `<Table>` に `rowSelection` を追加する**

既存の `<Table` タグに `rowSelection` prop を追加する（`rowKey="id"` の隣に追記）:

```tsx
<Table
  rowKey="id"
  rowSelection={{
    selectedRowKeys,
    onChange: (keys) => setSelectedRowKeys(keys as string[]),
  }}
  loading={isLoading}
  dataSource={localItems}
  columns={columns}
  pagination={{ pageSize: 20, total: taskList?.total, showSizeChanger: false }}
  components={{ body: { row: DraggableRow } }}
/>
```

- [ ] **Step 5: 一括操作バーを追加する**

`</Space>` の最終閉じタグ（`return` ブロックの末尾）の直前に追加:

```tsx
{selectedRowKeys.length > 0 && (
  <div
    style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      background: '#fff',
      borderTop: '1px solid #f0f0f0',
      padding: '12px 24px',
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      boxShadow: '0 -2px 8px rgba(0,0,0,0.08)',
    }}
  >
    <Typography.Text strong>{selectedRowKeys.length}件選択中</Typography.Text>
    <Select
      placeholder="ステータスを変更"
      allowClear
      style={{ width: 160 }}
      options={STATUS_OPTIONS.filter((o) => o.value !== '')}
      value={bulkStatus}
      onChange={setBulkStatus}
    />
    <Select
      placeholder="担当者を変更"
      allowClear
      style={{ width: 160 }}
      options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
      value={bulkAssignee}
      onChange={setBulkAssignee}
    />
    <Button
      type="primary"
      loading={bulkUpdate.isPending}
      disabled={!bulkStatus && !bulkAssignee}
      onClick={() => void handleBulkApply()}
    >
      適用
    </Button>
    <Button
      onClick={() => {
        setSelectedRowKeys([])
        setBulkStatus(undefined)
        setBulkAssignee(undefined)
      }}
    >
      選択解除
    </Button>
  </div>
)}
```

- [ ] **Step 6: TypeScript 型チェック**

Run:
```
cd frontend && npx tsc --noEmit
```
Expected: エラーなし

- [ ] **Step 7: 全バックエンドテストが通ることを確認する**

Run:
```
python -m pytest tests/ -q
```
Expected: 240 passed 以上, 0 failed

- [ ] **Step 8: コミット**

```bash
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: タスク一覧に rowSelection と一括操作バー追加"
```

---

## 完了チェック

全タスク完了後に以下を確認する:

```bash
# バックエンドテスト全件通過
python -m pytest tests/ -q

# TypeScript エラーなし
cd frontend && npx tsc --noEmit

# 動作確認（ブラウザで http://localhost:5175/tasks を開く）
# - タスク行の左端にチェックボックスが表示される
# - チェックを入れると画面下部に「N件選択中」バーが出現する
# - ステータス Select で選択 → 「適用」で一括変更される
# - 担当者 Select で選択 → 「適用」で一括変更される
# - D&D 並び替えが引き続き動作する
# - 「選択解除」でバーが非表示になる
```
