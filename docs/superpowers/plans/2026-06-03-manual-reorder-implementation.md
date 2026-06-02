# タスク手動並び替え Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク一覧（/tasks）とボード（/board）でドラッグ＆ドロップによるセクション内並び替えを実装し、`order_index` に永続化する。

**Architecture:** フラクショナルインデックス方式で `PATCH /api/v1/tasks/{task_id}/order` エンドポイントを追加。フロントエンドは `@dnd-kit/sortable`（既導入済み）を両ページに適用し、楽観的更新でUIを即座に反映する。

**Tech Stack:** Python/FastAPI/SQLAlchemy（PostgreSQL）、React/TypeScript、@dnd-kit/core + @dnd-kit/sortable、Ant Design Table

---

## ファイル構成

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/db/models.py` | 修正 | `Task.order_index`: `Integer` → `Float` |
| `src/models/task_web.py` | 修正 | `TaskResponse.order_index: float`; `TaskReorderRequest` 追加 |
| `alembic/versions/0006_task_order_index_float.py` | 新規 | カラム型変更 + 初期採番マイグレーション |
| `src/api/routers/tasks_crud.py` | 修正 | `PATCH /{task_id}/order` 追加; `list_tasks` ORDER BY 変更; `create_task` 末尾追加対応 |
| `tests/unit/test_task_reorder.py` | 新規 | 5件のテスト |
| `frontend/src/lib/api.ts` | 修正 | `Task.order_index` フィールド追加 |
| `frontend/src/hooks/useTasks.ts` | 修正 | `useReorderTask` フック追加 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | `DndContext` + `SortableContext` + `DraggableRow` 追加 |
| `frontend/src/pages/Board/index.tsx` | 修正 | カラム内 `SortableContext`; `TaskCard` を `useSortable` に変更 |

---

## Task 1: DB マイグレーション + Python モデル変更

**Files:**
- Modify: `src/db/models.py:74`
- Modify: `src/models/task_web.py:109`
- Create: `alembic/versions/0006_task_order_index_float.py`

- [ ] **Step 1: `src/db/models.py` の `order_index` を Float に変更**

`src/db/models.py` の74行目を変更する。変更前後:

```python
# 変更前
order_index: Mapped[int] = mapped_column(Integer(), default=0)

# 変更後
order_index: Mapped[float] = mapped_column(Float, default=0.0)
```

`Float` は既に `from sqlalchemy import ... Float` でインポート済みか確認。インポート行を確認:

```python
# models.py の先頭付近を確認
grep -n "from sqlalchemy import" src/db/models.py
```

`Float` がなければ追加する。

- [ ] **Step 2: `src/models/task_web.py` の `TaskResponse` を修正し `TaskReorderRequest` を追加**

`src/models/task_web.py` の109行目を変更:

```python
# 変更前
order_index: int = 0

# 変更後
order_index: float = 0.0
```

同ファイルの末尾（`SectionReorderItem` の後）に追加:

```python
class TaskReorderRequest(BaseModel):
    before_id: uuid.UUID | None = None
    after_id: uuid.UUID | None = None
```

- [ ] **Step 3: Alembic マイグレーションファイルを作成**

`alembic/versions/0006_task_order_index_float.py` を新規作成:

```python
"""task order_index を Integer から Float に変更し初期採番

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tasks",
        "order_index",
        type_=sa.Float(),
        nullable=False,
        server_default="0.0",
        existing_nullable=False,
    )
    # セクション（またはプロジェクト）ごとに created_at 昇順で 1000.0 刻みに採番
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY COALESCE(section_id::text, project_id::text, 'no_group')
                       ORDER BY created_at
                   ) AS rn
            FROM tasks
        )
        UPDATE tasks
        SET order_index = ranked.rn * 1000.0
        FROM ranked
        WHERE tasks.id = ranked.id
    """)


def downgrade() -> None:
    op.alter_column(
        "tasks",
        "order_index",
        type_=sa.Integer(),
        nullable=False,
        server_default="0",
        existing_nullable=False,
    )
