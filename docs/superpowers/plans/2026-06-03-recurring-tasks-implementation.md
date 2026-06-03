# 繰り返しタスク Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスクに daily/weekly/monthly の繰り返しルールを設定し、完了時即生成と APScheduler 深夜バックフィルで次インスタンスを自動生成する。

**Architecture:** `tasks` テーブルに `recurrence_rule`・`recurrence_end_date`・`recurrence_origin_id` を追加し、`_spawn_next_recurrence` ヘルパーに生成ロジックを集約する。完了時トリガーは `update_task` エンドポイントに組み込み、バックフィルは APScheduler cron ジョブとして `main.py` に追加する。

**Tech Stack:** FastAPI + SQLAlchemy Async + Alembic + APScheduler + python-dateutil（インストール済み）+ React + Ant Design 5.x

---

## ファイル構成

| ファイル | 変更内容 |
|---------|---------|
| `alembic/versions/0007_recurring_tasks.py` | 新規: 3カラム追加 |
| `src/db/models.py` | 修正: Task モデルに3フィールド追加 |
| `src/models/task_web.py` | 修正: TaskCreate・TaskResponse に繰り返しフィールド追加 |
| `src/api/routers/tasks_crud.py` | 修正: `_spawn_next_recurrence` 追加・`_task_to_response` 更新・`create_task` 更新・`update_task` 更新・`DELETE /{id}/recurrence` 追加 |
| `src/api/main.py` | 修正: `recurrence_backfill_job` 追加・スケジューラー登録 |
| `tests/unit/test_task_recurrence.py` | 新規: 7テスト |
| `frontend/src/lib/api.ts` | 修正: Task インターフェース拡張・`deleteRecurrence` 追加 |
| `frontend/src/hooks/useTasks.ts` | 修正: `useDeleteRecurrence` フック追加 |
| `frontend/src/pages/Tasks/index.tsx` | 修正: 作成フォームに繰り返しフィールド・一覧にアイコン追加 |
| `frontend/src/pages/Tasks/TaskDetail.tsx` | 修正: 詳細に繰り返し表示・解除ボタン追加 |

---

### Task 1: DB マイグレーション + Python モデル変更

**Files:**
- Create: `alembic/versions/0007_recurring_tasks.py`
- Modify: `src/db/models.py`
- Modify: `src/models/task_web.py`

- [ ] **Step 1: マイグレーションファイルを作成する**

`alembic/versions/0007_recurring_tasks.py` を新規作成:

```python
"""recurring tasks

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("recurrence_rule", sa.String(10), nullable=True))
    op.add_column("tasks", sa.Column("recurrence_end_date", sa.Date(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "recurrence_origin_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "recurrence_origin_id")
    op.drop_column("tasks", "recurrence_end_date")
    op.drop_column("tasks", "recurrence_rule")
```

- [ ] **Step 2: SQLAlchemy Task モデルに3フィールドを追加する**

`src/db/models.py` の `order_index` 行の直後に追加する（`order_index: Mapped[float] ...` の次の行）:

```python
    recurrence_rule: Mapped[str | None] = mapped_column(String(10), nullable=True)
    recurrence_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recurrence_origin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
```

`src/db/models.py` の先頭 import に `date` が含まれていることを確認する（`from datetime import date, datetime` が既にある）。

- [ ] **Step 3: Pydantic モデルを更新する**

`src/models/task_web.py` の `TaskCreate` クラスに追加（`route: str | None = None` の次の行）:

```python
    recurrence_rule: Literal["daily", "weekly", "monthly"] | None = None
    recurrence_end_date: date | None = None
```

`TaskCreate` の先頭に `Literal` は既に import されているが、されていない場合は `from typing import Literal` を確認して追加する。

`TaskResponse` クラスに追加（`risk_level: str | None = None` の次の行）:

```python
    recurrence_rule: str | None = None
    recurrence_end_date: date | None = None
    recurrence_origin_id: uuid.UUID | None = None
```

- [ ] **Step 4: マイグレーションを実行して確認する**

```bash
alembic upgrade head
```

Expected: `Running upgrade 0006 -> 0007` と表示されてエラーなし。

- [ ] **Step 5: コミットする**

