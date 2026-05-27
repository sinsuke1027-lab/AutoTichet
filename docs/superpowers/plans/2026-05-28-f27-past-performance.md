# F-27 過去実績参照機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク詳細の工数タブに、同一タグを持つ完了済みタスクの実績工数（平均・最小・最大・件数＋最新3件リスト）を参考情報として表示する。

**Architecture:** 専用エンドポイント `GET /api/v1/tasks/{task_id}/past-performance` を `task_details.py` に追加し、タグ一致 + 完了 + actual_hours IS NOT NULL のタスクを DB 側で集計して返す。フロントエンドは `WorkHoursPanel.tsx` の下部に `PastPerformanceSection` コンポーネントを追加して表示する。

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2, React 18, TanStack Query v5, Ant Design 5.x

---

## ファイル構成

| 操作 | ファイル |
|------|---------|
| 修正 | `src/models/task_web.py` — `PastPerformanceSimilarTask`, `PastPerformanceResponse` 追加 |
| 修正 | `src/api/routers/task_details.py` — `GET /{task_id}/past-performance` エンドポイント追加 |
| 作成 | `tests/unit/test_past_performance.py` — 6 件のユニットテスト |
| 修正 | `frontend/src/hooks/useTaskDetails.ts` — `usePastPerformance` フック追加 |
| 修正 | `frontend/src/pages/Tasks/components/WorkHoursPanel.tsx` — `PastPerformanceSection` 追加 |

---

## Task 1: Pydantic モデル追加

**Files:**
- Modify: `src/models/task_web.py`（末尾に追加）

- [ ] **Step 1: `PastPerformanceSimilarTask` と `PastPerformanceResponse` を `src/models/task_web.py` 末尾に追加**

```python
# --- 過去実績参照 (F-27) ---


class PastPerformanceSimilarTask(BaseModel):
    id: uuid.UUID
    title: str
    actual_hours: float


class PastPerformanceResponse(BaseModel):
    avg_actual_hours: float | None   # None = 実績データなし
    min_actual_hours: float | None
    max_actual_hours: float | None
    task_count: int
    similar_tasks: list[PastPerformanceSimilarTask]
```

- [ ] **Step 2: インポート確認**

`src/models/task_web.py` の先頭に `uuid` と `datetime` がインポートされていることを確認（既に存在する）。

- [ ] **Step 3: Python で動作確認**

```bash
python -c "from src.models.task_web import PastPerformanceResponse, PastPerformanceSimilarTask; print('OK')"
```

Expected: `OK`

---

## Task 2: バックエンド エンドポイント（TDD）

**Files:**
- Create: `tests/unit/test_past_performance.py`
- Modify: `src/api/routers/task_details.py`

### Step 1: テストファイル作成

- [ ] **Step 1: `tests/unit/test_past_performance.py` を作成**