```

- [ ] **Step 4: マイグレーション構文チェック（Python import のみ）**

```bash
python -c "import alembic.versions.0006_task_order_index_float"
```

構文エラーがなければ OK。（実際の DB 適用は開発環境での手動実行）

- [ ] **Step 5: コミット**

```bash
git add src/db/models.py src/models/task_web.py alembic/versions/0006_task_order_index_float.py
git commit -m "feat: Task.order_index を Float に変更・マイグレーション追加"
```

---

## Task 2: バックエンド `PATCH /{task_id}/order` エンドポイント + テスト

**Files:**
- Create: `tests/unit/test_task_reorder.py`
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: テストファイルを作成（失敗テスト）**

`tests/unit/test_task_reorder.py` を新規作成:

```python
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.db.models import Task

_admin = TokenPayload(
    sub="admin-1", name="Admin", email="a@t.com", roles=["admin"], tid="tid"
)


def _make_task(*, order_index: float = 1000.0, section_id: uuid.UUID | None = None) -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "テストタスク"
    t.status = "not_started"
    t.priority = "medium"
    t.assignee_id = "user-1"
    t.start_date = date(2026, 6, 1)
    t.due_date = date(2026, 6, 30)
    t.completed_at = None
    t.project_id = None
    t.section_id = section_id
    t.description = None
    t.confidence_score = None
    t.source_type = None
    t.created_at = datetime(2026, 6, 1, 0, 0, 0)
    t.updated_at = datetime(2026, 6, 1, 0, 0, 0)
    t.tags = []
    t.sub_assignees = []
    t.work_hours = []
    t.subtasks = []
    t.project = None
    t.section = None
    t.visibility = "all"
    t.order_index = order_index
    return t


def _make_db_for_reorder(
    target: MagicMock,
    before: MagicMock | None = None,
    after: MagicMock | None = None,
    section_tasks: list | None = None,
) -> AsyncMock:
    """reorder エンドポイント用の DB モック。

    execute() の呼び出し順:
      1. target タスク取得
      2. before タスク取得（指定時）
      3. after タスク取得（指定時）
      4. 再採番が必要な場合: セクション全タスク取得
    """
    mock_db = AsyncMock()
    call_count = 0
    targets = [target, before, after]

    def _scalar_result(val: MagicMock | None) -> MagicMock:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        return r

    def _scalars_result(tasks: list) -> MagicMock:
        r = MagicMock()
        r.scalars.return_value.all.return_value = tasks
        return r

    async def _execute(query: object) -> MagicMock:
        nonlocal call_count
        idx = call_count
        call_count += 1
        # 最初の3回はスカラー（task 取得）
        if idx < 3:
            val = targets[idx]
            return _scalar_result(val)
        # それ以降は再採番用の全件取得
        return _scalars_result(section_tasks or [])

    mock_db.execute = _execute
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    return mock_db


def _make_client(db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_reorder_to_middle_returns_204() -> None:
    """前後タスクの中間値で order_index が更新される → 204"""
    before = _make_task(order_index=1000.0)
    target = _make_task(order_index=3000.0)
    after = _make_task(order_index=2000.0)
    db = _make_db_for_reorder(target, before, after)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": str(before.id), "after_id": str(after.id)},
    )
    assert resp.status_code == 204
    assert target.order_index == 1500.0


def test_reorder_to_top_returns_204() -> None:
    """before_id=null → after.order_index - 1000.0"""
    target = _make_task(order_index=3000.0)
    after = _make_task(order_index=1000.0)
    db = _make_db_for_reorder(target, None, after)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": None, "after_id": str(after.id)},
    )
    assert resp.status_code == 204
    assert target.order_index == 0.0


def test_reorder_to_bottom_returns_204() -> None:
    """after_id=null → before.order_index + 1000.0"""
    target = _make_task(order_index=1000.0)
    before = _make_task(order_index=3000.0)
    db = _make_db_for_reorder(target, before, None)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": str(before.id), "after_id": None},
    )
    assert resp.status_code == 204
    assert target.order_index == 4000.0


def test_reorder_triggers_renormalization() -> None:
    """差が 0.001 未満のとき再採番が実行される"""
    before = _make_task(order_index=1000.0)
    target = _make_task(order_index=3000.0)
    after = _make_task(order_index=1000.0005)  # gap = 0.0005 < 0.001
    # 再採番後: before=1000, target=2000, after=3000 になるはず
    section_tasks = [before, after, target]
    db = _make_db_for_reorder(target, before, after, section_tasks=section_tasks)
    client = _make_client(db)
    resp = client.patch(
        f"/api/v1/tasks/{target.id}/order",
        json={"before_id": str(before.id), "after_id": str(after.id)},
    )
    assert resp.status_code == 204