```bash
git add alembic/versions/0007_recurring_tasks.py src/db/models.py src/models/task_web.py
git commit -m "feat: 繰り返しタスク DB マイグレーション・モデル追加"
```

---

### Task 2: `_spawn_next_recurrence` ヘルパー + ユニットテスト

**Files:**
- Modify: `src/api/routers/tasks_crud.py`
- Create: `tests/unit/test_task_recurrence.py`

- [ ] **Step 1: テストファイルを作成してテストを書く（先に書いてから実装）**

`tests/unit/test_task_recurrence.py` を新規作成:

```python
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.db.models import Task


def _make_task(
    *,
    rule: str | None = "daily",
    end_date: date | None = None,
    due_date: date = date(2026, 6, 10),
    start_date: date | None = None,
    origin_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "週次レポート"
    t.description = None
    t.status = "completed"
    t.priority = "medium"
    t.assignee_id = "user-1"
    t.due_date = due_date
    t.start_date = start_date
    t.visibility = "team"
    t.project_id = project_id
    t.section_id = section_id
    t.parent_task_id = None
    t.created_by = "user-1"
    t.recurrence_rule = rule
    t.recurrence_end_date = end_date
    t.recurrence_origin_id = origin_id or t.id
    t.tags = []
    t.order_index = 1000.0
    t.completed_at = datetime(2026, 6, 10, 12, 0, 0)
    t.created_at = datetime(2026, 6, 1, 0, 0, 0)
    t.updated_at = datetime(2026, 6, 10, 12, 0, 0)
    t.confidence_score = None
    t.source_type = None
    t.sub_assignees = []
    t.work_hours = []
    t.subtasks = []
    t.project = None
    t.section = None
    return t


def _make_db(*, pending_task: MagicMock | None = None, max_order: float | None = 1000.0) -> AsyncMock:
    """_spawn_next_recurrence が実行するクエリ順にモックを設定する。
    Query 1: 既存の pending インスタンス確認 -> scalar_one_or_none = pending_task
    Query 2: max order_index 取得 -> scalar_one_or_none = max_order
    """
    mock_db = AsyncMock()
    call_count = 0

    def _scalar_result(val: object) -> MagicMock:
        r = MagicMock()
        r.scalar_one_or_none.return_value = val
        return r

    async def _execute(query: object) -> MagicMock:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx == 0:
            return _scalar_result(pending_task)
        return _scalar_result(max_order)

    mock_db.execute = _execute
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    return mock_db


@pytest.mark.asyncio
async def test_spawn_next_daily() -> None:
    """daily タスク完了後、翌日 due_date の新タスクが生成される"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="daily", due_date=date(2026, 6, 10))
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 6, 11)
    assert new_task.status == "not_started"
    assert new_task.recurrence_rule == "daily"
    assert new_task.recurrence_origin_id == task.recurrence_origin_id


@pytest.mark.asyncio
async def test_spawn_next_weekly() -> None:
    """weekly タスク完了後、+7日の新タスクが生成される"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="weekly", due_date=date(2026, 6, 10))
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 6, 17)


@pytest.mark.asyncio
async def test_spawn_next_monthly() -> None:
    """monthly タスク完了後、+1ヶ月の新タスクが生成される"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="monthly", due_date=date(2026, 6, 10))
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 7, 10)


@pytest.mark.asyncio
async def test_no_spawn_after_end_date() -> None:
    """次の due_date が end_date を超える場合は生成しない"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(
        rule="weekly",
        due_date=date(2026, 6, 10),
        end_date=date(2026, 6, 15),  # 次は 6/17 → 超過
    )
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_no_spawn_if_pending_exists() -> None:
    """同じ origin_id の未完了タスクが存在する場合は生成しない"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule="daily", due_date=date(2026, 6, 10))
    pending = _make_task(rule="daily", due_date=date(2026, 6, 11))
    db = _make_db(pending_task=pending)
    await _spawn_next_recurrence(task, db)

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_no_spawn_if_no_rule() -> None:
    """recurrence_rule が None のタスクは何もしない"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(rule=None)
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_preserves_start_date_offset() -> None:
    """start_date が設定されている場合、due_date との差分を保って次インスタンスに引き継ぐ"""
    from src.api.routers.tasks_crud import _spawn_next_recurrence

    task = _make_task(
        rule="weekly",
        due_date=date(2026, 6, 10),
        start_date=date(2026, 6, 8),  # 2日前から開始
    )
    db = _make_db()
    await _spawn_next_recurrence(task, db)

    db.add.assert_called_once()
    new_task = db.add.call_args[0][0]
    assert new_task.due_date == date(2026, 6, 17)
    assert new_task.start_date == date(2026, 6, 15)  # 2日前を維持
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
python -m pytest tests/unit/test_task_recurrence.py -v
```