```python
import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")


def _make_client(mock_db: AsyncMock) -> TestClient:
    from src.api.routers.task_details import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _task_mock() -> MagicMock:
    from src.db.models import Task

    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    return t


def _exec_task(task: MagicMock | None) -> MagicMock:
    m = MagicMock()
    m.scalar_one_or_none.return_value = task
    return m


def _exec_tags(tags: list[str]) -> MagicMock:
    m = MagicMock()
    m.scalars.return_value.all.return_value = tags
    return m


def _exec_agg(
    avg: float | None,
    min_h: float | None,
    max_h: float | None,
    count: int,
) -> MagicMock:
    row = MagicMock()
    row.avg_hours = avg
    row.min_hours = min_h
    row.max_hours = max_h
    row.task_count = count
    m = MagicMock()
    m.one.return_value = row
    return m


def _exec_similar(rows: list) -> MagicMock:
    m = MagicMock()
    m.all.return_value = rows
    return m


def _similar_row(title: str, actual_hours: float) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.title = title
    row.actual_hours = actual_hours
    return row


def test_past_performance_no_tags() -> None:
    """タグなしタスクは task_count=0 の空レスポンスを返す"""
    task = _task_mock()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags([]),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["similar_tasks"] == []
    assert data["avg_actual_hours"] is None


def test_past_performance_with_matching_tasks() -> None:
    """類似完了タスクがある場合、集計値と一覧を返す"""
    task = _task_mock()
    mock_db = AsyncMock()
    similar = [
        _similar_row("月次報告（4月）", 2.0),
        _similar_row("月次報告（3月）", 3.0),
    ]
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["報告"]),
        _exec_agg(2.5, 2.0, 3.0, 2),
        _exec_similar(similar),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 2
    assert data["avg_actual_hours"] == 2.5
    assert data["min_actual_hours"] == 2.0
    assert data["max_actual_hours"] == 3.0
    assert len(data["similar_tasks"]) == 2
    assert data["similar_tasks"][0]["title"] == "月次報告（4月）"
    assert data["similar_tasks"][0]["actual_hours"] == 2.0


def test_past_performance_no_completed_tasks() -> None:
    """タグ一致タスクはあるが実績なし（未完了 or actual_hours=null）"""
    task = _task_mock()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["報告"]),
        _exec_agg(None, None, None, 0),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None
    assert data["similar_tasks"] == []


def test_past_performance_task_not_found() -> None:
    """存在しない task_id は 404"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(None),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{uuid.uuid4()}/past-performance")
    assert resp.status_code == 404


def test_past_performance_limited_to_3() -> None:
    """similar_tasks は最大 3 件（DB 側で LIMIT 3 をかける）"""
    task = _task_mock()
    mock_db = AsyncMock()
    similar = [_similar_row(f"タスク{i}", float(i + 1)) for i in range(3)]
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["月次"]),
        _exec_agg(2.0, 1.0, 3.0, 5),
        _exec_similar(similar),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["similar_tasks"]) == 3


def test_past_performance_multiple_tags() -> None:
    """複数タグを持つタスクでも正常動作する"""
    task = _task_mock()
    mock_db = AsyncMock()
    similar = [_similar_row("週次レビュー（先週）", 1.5)]
    mock_db.execute = AsyncMock(side_effect=[
        _exec_task(task),
        _exec_tags(["週次", "レビュー", "報告"]),
        _exec_agg(1.5, 1.5, 1.5, 1),
        _exec_similar(similar),
    ])
    client = _make_client(mock_db)
    resp = client.get(f"/api/v1/tasks/{task.id}/past-performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 1
    assert data["similar_tasks"][0]["actual_hours"] == 1.5
```

- [ ] **Step 2: テストが FAIL することを確認**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket"
.venv\Scripts\Activate.ps1
pytest tests/unit/test_past_performance.py -v
```

Expected: FAIL（`ImportError` or route not found）

### Step 2: エンドポイント実装

- [ ] **Step 3: `src/api/routers/task_details.py` の import を更新**

ファイル冒頭の import を以下に変更（`distinct`, `func`, `TaskTag` を追加）:

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskAssignee, TaskComment, TaskDependency, TaskTag, TaskWorkHour
from src.models.task_web import (
    CommentCreate,
    CommentResponse,
    DependencyCreate,
    DependencyResponse,
    PastPerformanceResponse,
    PastPerformanceSimilarTask,
    TaskAssigneeCreate,
    TaskAssigneeResponse,
    WorkHourCreate,
    WorkHourResponse,
)
```

- [ ] **Step 4: `get_past_performance` エンドポイントを `src/api/routers/task_details.py` の工数セクションの後（依存関係セクションの前）に追加**