def test_reorder_task_not_found_returns_404() -> None:
    """存在しない task_id → 404"""
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    client = _make_client(mock_db)
    resp = client.patch(
        f"/api/v1/tasks/{uuid.uuid4()}/order",
        json={"before_id": None, "after_id": None},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: テストが FAIL することを確認**

```bash
pytest tests/unit/test_task_reorder.py -v
```

Expected: 全5件 FAIL（エンドポイントが存在しないため）

- [ ] **Step 3: `src/models/task_web.py` に `TaskReorderRequest` が追加済みか確認**

Task 1 で追加済みのはず。なければ以下を `SectionReorderItem` の後に追加:

```python
class TaskReorderRequest(BaseModel):
    before_id: uuid.UUID | None = None
    after_id: uuid.UUID | None = None
```

- [ ] **Step 4: `src/api/routers/tasks_crud.py` のインポートに `TaskReorderRequest` を追加**

`src/api/routers/tasks_crud.py` の `from src.models.task_web import (` ブロックに追記:

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
    TaskReorderRequest,   # ← 追加
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
```

- [ ] **Step 5: `PATCH /{task_id}/order` エンドポイントを追加**

`src/api/routers/tasks_crud.py` の `@router.get("/export/csv")` の直前（`_CSV_HEADERS` 定数定義の後かつ `export_tasks_csv` の前の位置）に追加:

```python
async def _renormalize_section(
    db: AsyncSession, section_id: uuid.UUID | None, project_id: uuid.UUID | None
) -> None:
    """セクション（またはプロジェクト）内の全タスクを 1000.0 刻みで再採番する。"""
    if section_id is not None:
        q = select(Task).where(Task.section_id == section_id).order_by(Task.order_index.asc())
    elif project_id is not None:
        q = (
            select(Task)
            .where(Task.section_id.is_(None), Task.project_id == project_id)
            .order_by(Task.order_index.asc())
        )
    else:
        q = (
            select(Task)
            .where(Task.section_id.is_(None), Task.project_id.is_(None))
            .order_by(Task.order_index.asc())
        )
    result = await db.execute(q)
    tasks = result.scalars().all()
    for i, t in enumerate(tasks):
        t.order_index = float((i + 1) * 1000)
    await db.flush()


@router.patch("/{task_id}/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_task(
    task_id: uuid.UUID,
    body: TaskReorderRequest,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    # 対象タスク取得
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    # before / after タスクの order_index を取得
    before_index: float | None = None
    after_index: float | None = None

    if body.before_id is not None:
        r = await db.execute(select(Task).where(Task.id == body.before_id))
        before_task = r.scalar_one_or_none()
        if before_task:
            before_index = float(before_task.order_index)

    if body.after_id is not None:
        r = await db.execute(select(Task).where(Task.id == body.after_id))
        after_task = r.scalar_one_or_none()
        if after_task:
            after_index = float(after_task.order_index)

    # 新 order_index を計算
    if before_index is not None and after_index is not None:
        new_index = (before_index + after_index) / 2.0
        # 差が小さすぎる場合は再採番してから再計算
        if abs(after_index - before_index) < 0.001:
            await _renormalize_section(db, task.section_id, task.project_id)
            # 再採番後は単純中間値（再採番で十分な間隔が確保される）
            r2 = await db.execute(select(Task).where(Task.id == body.before_id))
            b2 = r2.scalar_one_or_none()
            r3 = await db.execute(select(Task).where(Task.id == body.after_id))
            a2 = r3.scalar_one_or_none()
            new_index = ((b2.order_index if b2 else 0.0) + (a2.order_index if a2 else 0.0)) / 2.0
    elif before_index is not None:
        new_index = before_index + 1000.0
    elif after_index is not None:
        new_index = after_index - 1000.0
    else:
        new_index = 1000.0

    task.order_index = new_index
    await db.commit()
```

- [ ] **Step 6: `list_tasks` の ORDER BY を `order_index.asc()` に変更**

`src/api/routers/tasks_crud.py` の244行目付近を変更:

```python
# 変更前
result = await db.execute(
    query.order_by(Task.due_date.asc().nulls_last()).limit(limit).offset(offset)
)

# 変更後
result = await db.execute(
    query.order_by(Task.order_index.asc().nulls_last(), Task.due_date.asc().nulls_last())
    .limit(limit)
    .offset(offset)
)
```

- [ ] **Step 7: `create_task` で新タスクを末尾に追加する**

`src/api/routers/tasks_crud.py` の `create_task` 関数内、`task = Task(**data)` の前に追加:

```python
    # セクション内末尾に追加（order_index = 現在の最大値 + 1000.0）
    section_id_val = data.get("section_id")
    project_id_val = data.get("project_id")
    if section_id_val is not None:
        max_result = await db.execute(
            select(func.max(Task.order_index)).where(Task.section_id == section_id_val)
        )
    elif project_id_val is not None:
        max_result = await db.execute(
            select(func.max(Task.order_index)).where(
                Task.section_id.is_(None), Task.project_id == project_id_val
            )
        )
    else:
        max_result = await db.execute(
            select(func.max(Task.order_index)).where(
                Task.section_id.is_(None), Task.project_id.is_(None)
            )
        )
    max_order = max_result.scalar_one_or_none()
    data["order_index"] = (float(max_order) if max_order is not None else 0.0) + 1000.0
```

- [ ] **Step 8: テストを実行して全件パスを確認**

```bash
pytest tests/unit/test_task_reorder.py -v
```

Expected: 5件全て PASS

- [ ] **Step 9: 既存テスト全件パスを確認**

```bash
pytest tests/ -v --tb=short -q
```

Expected: 全件 PASS（`test_task_reorder.py` の5件含む）

- [ ] **Step 10: コミット**

```bash
git add src/api/routers/tasks_crud.py src/models/task_web.py tests/unit/test_task_reorder.py
git commit -m "feat: タスク手動並び替えエンドポイント PATCH /{task_id}/order を追加"
```

---

## Task 3: フロントエンド基盤 (`api.ts` + `useTasks.ts`)

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useTasks.ts`

- [ ] **Step 1: `frontend/src/lib/api.ts` の `Task` インターフェースに `order_index` を追加**

`frontend/src/lib/api.ts` の `Task` インターフェース（35行目付近）に追記:

```typescript
export interface Task {
  id: string
  title: string
  description: string | null
  status: string
  priority: string
  assignee_id: string | null
  due_date: string | null
  start_date?: string | null
  visibility: string
  tags: string[]
  project_id?: string | null
  section_id?: string | null
  parent_task_id?: string | null
  subtask_count?: number
  subtask_done_count?: number
  created_at: string
  updated_at: string
  risk_level?: 'high' | 'medium' | null
  order_index?: number   // ← 追加
}
```

- [ ] **Step 2: `frontend/src/hooks/useTasks.ts` に `useReorderTask` を追加**

`frontend/src/hooks/useTasks.ts` の既存フックの末尾に追加（`useDeleteTask` の後）:

```typescript
export function useReorderTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      taskId,
      beforeId,
      afterId,
    }: {
      taskId: string
      beforeId: string | null
      afterId: string | null
    }) => {
      await api.patch(`/tasks/${taskId}/order`, {
        before_id: beforeId,
        after_id: afterId,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks-view'] })
    },
  })
}
```

- [ ] **Step 3: TypeScript の型チェック**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: エラーなし

- [ ] **Step 4: コミット**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useTasks.ts
git commit -m "feat: useReorderTask フック追加・Task に order_index フィールド追加"
```

---

## Task 4: タスク一覧ドラッグ (`Tasks/index.tsx`)

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: インポートを追加**

`frontend/src/pages/Tasks/index.tsx` の先頭のインポートに追加:

```typescript
// @dnd-kit インポートを追加（既存 import 行の後）
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { HolderOutlined } from '@ant-design/icons'
```

また既存の icons インポート行:
```typescript
// 変更前
import { CopyOutlined, DownloadOutlined, FileTextOutlined, PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'

// 変更後（HolderOutlined を追加）
import { CopyOutlined, DownloadOutlined, FileTextOutlined, HolderOutlined, PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
```

- [ ] **Step 2: `useReorderTask` を useTasks からインポートに追加**

```typescript
// 変更前
import { useTasks, useCreateTask, useEstimateHours, useRecordEstimatedHours } from '../../hooks/useTasks'

// 変更後
import { useTasks, useCreateTask, useEstimateHours, useRecordEstimatedHours, useReorderTask } from '../../hooks/useTasks'
```

- [ ] **Step 3: `DraggableRow` コンポーネントを追加**

`TaskList` 関数の外側（`export default function TaskList()` の上）に追加:

```typescript
interface DraggableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  'data-row-key': string
}

function DraggableRow({ 'data-row-key': id, style, ...props }: DraggableRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  })
  return (
    <tr
      ref={setNodeRef}
      style={{
        ...style,
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        background: isDragging ? '#f0f5ff' : undefined,
        cursor: isDragging ? 'grabbing' : undefined,
      }}
      {...props}
      {...attributes}
      {...listeners}
    />
  )
}
```

- [ ] **Step 4: コンポーネント内に state・フック・ハンドラを追加**

`TaskList` 関数内の既存 state 宣言の後（`const [exporting, setExporting] = useState(false)` の後）に追加:

```typescript
  const [localItems, setLocalItems] = useState<Task[]>([])
  const reorderTask = useReorderTask()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )
```

`taskList` が変わったときに `localItems` を同期する `useEffect` を追加（既存 `useEffect` の後）:

```typescript
  useEffect(() => {
    if (taskList?.items) {
      setLocalItems(taskList.items)
    }
  }, [taskList?.items])
```

`handleSearch` の後にドラッグエンドハンドラを追加:

```typescript
  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const activeId = String(active.id)
    const overId = String(over.id)
    const oldIndex = localItems.findIndex((t) => t.id === activeId)
    const newIndex = localItems.findIndex((t) => t.id === overId)
    if (oldIndex === -1 || newIndex === -1) return

    const newItems = arrayMove(localItems, oldIndex, newIndex)
    const prevItems = localItems
    setLocalItems(newItems)  // 楽観的更新

    const beforeTask = newIndex > 0 ? newItems[newIndex - 1] : null
    const afterTask = newIndex < newItems.length - 1 ? newItems[newIndex + 1] : null

    reorderTask.mutate(
      {
        taskId: activeId,
        beforeId: beforeTask?.id ?? null,
        afterId: afterTask?.id ?? null,
      },
      {
        onError: () => {
          setLocalItems(prevItems)  // エラー時ロールバック
          void message.error('並び替えに失敗しました')
        },
      }
    )
  }
```

- [ ] **Step 5: columns にドラッグハンドル列を追加**

`columns` 配列の先頭に追加:

```typescript
  const columns = [
    {
      key: 'drag-handle',
      width: 40,
      render: () => <HolderOutlined style={{ color: '#bbb', cursor: 'grab' }} />,
    },
    {
      title: 'タスク名',
      // ... 以下既存のまま
```

- [ ] **Step 6: Table を DndContext + SortableContext でラップ**

`<Table ... />` を以下に置き換える:

```tsx
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <SortableContext
          items={localItems.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          <Table
            rowKey="id"
            loading={isLoading}
            dataSource={localItems}
            columns={columns}
            pagination={{ pageSize: 20, total: taskList?.total, showSizeChanger: false }}
            components={{ body: { row: DraggableRow } }}
          />
        </SortableContext>
      </DndContext>
```

- [ ] **Step 7: TypeScript の型チェック**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: エラーなし

- [ ] **Step 8: コミット**

```bash
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: タスク一覧にドラッグ&ドロップ並び替えを追加"
```

---

## Task 5: ボードのドラッグ (`Board/index.tsx`)

**Files:**
- Modify: `frontend/src/pages/Board/index.tsx`

- [ ] **Step 1: インポートを更新**

`frontend/src/pages/Board/index.tsx` のインポートを変更:

```typescript
// 変更前
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'

// 変更後
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
```

`useReorderTask` をインポート追加:

```typescript
import { useUpdateTask, useReorderTask } from '../../hooks/useTasks'
```

- [ ] **Step 2: `TaskCard` を `useDraggable` から `useSortable` に変更**

`TaskCard` コンポーネントを以下に変更:

```typescript
function TaskCard({ task, onCardClick }: { task: Task; onCardClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
  })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.3 : 1,
        marginBottom: 8,
        cursor: isDragging ? 'grabbing' : 'grab',
        zIndex: isDragging ? 1000 : undefined,
        position: isDragging ? 'relative' : undefined,
      }}
      {...attributes}
      {...listeners}
    >
      <Card
        size="small"
        onClick={onCardClick}
        hoverable
      >
        <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 13 }}>{task.title}</div>
        <Space size={4} wrap>
          <Tag color={PRIORITY_COLORS[task.priority] ?? 'default'} style={{ fontSize: 11 }}>
            {task.priority}
          </Tag>
          {task.due_date && (
            <span style={{ fontSize: 11, color: '#888' }}>{task.due_date}</span>
          )}
        </Space>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: `KanbanColumn` に `SortableContext` を追加**