Expected: `ImportError` または `AttributeError: _spawn_next_recurrence`（まだ実装していないため）

- [ ] **Step 3: `_spawn_next_recurrence` を実装する**

`src/api/routers/tasks_crud.py` の既存 `_renormalize_section` 関数の直前（`@router.patch("/{task_id}/order"...` の上）に追加する。

まず import に追加（ファイル冒頭の `from datetime import date, timedelta` を確認、`timedelta` が既にあれば OK、なければ追加）。また `dateutil.relativedelta` を import する。

`src/api/routers/tasks_crud.py` の import 部分の `from datetime import date, timedelta` の行を確認し、`timedelta` がなければ追加する。ファイル冒頭に以下を追加する（既存 import の末尾付近）:

```python
from dateutil.relativedelta import relativedelta
```

次に `_renormalize_section` の直前に `_spawn_next_recurrence` を追加する:

```python
async def _spawn_next_recurrence(task: Task, db: AsyncSession) -> None:
    """繰り返しタスクの次インスタンスを生成する。条件を満たさない場合は何もしない。"""
    if not task.recurrence_rule:
        return

    base_due: date = task.due_date or date.today()
    if task.recurrence_rule == "daily":
        next_due: date = base_due + timedelta(days=1)
    elif task.recurrence_rule == "weekly":
        next_due = base_due + timedelta(days=7)
    else:
        next_due = base_due + relativedelta(months=1)

    if task.recurrence_end_date and next_due > task.recurrence_end_date:
        return

    origin_id: uuid.UUID = task.recurrence_origin_id or task.id
    existing = await db.execute(
        select(Task).where(
            Task.recurrence_origin_id == origin_id,
            Task.status.notin_(["completed", "cancelled"]),
            Task.id != task.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    next_start: date | None = None
    if task.start_date and task.due_date:
        next_start = next_due - (task.due_date - task.start_date)

    if task.section_id is not None:
        max_result = await db.execute(
            select(func.max(Task.order_index)).where(Task.section_id == task.section_id)
        )
    elif task.project_id is not None:
        max_result = await db.execute(
            select(func.max(Task.order_index)).where(
                Task.section_id.is_(None), Task.project_id == task.project_id
            )
        )
    else:
        max_result = await db.execute(
            select(func.max(Task.order_index)).where(
                Task.section_id.is_(None), Task.project_id.is_(None)
            )
        )
    max_order = max_result.scalar_one_or_none()
    order_index = (float(max_order) if max_order is not None else 0.0) + 1000.0

    new_task = Task(
        title=task.title,
        description=task.description,
        status="not_started",
        priority=task.priority,
        assignee_id=task.assignee_id,
        due_date=next_due,
        start_date=next_start,
        visibility=task.visibility,
        project_id=task.project_id,
        section_id=task.section_id,
        parent_task_id=task.parent_task_id,
        created_by=task.created_by,
        recurrence_rule=task.recurrence_rule,
        recurrence_end_date=task.recurrence_end_date,
        recurrence_origin_id=origin_id,
        order_index=order_index,
    )
    db.add(new_task)
    for tag in (task.tags or []):
        db.add(TaskTag(task_id=new_task.id, tag=tag.tag if hasattr(tag, "tag") else tag))
    await db.flush()
```

`timedelta` が既存 import にあることを確認する。`src/api/routers/tasks_crud.py` の冒頭行を確認:

```python
from datetime import date, timedelta
```

もし `timedelta` がなければ追加する。

- [ ] **Step 4: テストを実行して全件パスを確認する**

```bash
python -m pytest tests/unit/test_task_recurrence.py -v
```