```python
# --- 過去実績参照 ---


@router.get("/{task_id}/past-performance", response_model=PastPerformanceResponse)
async def get_past_performance(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> PastPerformanceResponse:
    await _get_task_or_404(task_id, db)

    tags_result = await db.execute(
        select(TaskTag.tag).where(TaskTag.task_id == task_id)
    )
    tags = list(tags_result.scalars().all())

    if not tags:
        return PastPerformanceResponse(
            avg_actual_hours=None,
            min_actual_hours=None,
            max_actual_hours=None,
            task_count=0,
            similar_tasks=[],
        )

    similar_ids = (
        select(TaskTag.task_id)
        .where(TaskTag.tag.in_(tags), TaskTag.task_id != task_id)
        .distinct()
    )

    agg_result = await db.execute(
        select(
            func.avg(TaskWorkHour.actual_hours).label("avg_hours"),
            func.min(TaskWorkHour.actual_hours).label("min_hours"),
            func.max(TaskWorkHour.actual_hours).label("max_hours"),
            func.count(distinct(TaskWorkHour.task_id)).label("task_count"),
        )
        .join(Task, Task.id == TaskWorkHour.task_id)
        .where(
            TaskWorkHour.task_id.in_(similar_ids),
            Task.status == "completed",
            TaskWorkHour.actual_hours.is_not(None),
        )
    )
    agg_row = agg_result.one()

    if not agg_row.task_count:
        return PastPerformanceResponse(
            avg_actual_hours=None,
            min_actual_hours=None,
            max_actual_hours=None,
            task_count=0,
            similar_tasks=[],
        )

    similar_result = await db.execute(
        select(Task.id, Task.title, TaskWorkHour.actual_hours)
        .join(TaskWorkHour, TaskWorkHour.task_id == Task.id)
        .where(
            TaskWorkHour.task_id.in_(similar_ids),
            Task.status == "completed",
            TaskWorkHour.actual_hours.is_not(None),
        )
        .order_by(TaskWorkHour.recorded_at.desc())
        .limit(3)
    )
    similar_tasks = [
        PastPerformanceSimilarTask(id=row.id, title=row.title, actual_hours=row.actual_hours)
        for row in similar_result.all()
    ]

    return PastPerformanceResponse(
        avg_actual_hours=float(agg_row.avg_hours),
        min_actual_hours=float(agg_row.min_hours),
        max_actual_hours=float(agg_row.max_hours),
        task_count=agg_row.task_count,
        similar_tasks=similar_tasks,
    )
```

- [ ] **Step 5: テストを実行して全件 PASS を確認**

```bash
pytest tests/unit/test_past_performance.py -v
```

Expected: 6 passed

- [ ] **Step 6: 全テストが壊れていないことを確認**

```bash
pytest tests/unit/ -v --ignore=tests/unit/test_connectors.py --ignore=tests/unit/test_teams_chat.py --ignore=tests/unit/test_onenote.py
```

Expected: 147 passed（141 + 6）

- [ ] **Step 7: コミット**

```bash
git add src/models/task_web.py src/api/routers/task_details.py tests/unit/test_past_performance.py
git commit -m "feat: F-27 過去実績参照 API 追加（GET /tasks/{id}/past-performance）"
```

---

## Task 3: フロントエンド フック追加

**Files:**
- Modify: `frontend/src/hooks/useTaskDetails.ts`（末尾に追加）

- [ ] **Step 1: `useTaskDetails.ts` の末尾に interface と `usePastPerformance` を追加**

```typescript
interface PastPerformanceSimilarTask {
  id: string
  title: string
  actual_hours: number
}

interface PastPerformanceData {
  avg_actual_hours: number | null
  min_actual_hours: number | null
  max_actual_hours: number | null
  task_count: number
  similar_tasks: PastPerformanceSimilarTask[]
}

export function usePastPerformance(taskId: string) {
  return useQuery<PastPerformanceData>({
    queryKey: ['past-performance', taskId],
    queryFn: () => api.get(`/tasks/${taskId}/past-performance`).then((r) => r.data),
    staleTime: 5 * 60 * 1000,
    enabled: !!taskId,
  })
}
```

- [ ] **Step 2: TypeScript 型チェック**

```bash
cd frontend
npx tsc --noEmit
```

Expected: エラーなし

---

## Task 4: WorkHoursPanel に PastPerformanceSection 追加

**Files:**
- Modify: `frontend/src/pages/Tasks/components/WorkHoursPanel.tsx`（全体置き換え）