`KanbanColumn` コンポーネントの props に `colTasks` の ID 列が必要なので、コンポーネントを以下に変更:

```typescript
function KanbanColumn({
  colKey,
  label,
  color,
  tasks,
  onCardClick,
}: {
  colKey: string
  label: string
  color: string
  tasks: Task[]
  onCardClick: (taskId: string) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: colKey })

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: '0 0 260px',
        background: isOver ? '#e6f4ff' : '#f5f5f5',
        borderRadius: 8,
        padding: 12,
        minHeight: 200,
        transition: 'background 0.15s',
      }}
    >
      <div
        style={{
          borderLeft: `4px solid ${color}`,
          paddingLeft: 8,
          marginBottom: 12,
          fontWeight: 600,
        }}
      >
        {label}{' '}
        <span style={{ color: '#888', fontSize: 13 }}>({tasks.length})</span>
      </div>
      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onCardClick={() => onCardClick(task.id)} />
        ))}
      </SortableContext>
    </div>
  )
}
```

- [ ] **Step 4: `Board` コンポーネントに `useReorderTask` と `handleDragEnd` 更新**

`Board` コンポーネント内で `useReorderTask` を追加:

```typescript
  const updateTask = useUpdateTask()
  const reorderTask = useReorderTask()
```

`handleDragEnd` を以下に置き換える:

```typescript
  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveTask(null)
    if (!over) {
      dragOccurredRef.current = false
      return
    }
    const activeId = String(active.id)
    const overId = String(over.id)

    // active タスクが属するカラムを特定
    const activeColKey = STATUS_COLUMNS.find((col) =>
      (columnTasks[col.key] ?? []).some((t) => t.id === activeId)
    )?.key

    // over がカラムキーかタスク ID かを判定し、対応するカラムを特定
    const overColKey =
      STATUS_COLUMNS.find((col) => col.key === overId)?.key ??
      STATUS_COLUMNS.find((col) => (columnTasks[col.key] ?? []).some((t) => t.id === overId))?.key

    if (!activeColKey || !overColKey) {
      dragOccurredRef.current = false
      return
    }

    if (activeColKey === overColKey) {
      // 同一カラム内の並び替え
      const colTasks = columnTasks[activeColKey] ?? []
      const activeIndex = colTasks.findIndex((t) => t.id === activeId)
      const overIndex = colTasks.findIndex((t) => t.id === overId)
      if (activeIndex !== -1 && overIndex !== -1 && activeIndex !== overIndex) {
        const newOrder = arrayMove(colTasks, activeIndex, overIndex)
        const beforeTask = overIndex > 0 ? newOrder[overIndex - 1] : null
        const afterTask = overIndex < newOrder.length - 1 ? newOrder[overIndex + 1] : null
        reorderTask.mutate({
          taskId: activeId,
          beforeId: beforeTask?.id ?? null,
          afterId: afterTask?.id ?? null,
        })
      }
    } else {
      // 別カラムへのドロップ → ステータス更新
      updateTask.mutate({ id: activeId, status: overColKey })
    }

    setTimeout(() => {
      dragOccurredRef.current = false
    }, 100)
  }
```

- [ ] **Step 5: TypeScript の型チェック**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: エラーなし

- [ ] **Step 6: 全バックエンドテストパスを確認**

```bash
pytest tests/ -v --tb=short -q
```

Expected: 全件 PASS

- [ ] **Step 7: コミット**

```bash
git add frontend/src/pages/Board/index.tsx
git commit -m "feat: ボードにカラム内ドラッグ&ドロップ並び替えを追加"
```