Expected:
```
test_spawn_next_daily PASSED
test_spawn_next_weekly PASSED
test_spawn_next_monthly PASSED
test_no_spawn_after_end_date PASSED
test_no_spawn_if_pending_exists PASSED
test_no_spawn_if_no_rule PASSED
test_spawn_preserves_start_date_offset PASSED
7 passed
```

- [ ] **Step 5: 全テストが壊れていないことを確認する**

```bash
python -m pytest tests/ -q
```

Expected: 228 passed（221 + 7）以上、0 failed

- [ ] **Step 6: コミットする**

```bash
git add tests/unit/test_task_recurrence.py src/api/routers/tasks_crud.py
git commit -m "feat: _spawn_next_recurrence ヘルパー追加・テスト 7 件"
```

---

### Task 3: API エンドポイント変更

**Files:**
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: `_task_to_response` に繰り返しフィールドを追加する**

`src/api/routers/tasks_crud.py` の `_task_to_response` 関数内、`return TaskResponse(` ブロックに以下を追加する（`risk_level=_compute_risk_level(task),` の次の行）:

```python
        recurrence_rule=task.recurrence_rule,
        recurrence_end_date=task.recurrence_end_date,
        recurrence_origin_id=task.recurrence_origin_id,
```

- [ ] **Step 2: `create_task` で `recurrence_origin_id` を自己参照にセットする**

`src/api/routers/tasks_crud.py` の `create_task` 関数内、`await db.flush()` の直後（タグ追加の前）に追加する:

現在のコード（抜粋）:
```python
    task = Task(**data)
    db.add(task)
    await db.flush()
    for tag in tags:
        db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
```

変更後:
```python
    task = Task(**data)
    db.add(task)
    await db.flush()
    if task.recurrence_rule:
        task.recurrence_origin_id = task.id
    for tag in tags:
        db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
```

- [ ] **Step 3: `update_task` で完了/キャンセル時に次インスタンスを生成する**

`src/api/routers/tasks_crud.py` の `update_task` 関数内、`await db.commit()` の前に追加する。

現在のコード（抜粋）:
```python
    if body.tags is not None:
        for existing in list(task.tags):
            await db.delete(existing)
        await db.flush()
        for tag in body.tags:
            db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
```

変更後:
```python
    if body.tags is not None:
        for existing in list(task.tags):
            await db.delete(existing)
        await db.flush()
        for tag in body.tags:
            db.add(TaskTag(task_id=task.id, tag=tag))
    if body.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
        await _spawn_next_recurrence(task, db)
    await db.commit()
```

- [ ] **Step 4: `DELETE /{task_id}/recurrence` エンドポイントを追加する**

`src/api/routers/tasks_crud.py` の `DELETE /{task_id}` エンドポイントの直前に追加する。

`DELETE /{task_id}` を探す（`@router.delete("/{task_id}"...` の行）。その直前に挿入:

```python
@router.delete("/{task_id}/recurrence", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurrence(
    task_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    task.recurrence_rule = None
    task.recurrence_end_date = None
    task.recurrence_origin_id = None
    await db.commit()
```

- [ ] **Step 5: 既存テストが全件パスすることを確認する**

```bash
python -m pytest tests/ -q
```

Expected: 228 passed 以上、0 failed

- [ ] **Step 6: コミットする**

```bash
git add src/api/routers/tasks_crud.py
git commit -m "feat: create_task・update_task・DELETE /recurrence に繰り返しロジックを追加"
```

---

### Task 4: APScheduler バックフィルジョブ

**Files:**
- Modify: `src/api/main.py`

- [ ] **Step 1: `recurrence_backfill_job` を実装する**

`src/api/main.py` の `polling_job` 関数定義の直前に追加する。

まず import を確認・追加する。`main.py` の既存 import に以下が必要:

```python
from sqlalchemy import select
from src.api.routers.tasks_crud import _spawn_next_recurrence
from src.db.engine import AsyncSessionLocal
from src.db.models import Task
```

既に import されているものはスキップする。不足しているものだけ追加する。

次に `recurrence_backfill_job` 関数を追加する（`polling_job` 関数の直前）:

```python
async def recurrence_backfill_job() -> None:
    """繰り返しタスクのうち後継インスタンスが未生成のものを生成する（深夜バックフィル）。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.recurrence_rule.is_not(None),
                Task.status.in_(["completed", "cancelled"]),
            )
        )
        tasks = result.scalars().all()
        for task in tasks:
            try:
                await _spawn_next_recurrence(task, db)
            except Exception as e:
                logger.warning("繰り返しバックフィルエラー task_id=%s: %s", task.id, e)
        await db.commit()
```

- [ ] **Step 2: スケジューラーにジョブを登録する**

`src/api/main.py` の `lifespan` 関数内、`scheduler.add_job(polling_job, ...)` の直後に追加する:

```python
    scheduler.add_job(
        recurrence_backfill_job,
        "cron",
        hour=2,
        minute=0,
        timezone="Asia/Tokyo",
        id="recurrence_backfill",
    )
```

- [ ] **Step 3: 既存テストが全件パスすることを確認する**

```bash
python -m pytest tests/ -q
```

Expected: 228 passed 以上、0 failed

- [ ] **Step 4: コミットする**

```bash
git add src/api/main.py
git commit -m "feat: APScheduler に繰り返しタスクバックフィルジョブを追加"
```

---

### Task 5: フロントエンド UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useTasks.ts`
- Modify: `frontend/src/pages/Tasks/index.tsx`
- Modify: `frontend/src/pages/Tasks/TaskDetail.tsx`

- [ ] **Step 1: `api.ts` の Task インターフェースに繰り返しフィールドを追加し、`deleteRecurrence` 関数を追加する**

`frontend/src/lib/api.ts` の `Task` インターフェース（`order_index?: number` の行の後）に追加:

```typescript
  recurrence_rule?: 'daily' | 'weekly' | 'monthly' | null
  recurrence_end_date?: string | null
  recurrence_origin_id?: string | null
```

同じファイルの末尾付近（`unarchiveProject` 関数の後）に追加:

```typescript
export async function deleteRecurrence(taskId: string): Promise<void> {
  await api.delete(`/tasks/${taskId}/recurrence`)
}
```

- [ ] **Step 2: `useDeleteRecurrence` フックを追加する**

`frontend/src/hooks/useTasks.ts` の `useExtractTasks` の直前に追加:

```typescript
export function useDeleteRecurrence() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) => deleteRecurrence(taskId),
    onSuccess: (_, taskId) => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks-view'] })
    },
  })
}
```

`useTasks.ts` の import 行を更新して `deleteRecurrence` を追加する:

```typescript
import api, { type Task, type TaskListResponse, type HourEstimate, type ExtractResult, getEstimateHours, extractTasksFromText, deleteRecurrence } from '../lib/api'
```

- [ ] **Step 3: タスク一覧の作成フォームに繰り返しフィールドを追加する**

`frontend/src/pages/Tasks/index.tsx` の import に `RedoOutlined` を追加する（`CopyOutlined, DownloadOutlined, ...` の行）:

```typescript
import { CopyOutlined, DownloadOutlined, FileTextOutlined, HolderOutlined, PlusOutlined, RedoOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
```

同ファイルの `handleCreate` 関数を更新して `recurrence_rule`・`recurrence_end_date` を API に渡せるようにする（現状の `taskValues` に自動的に含まれるため変更不要。ただし `due_date` が dayjs オブジェクトの場合は文字列変換が必要）。

フォーム内の `<Form.Item name="visibility" ...>` の直前に繰り返しフィールドを追加する:

```tsx
          <Form.Item name="recurrence_rule" label="繰り返し">
            <Select
              allowClear
              placeholder="なし"
              style={{ width: 160 }}
              options={[
                { label: '毎日', value: 'daily' },
                { label: '毎週', value: 'weekly' },
                { label: '毎月', value: 'monthly' },
              ]}
            />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.recurrence_rule !== curr.recurrence_rule}
          >
            {({ getFieldValue }) =>
              getFieldValue('recurrence_rule') ? (
                <Form.Item name="recurrence_end_date" label="繰り返し終了日">
                  <DatePicker style={{ width: 160 }} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
```

`handleCreate` 関数を更新して `recurrence_end_date` を ISO 文字列に変換する:

```typescript
  const handleCreate = async (values: Record<string, unknown>) => {
    const { estimated_hours, recurrence_end_date, ...taskValues } = values as {
      estimated_hours?: number
      recurrence_end_date?: import('dayjs').Dayjs
      [key: string]: unknown
    }
    const payload = {
      ...taskValues,
      ...(recurrence_end_date
        ? { recurrence_end_date: recurrence_end_date.format('YYYY-MM-DD') }
        : {}),
    }
    const created = await createTask.mutateAsync(
      payload as Partial<import('../../lib/api').Task> & { title: string },
    )
    if (estimated_hours != null && created?.id) {
      await recordEstimatedHours.mutateAsync({
        taskId: created.id as string,
        estimatedHours: estimated_hours,
      })
    }
    setOpen(false)
    form.resetFields()
    autoFilledRef.current = false
    setNewTitle('')
  }
```

タスク名列の render 関数に `RedoOutlined` アイコンを追加する（既存の `columns` 配列内の `タスク名` 列の render 関数を更新）:

```tsx
      render: (title: string, rec: Task) => (
        <Space size={4}>
          <a onClick={() => navigate(`/tasks/${rec.id}`)}>{title}</a>
          {rec.recurrence_rule && (
            <Tooltip title={`繰り返し: ${rec.recurrence_rule === 'daily' ? '毎日' : rec.recurrence_rule === 'weekly' ? '毎週' : '毎月'}`}>
              <RedoOutlined style={{ color: '#1677ff', fontSize: 12 }} />
            </Tooltip>
          )}
        </Space>
      ),
```

現在の `render` 関数を上記で置き換える。現在の `render` 関数は以下のような形:
```tsx
      render: (title: string, rec: Task) => (
        <a onClick={() => navigate(`/tasks/${rec.id}`)}>{title}</a>
      ),
```

- [ ] **Step 4: タスク詳細に繰り返し情報と解除ボタンを追加する**

`frontend/src/pages/Tasks/TaskDetail.tsx` の import を更新する:

```typescript
import { useTask, useUpdateTask, useDeleteTask, useDeleteRecurrence } from '../../hooks/useTasks'
```

`import { CopyOutlined, DeleteOutlined } from '@ant-design/icons'` を:

```typescript
import { CopyOutlined, DeleteOutlined, RedoOutlined } from '@ant-design/icons'
```

コンポーネント内の hooks 呼び出し部に追加する（`const clarify = ...` の後）:

```typescript
  const deleteRecurrence = useDeleteRecurrence()
```

`Descriptions` コンポーネント内の「期限」行の直後に追加する（`<Descriptions.Item label="期限">` の次）:

```tsx
            {task.recurrence_rule && (
              <Descriptions.Item label="繰り返し">
                <Space>
                  <RedoOutlined />
                  {task.recurrence_rule === 'daily' ? '毎日' : task.recurrence_rule === 'weekly' ? '毎週' : '毎月'}
                  {task.recurrence_end_date && `（${task.recurrence_end_date} まで）`}
                  <Popconfirm
                    title="繰り返しを解除しますか？"
                    onConfirm={async () => {
                      try {
                        await deleteRecurrence.mutateAsync(id ?? '')
                        void message.success('繰り返しを解除しました')
                      } catch {
                        void message.error('解除に失敗しました')
                      }
                    }}
                  >
                    <Button size="small" danger>解除</Button>
                  </Popconfirm>
                </Space>
              </Descriptions.Item>
            )}
```

- [ ] **Step 5: TypeScript の型チェックを実行する**

```bash
cd frontend && npx tsc --noEmit
```

Expected: エラーなし（出力なし）

- [ ] **Step 6: 全バックエンドテストをパスすることを確認する**

```bash
python -m pytest tests/ -q
```

Expected: 228 passed 以上、0 failed

- [ ] **Step 7: コミットする**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useTasks.ts frontend/src/pages/Tasks/index.tsx frontend/src/pages/Tasks/TaskDetail.tsx
git commit -m "feat: 繰り返しタスク フロントエンド UI を追加"
```

---

## 完了後の追加作業

全タスク実装後、以下を実行すること:

1. `docs/tasks.md` の「繰り返しタスク」項目を `[x]` に更新し、完了日を記載する
2. `docs/progress.md` に今セッションの作業内容を追記する
3. origin/master にプッシュする

```bash
git push origin master
```