- [ ] **Step 1: `WorkHoursPanel.tsx` を以下の内容で置き換え**

```tsx
import { Button, Divider, Form, InputNumber, List, Space, Spin, Statistic, Table, Typography } from 'antd'
import { useWorkHours, useCreateWorkHour, usePastPerformance } from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
}

interface PastPerformanceSimilarTaskItem {
  id: string
  title: string
  actual_hours: number
}

interface PastPerformanceData {
  avg_actual_hours: number | null
  min_actual_hours: number | null
  max_actual_hours: number | null
  task_count: number
  similar_tasks: PastPerformanceSimilarTaskItem[]
}

function PastPerformanceSection({ taskId }: Props) {
  const { data, isLoading } = usePastPerformance(taskId)

  return (
    <div>
      <Divider orientation="left" plain>
        過去の類似タスク実績
      </Divider>
      {isLoading ? (
        <Spin size="small" />
      ) : !data || data.task_count === 0 ? (
        <Typography.Text type="secondary">過去データなし</Typography.Text>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <Statistic
              title="平均実績"
              value={data.avg_actual_hours ?? 0}
              suffix="h"
              precision={1}
            />
            <Statistic
              title="最小"
              value={data.min_actual_hours ?? 0}
              suffix="h"
              precision={1}
            />
            <Statistic
              title="最大"
              value={data.max_actual_hours ?? 0}
              suffix="h"
              precision={1}
            />
            <Statistic title="件数" value={data.task_count} suffix="件" />
          </Space>
          <List<PastPerformanceSimilarTaskItem>
            size="small"
            dataSource={data.similar_tasks}
            renderItem={(item) => (
              <List.Item>
                <Typography.Text>{item.title}</Typography.Text>
                <Typography.Text type="secondary" style={{ marginLeft: 'auto' }}>
                  {item.actual_hours}h
                </Typography.Text>
              </List.Item>
            )}
          />
        </Space>
      )}
    </div>
  )
}

export default function WorkHoursPanel({ taskId }: Props) {
  const { data: records = [] } = useWorkHours(taskId)
  const createWorkHour = useCreateWorkHour(taskId)
  const [form] = Form.useForm()

  const handleSubmit = async () => {
    const values = await form.validateFields()
    await createWorkHour.mutateAsync(
      values as { estimated_hours?: number; actual_hours?: number; notes?: string },
    )
    form.resetFields()
  }

  const columns = [
    {
      title: '記録日時',
      dataIndex: 'recorded_at',
      key: 'recorded_at',
      render: (d: string) => new Date(d).toLocaleString('ja-JP'),
    },
    {
      title: '予定(h)',
      dataIndex: 'estimated_hours',
      key: 'estimated_hours',
      render: (v: number | null) => v ?? '—',
    },
    {
      title: '実績(h)',
      dataIndex: 'actual_hours',
      key: 'actual_hours',
      render: (v: number | null) => v ?? '—',
    },
    {
      title: 'メモ',
      dataIndex: 'notes',
      key: 'notes',
      render: (v: string | null) => v ?? '—',
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Form form={form} layout="inline">
        <Form.Item name="estimated_hours" label="予定工数(h)">
          <InputNumber min={0} step={0.5} precision={1} />
        </Form.Item>
        <Form.Item name="actual_hours" label="実績工数(h)">
          <InputNumber min={0} step={0.5} precision={1} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" onClick={handleSubmit} loading={createWorkHour.isPending}>
            記録
          </Button>
        </Form.Item>
      </Form>
      <Table
        rowKey="id"
        dataSource={records}
        columns={columns}
        size="small"
        pagination={false}
        locale={{ emptyText: '工数記録はありません' }}
      />
      <PastPerformanceSection taskId={taskId} />
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript 型チェック**

```bash
cd frontend
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 3: コミット**

```bash
git add frontend/src/hooks/useTaskDetails.ts frontend/src/pages/Tasks/components/WorkHoursPanel.tsx
git commit -m "feat: F-27 過去実績参照 UI 追加（WorkHoursPanel に PastPerformanceSection）"
```
