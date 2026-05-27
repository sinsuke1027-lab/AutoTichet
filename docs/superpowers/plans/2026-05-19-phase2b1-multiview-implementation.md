# Web App Phase 2B-1 — マルチビュー実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** カンバン・カレンダー・ガントの 3 ビューを独立ページとして追加し、F-36 自動リスケジュールをガントと一体で実装する

**Architecture:** 既存の `GET /api/v1/tasks` に `due_date_gte`/`lte`/`assignee_ids` フィルタを追加して 3 ビュー共通のデータソースとし、F-36 は `POST /tasks/{id}/reschedule` 新設エンドポイントでバックエンド BFS 走査・一括更新する。`start_date` は初期マイグレーション・ORM・Pydantic モデルに既存のため DB マイグレーション不要。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.x async / Pydantic v2 / React 18 / TypeScript strict / @dnd-kit/core @dnd-kit/sortable / react-big-calendar + date-fns / gantt-task-react / Ant Design 5.x / TanStack Query 5.x

---

## ファイル構成

### 新規作成
```
tests/unit/test_reschedule.py
frontend/src/hooks/useTasksForView.ts
frontend/src/hooks/useReschedule.ts
frontend/src/pages/Board/index.tsx
frontend/src/pages/Calendar/index.tsx
frontend/src/pages/Gantt/index.tsx
```

### 変更
```
src/models/task_web.py              RescheduleRequest/Response 追加
src/api/routers/tasks_crud.py       due_date_gte/lte/assignee_ids フィルタ + reschedule エンドポイント追加
frontend/src/lib/api.ts             start_date・DependencyResponse・UserProfile・Reschedule* 追加
frontend/src/App.tsx                /board /calendar /gantt ルート + サイドバー追加
```

---

## 既存コードのパターン（必読）

### バックエンド
- `DbDep = Annotated[AsyncSession, Depends(get_db)]` パターン
- `selectinload(Task.tags)` / `selectinload(Task.sub_assignees)` を SELECT 時に必ず付ける
- `await db.delete(obj)` は **await 必須**（AsyncSession.delete はコルーチン）
- `router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])`
- テスト: `FastAPI()` + `app.dependency_overrides[get_db] = lambda: mock_db`

### フロントエンド
- axios baseURL = `/api/v1` → フック内のパスに `/api/v1` を含めない（`/tasks` ✅ `/api/v1/tasks` ❌）
- `useUpdateTask(taskId?)` の呼び出し: `mutate({ id: 'uuid', status: 'in_progress' })`
- TypeScript strict + verbatimModuleSyntax: type-only は `import type { Foo }` または `import { type Foo }`

---

## Task 1: バックエンド API 拡張（フィルタ + reschedule）

**Files:**
- Modify: `src/models/task_web.py`
- Modify: `src/api/routers/tasks_crud.py`
- Create: `tests/unit/test_reschedule.py`

- [ ] **Step 1: RescheduleRequest / RescheduleResponse を task_web.py に追加する**

`src/models/task_web.py` のファイル末尾（`UserResponse` の後）に追加:

```python
# --- Reschedule ---


class RescheduleRequest(BaseModel):
    new_start_date: date | None = None
    new_due_date: date


class RescheduleResponse(BaseModel):
    updated_tasks: list[TaskResponse]
```

- [ ] **Step 2: テストを書く（先に失敗させる）**

`tests/unit/test_reschedule.py` を新規作成:

```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

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


def test_reschedule_route_exists() -> None:
    app = FastAPI()
    app.include_router(router)
    routes = [r.path for r in app.routes]
    assert "/api/v1/tasks/{task_id}/reschedule" in routes


def test_reschedule_returns_404_for_missing_task() -> None:
    mock_db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result_mock)
    client = _make_client(mock_db)
    resp = client.post(
        f"/api/v1/tasks/{uuid.uuid4()}/reschedule",
        json={"new_due_date": "2026-06-01"},
    )
    assert resp.status_code == 404


def test_list_tasks_accepts_due_date_gte() -> None:
    mock_db = AsyncMock()
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[count_mock, result_mock])
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks?due_date_gte=2026-06-01")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_tasks_accepts_assignee_ids() -> None:
    mock_db = AsyncMock()
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 0
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[count_mock, result_mock])
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks?assignee_ids=user-1&assignee_ids=user-2")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
```

- [ ] **Step 3: テストが失敗することを確認**

```powershell
.venv\Scripts\python -m pytest tests/unit/test_reschedule.py -v
```

Expected: `test_reschedule_route_exists` FAIL (reschedule route not yet defined)

- [ ] **Step 4: tasks_crud.py に due_date フィルタ・assignee_ids・reschedule エンドポイントを追加**

`src/api/routers/tasks_crud.py` の変更:

**インポートに追加（既存の import 行に追記）:**
```python
from datetime import date, timedelta
from collections import deque
```

```python
from src.db.models import Task, TaskAssignee, TaskDependency, TaskTag
```

```python
from src.models.task_web import (
    RescheduleRequest,
    RescheduleResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
```

**`list_tasks` 関数のシグネチャに追加（既存パラメータの後）:**
```python
    due_date_gte: date | None = Query(default=None),
    due_date_lte: date | None = Query(default=None),
    assignee_ids: list[str] | None = Query(default=None),
```

**`list_tasks` 関数の `if q:` ブロックの後に追加:**
```python
    if due_date_gte:
        query = query.where(Task.due_date >= due_date_gte)
    if due_date_lte:
        query = query.where(Task.due_date <= due_date_lte)
    if assignee_ids:
        query = query.where(Task.assignee_id.in_(assignee_ids))
```

**`delete_task` エンドポイントの後に追加（ファイル末尾の方）:**
```python
async def _cascade_reschedule(
    db: AsyncSession, root_id: uuid.UUID, delta: timedelta
) -> list[Task]:
    """依存タスクを BFS で走査して日程を連鎖移動する。"""
    updated: list[Task] = []
    queue: deque[uuid.UUID] = deque([root_id])
    visited: set[uuid.UUID] = {root_id}
    while queue:
        current_id = queue.popleft()
        dep_result = await db.execute(
            select(TaskDependency).where(TaskDependency.depends_on_task_id == current_id)
        )
        for dep in dep_result.scalars().all():
            if dep.task_id in visited:
                continue
            visited.add(dep.task_id)
            task_result = await db.execute(
                select(Task)
                .where(Task.id == dep.task_id)
                .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
            )
            task = task_result.scalar_one_or_none()
            if task and task.due_date:
                if task.start_date:
                    task.start_date = task.start_date + delta
                task.due_date = task.due_date + delta
                updated.append(task)
                queue.append(dep.task_id)
    return updated


@router.post("/{task_id}/reschedule", response_model=RescheduleResponse)
async def reschedule_task(
    task_id: uuid.UUID, body: RescheduleRequest, db: DbDep, current_user: CurrentUser
) -> RescheduleResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    old_due = task.due_date
    task.start_date = body.new_start_date
    task.due_date = body.new_due_date

    dependent_tasks: list[Task] = []
    if old_due and body.new_due_date and old_due != body.new_due_date:
        delta = timedelta(days=(body.new_due_date - old_due).days)
        dependent_tasks = await _cascade_reschedule(db, task_id, delta)

    await db.commit()
    await db.refresh(task, ["tags", "sub_assignees"])
    for t in dependent_tasks:
        await db.refresh(t, ["tags", "sub_assignees"])

    return RescheduleResponse(updated_tasks=[_task_to_response(t) for t in [task, *dependent_tasks]])
```

- [ ] **Step 5: テストを実行して全件 PASS を確認**

```powershell
.venv\Scripts\python -m pytest tests/unit/test_reschedule.py tests/unit/test_tasks_crud_router.py -v
```

Expected: 全 PASS（test_reschedule.py 4 件 + test_tasks_crud_router.py 8 件）

- [ ] **Step 6: 全ユニットテストを実行**

```powershell
.venv\Scripts\python -m pytest tests/unit/ -q
```

Expected: 114 passed 以上（新規 4 件追加）

- [ ] **Step 7: コミット**

```bash
git add src/models/task_web.py src/api/routers/tasks_crud.py tests/unit/test_reschedule.py
git commit -m "feat: add due_date filters, assignee_ids filter, and reschedule endpoint"
```

---

## Task 2: フロントエンドライブラリインストール + api.ts + App.tsx + スタブページ

**Files:**
- Modify: `frontend/package.json`（npm install）
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/Board/index.tsx`（スタブ）
- Create: `frontend/src/pages/Calendar/index.tsx`（スタブ）
- Create: `frontend/src/pages/Gantt/index.tsx`（スタブ）

- [ ] **Step 1: ライブラリをインストール**

```powershell
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npm install @dnd-kit/core @dnd-kit/sortable react-big-calendar date-fns gantt-task-react
npm install -D @types/react-big-calendar
```

Expected: 追加インストール完了・エラーなし

- [ ] **Step 2: api.ts に型定義を追加**

`frontend/src/lib/api.ts` の末尾（`SectionCreate` の後）に追加:

```typescript
export interface DependencyResponse {
  id: string
  depends_on_task_id: string
}

export interface UserProfile {
  user_id: string
  display_name: string
  email: string | null
  role: string
  capacity_hours_per_day: number
}

export interface RescheduleRequest {
  new_start_date?: string | null
  new_due_date: string
}

export interface RescheduleResponse {
  updated_tasks: Task[]
}
```

また `Task` インターフェースに `start_date?: string | null` を追加（`due_date` の次の行）:
```typescript
  start_date?: string | null
```

- [ ] **Step 3: スタブページを作成**

`frontend/src/pages/Board/index.tsx`:
```tsx
export default function Board() {
  return <div>カンバン（実装中）</div>
}
```

`frontend/src/pages/Calendar/index.tsx`:
```tsx
export default function CalendarView() {
  return <div>カレンダー（実装中）</div>
}
```

`frontend/src/pages/Gantt/index.tsx`:
```tsx
export default function GanttView() {
  return <div>ガント（実装中）</div>
}
```

- [ ] **Step 4: App.tsx にルートとサイドバーを追加**

`frontend/src/App.tsx` を以下のように更新:

```tsx
import { useMsal, useIsAuthenticated } from '@azure/msal-react'
import { Navigate, Route, Routes, useNavigate, useLocation } from 'react-router-dom'
import { Button, Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  CheckSquareOutlined,
  ProjectOutlined,
  CalendarOutlined,
  TeamOutlined,
  UploadOutlined,
  AppstoreOutlined,
  ScheduleOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { loginRequest } from './lib/msal'
import Dashboard from './pages/Dashboard'
import TaskList from './pages/Tasks'
import TaskDetail from './pages/Tasks/TaskDetail'
import Schedule from './pages/Schedule'
import Workload from './pages/Workload'
import ProjectList from './pages/Projects/List'
import ProjectDetail from './pages/Projects'
import ImportPage from './pages/Import'
import Board from './pages/Board'
import CalendarView from './pages/Calendar'
import GanttView from './pages/Gantt'

const { Header, Content, Sider } = Layout

function LoginPage() {
  const { instance } = useMsal()
  return (
    <div style={{ textAlign: 'center', paddingTop: 100 }}>
      <Typography.Title>AutoTicket</Typography.Title>
      <Button type="primary" size="large" onClick={() => instance.loginRedirect(loginRequest)}>
        Microsoft アカウントでログイン
      </Button>
    </div>
  )
}

const NAV_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'ダッシュボード' },
  { key: '/tasks', icon: <CheckSquareOutlined />, label: 'タスク一覧' },
  { key: '/projects', icon: <ProjectOutlined />, label: 'プロジェクト' },
  { key: '/board', icon: <AppstoreOutlined />, label: 'カンバン' },
  { key: '/calendar', icon: <ScheduleOutlined />, label: 'カレンダー' },
  { key: '/gantt', icon: <BarChartOutlined />, label: 'ガント' },
  { key: '/schedule', icon: <CalendarOutlined />, label: 'スケジュール' },
  { key: '/workload', icon: <TeamOutlined />, label: 'ワークロード' },
  { key: '/import', icon: <UploadOutlined />, label: 'データインポート' },
]

function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedKey =
    NAV_ITEMS.find((item) => item.key !== '/' && location.pathname.startsWith(item.key))?.key ??
    '/'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ color: 'white', fontSize: 18, padding: '0 24px' }}>AutoTicket</Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            style={{ height: '100%', borderRight: 0 }}
            items={NAV_ITEMS}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tasks" element={<TaskList />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/projects" element={<ProjectList />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/board" element={<Board />} />
            <Route path="/calendar" element={<CalendarView />} />
            <Route path="/gantt" element={<GanttView />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/workload" element={<Workload />} />
            <Route path="/import" element={<ImportPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

export default function App() {
  const isAuthenticated = useIsAuthenticated()
  if (!isAuthenticated) return <LoginPage />
  return <AppLayout />
}
```

- [ ] **Step 5: TypeScript チェック**

```powershell
npx tsc -b --noEmit
```

Expected: エラー 0（スタブページとインポートが整合していること）

- [ ] **Step 6: コミット**

```bash
git add frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/pages/Board/index.tsx frontend/src/pages/Calendar/index.tsx frontend/src/pages/Gantt/index.tsx
git commit -m "feat: add board/calendar/gantt stubs, update App.tsx routing and api.ts types"
```

---

## Task 3: useTasksForView + useReschedule + useUsers フック

**Files:**
- Create: `frontend/src/hooks/useTasksForView.ts`
- Create: `frontend/src/hooks/useReschedule.ts`

- [ ] **Step 1: useTasksForView.ts を作成**

`frontend/src/hooks/useTasksForView.ts`:

```typescript
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import type { Task, TaskListResponse, UserProfile } from '../lib/api'

interface ViewFilters {
  due_date_gte?: string
  due_date_lte?: string
  project_id?: string
  assignee_ids?: string[]
  status?: string
  limit?: number
}

export function useTasksForView(filters: ViewFilters) {
  return useQuery<Task[]>({
    queryKey: ['tasks-view', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.due_date_gte) params.set('due_date_gte', filters.due_date_gte)
      if (filters.due_date_lte) params.set('due_date_lte', filters.due_date_lte)
      if (filters.project_id) params.set('project_id', filters.project_id)
      if (filters.status) params.set('status', filters.status)
      params.set('limit', String(filters.limit ?? 200))
      filters.assignee_ids?.forEach((id) => params.append('assignee_ids', id))
      const res = await api.get<TaskListResponse>(`/tasks?${params}`)
      return res.data.items
    },
  })
}

export function useUsers() {
  return useQuery<UserProfile[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await api.get<UserProfile[]>('/users')
      return res.data
    },
  })
}
```

- [ ] **Step 2: useReschedule.ts を作成**

`frontend/src/hooks/useReschedule.ts`:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import type { RescheduleRequest, RescheduleResponse } from '../lib/api'

export function useReschedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ taskId, body }: { taskId: string; body: RescheduleRequest }) => {
      const res = await api.post<RescheduleResponse>(`/tasks/${taskId}/reschedule`, body)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks-view'] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
```

- [ ] **Step 3: TypeScript チェック**

```powershell
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npx tsc -b --noEmit
```

Expected: エラー 0

- [ ] **Step 4: コミット**

```bash
git add frontend/src/hooks/useTasksForView.ts frontend/src/hooks/useReschedule.ts
git commit -m "feat: add useTasksForView, useReschedule, useUsers hooks"
```

---

## Task 4: カンバンビュー（/board）

**Files:**
- Modify: `frontend/src/pages/Board/index.tsx`

- [ ] **Step 1: カンバンビューを実装する**

`frontend/src/pages/Board/index.tsx` を以下に置き換え:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { Card, Select, Space, Spin, Tag, Typography } from 'antd'
import { useProjects } from '../../hooks/useProjects'
import { useSections } from '../../hooks/useSections'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useUpdateTask } from '../../hooks/useTasks'
import type { Task } from '../../lib/api'

const { Title } = Typography

const STATUS_COLUMNS = [
  { key: 'not_started', label: '未着手', color: '#d9d9d9' },
  { key: 'in_progress', label: '進行中', color: '#1677ff' },
  { key: 'completed', label: '完了', color: '#52c41a' },
  { key: 'cancelled', label: 'キャンセル', color: '#ff4d4f' },
]

const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'red',
  high: 'orange',
  medium: 'blue',
  low: 'default',
}

function TaskCard({ task }: { task: Task }) {
  const navigate = useNavigate()
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined,
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
        onClick={() => !isDragging && navigate(`/tasks/${task.id}`)}
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

function KanbanColumn({
  colKey,
  label,
  color,
  tasks,
}: {
  colKey: string
  label: string
  color: string
  tasks: Task[]
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
      {tasks.map((task) => (
        <TaskCard key={task.id} task={task} />
      ))}
    </div>
  )
}

export default function Board() {
  const [projectId, setProjectId] = useState<string | undefined>()
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const { data: projects = [] } = useProjects()
  const { data: sections = [] } = useSections(projectId)
  const { data: tasks = [], isLoading } = useTasksForView({ project_id: projectId })
  const updateTask = useUpdateTask()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const usingSections = !!(projectId && sections.length > 0)
  const columns = usingSections
    ? sections.map((s) => ({ key: s.id, label: s.name, color: '#1677ff' }))
    : STATUS_COLUMNS

  const getColumnTasks = (colKey: string) =>
    usingSections
      ? tasks.filter((t) => t.section_id === colKey)
      : tasks.filter((t) => t.status === colKey)

  const handleDragStart = ({ active }: DragStartEvent) => {
    setActiveTask(tasks.find((t) => t.id === active.id) ?? null)
  }

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveTask(null)
    if (!over) return
    const overColKey = columns.find((c) => c.key === String(over.id))?.key
    if (!overColKey) return
    const patch = usingSections
      ? { id: String(active.id), section_id: overColKey }
      : { id: String(active.id), status: overColKey }
    updateTask.mutate(patch)
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space align="center">
        <Title level={3} style={{ margin: 0 }}>
          カンバン
        </Title>
        <Select
          allowClear
          placeholder="プロジェクト（任意）"
          style={{ width: 240 }}
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          onChange={(v) => setProjectId(v)}
        />
      </Space>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 16 }}>
            {columns.map((col) => (
              <KanbanColumn
                key={col.key}
                colKey={col.key}
                label={col.label}
                color={col.color}
                tasks={getColumnTasks(col.key)}
              />
            ))}
          </div>
          <DragOverlay>
            {activeTask && (
              <Card
                size="small"
                style={{ width: 240, opacity: 0.9, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
              >
                <div style={{ fontWeight: 500 }}>{activeTask.title}</div>
              </Card>
            )}
          </DragOverlay>
        </DndContext>
      )}
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript チェック**

```powershell
npx tsc -b --noEmit
```

Expected: エラー 0

- [ ] **Step 3: コミット**

```bash
git add frontend/src/pages/Board/index.tsx
git commit -m "feat: implement Kanban board with dnd-kit drag-and-drop"
```

---

## Task 5: カレンダービュー（/calendar）

**Files:**
- Modify: `frontend/src/pages/Calendar/index.tsx`

- [ ] **Step 1: カレンダービューを実装する**

`frontend/src/pages/Calendar/index.tsx` を以下に置き換え:

```tsx
import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, dateFnsLocalizer } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay, startOfMonth, endOfMonth, parseISO } from 'date-fns'
import { ja } from 'date-fns/locale/ja'
import { Select, Space, Typography } from 'antd'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { useTasksForView, useUsers } from '../../hooks/useTasksForView'
import { useProjects } from '../../hooks/useProjects'
import type { Task } from '../../lib/api'

const { Title } = Typography

const locales = { ja }
const localizer = dateFnsLocalizer({ format, parse, startOfWeek, getDay, locales })

const RBC_MESSAGES = {
  next: '次',
  previous: '前',
  today: '今日',
  month: '月',
  week: '週',
  day: '日',
  noEventsInRange: 'この期間にタスクはありません',
}

interface CalEvent {
  id: string
  title: string
  start: Date
  end: Date
  allDay: boolean
  resource: Task
}

function assigneeColor(userId: string | null): string {
  if (!userId) return '#1677ff'
  let hash = 0
  for (let i = 0; i < userId.length; i++) {
    hash = userId.charCodeAt(i) + ((hash << 5) - hash)
  }
  return `hsl(${Math.abs(hash) % 360}, 65%, 50%)`
}

export default function CalendarView() {
  const navigate = useNavigate()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [projectId, setProjectId] = useState<string | undefined>()
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])

  const { data: projects = [] } = useProjects()
  const { data: users = [] } = useUsers()

  const monthStart = startOfMonth(currentDate)
  const monthEnd = endOfMonth(currentDate)

  const { data: tasks = [] } = useTasksForView({
    due_date_gte: format(monthStart, 'yyyy-MM-dd'),
    due_date_lte: format(monthEnd, 'yyyy-MM-dd'),
    project_id: projectId,
    assignee_ids: assigneeIds.length > 0 ? assigneeIds : undefined,
  })

  const events = useMemo<CalEvent[]>(() => {
    return tasks.map((task) => {
      const end = task.due_date ? parseISO(task.due_date) : new Date()
      const start = task.start_date ? parseISO(task.start_date) : end
      return { id: task.id, title: task.title, start, end, allDay: true, resource: task }
    })
  }, [tasks])

  const taskCountByDate = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const task of tasks) {
      if (task.due_date) counts[task.due_date] = (counts[task.due_date] ?? 0) + 1
    }
    return counts
  }, [tasks])

  const DensityCellWrapper = useCallback(
    ({ value, children }: { value: Date; children: React.ReactNode }) => {
      const key = format(value, 'yyyy-MM-dd')
      const count = taskCountByDate[key] ?? 0
      const bg =
        count === 0 ? undefined
        : count <= 2 ? '#e6f4ff'
        : count <= 5 ? '#91caff'
        : 'rgba(22, 119, 255, 0.15)'
      return <div style={{ flex: 1, minHeight: 'inherit', background: bg }}>{children}</div>
    },
    [taskCountByDate]
  )

  const eventPropGetter = useCallback(
    (event: object) => {
      const ev = event as CalEvent
      return { style: { backgroundColor: assigneeColor(ev.resource.assignee_id ?? null) } }
    },
    []
  )

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space align="center" wrap>
        <Title level={3} style={{ margin: 0 }}>
          カレンダー
        </Title>
        <Select
          allowClear
          placeholder="プロジェクト（任意）"
          style={{ width: 200 }}
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          onChange={(v) => setProjectId(v)}
        />
        <Select
          mode="multiple"
          allowClear
          placeholder="担当者（未選択: 全員）"
          style={{ minWidth: 240 }}
          options={users.map((u) => ({ value: u.user_id, label: u.display_name }))}
          onChange={(v: string[]) => setAssigneeIds(v)}
        />
      </Space>

      <Calendar
        localizer={localizer}
        events={events}
        views={['month']}
        defaultView="month"
        date={currentDate}
        onNavigate={setCurrentDate}
        style={{ height: 620 }}
        eventPropGetter={eventPropGetter as Parameters<typeof Calendar>[0]['eventPropGetter']}
        onSelectEvent={(event) => navigate(`/tasks/${(event as CalEvent).id}`)}
        messages={RBC_MESSAGES}
        components={{ dateCellWrapper: DensityCellWrapper as Parameters<typeof Calendar>[0]['components'] extends { dateCellWrapper?: infer T } ? T : never }}
      />
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript チェック**

```powershell
npx tsc -b --noEmit
```

Expected: エラー 0。`eventPropGetter` や `dateCellWrapper` の型エラーが出た場合は `as any` で回避して構わない（react-big-calendar の型定義が厳密でないため）。具体的には:

```tsx
// 型エラーが出る場合の回避策
eventPropGetter={eventPropGetter as any}
components={{ dateCellWrapper: DensityCellWrapper as any }}
```

- [ ] **Step 3: コミット**

```bash
git add frontend/src/pages/Calendar/index.tsx
git commit -m "feat: implement calendar view with density heatmap and assignee filter"
```

---

## Task 6: ガントチャート（/gantt）

**Files:**
- Modify: `frontend/src/pages/Gantt/index.tsx`

- [ ] **Step 1: ガントチャートを実装する**

`frontend/src/pages/Gantt/index.tsx` を以下に置き換え:

```tsx
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Gantt, ViewMode } from 'gantt-task-react'
import type { Task as GanttTask } from 'gantt-task-react'
import 'gantt-task-react/dist/index.css'
import { Alert, Button, Modal, Select, Space, Spin, Typography } from 'antd'
import { useProjects } from '../../hooks/useProjects'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useReschedule } from '../../hooks/useReschedule'
import { useUpdateTask } from '../../hooks/useTasks'
import api from '../../lib/api'
import type { DependencyResponse, Task } from '../../lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const { Title } = Typography

function toGanttTask(task: Task, depMap: Record<string, string[]>): GanttTask {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const end = task.due_date ? new Date(task.due_date) : new Date(today.getTime() + 86400000)
  const start = task.start_date ? new Date(task.start_date) : end
  const progress =
    task.status === 'completed' ? 100
    : task.status === 'in_progress' ? 50
    : 0
  return {
    id: task.id,
    name: task.title,
    start,
    end,
    progress,
    type: 'task',
    dependencies: depMap[task.id] ?? [],
    isDisabled: false,
  }
}

export default function GanttView() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState<string | undefined>()
  const [addDepTarget, setAddDepTarget] = useState<string | null>(null)
  const [addDepModal, setAddDepModal] = useState(false)
  const [selectedDepId, setSelectedDepId] = useState<string | undefined>()

  const { data: projects = [] } = useProjects()
  const { data: tasks = [], isLoading } = useTasksForView({
    project_id: projectId,
    limit: 200,
  })
  const reschedule = useReschedule()
  const updateTask = useUpdateTask()

  // 依存関係を並列取得
  const { data: depMap = {} } = useQuery<Record<string, string[]>>({
    queryKey: ['gantt-deps', projectId, tasks.map((t) => t.id).join(',')],
    enabled: tasks.length > 0 && !!projectId,
    queryFn: async () => {
      const results = await Promise.all(
        tasks.map((t) =>
          api
            .get<DependencyResponse[]>(`/tasks/${t.id}/dependencies`)
            .then((r) => ({ taskId: t.id, deps: r.data }))
        )
      )
      const map: Record<string, string[]> = {}
      for (const { taskId, deps } of results) {
        map[taskId] = deps.map((d) => d.depends_on_task_id)
      }
      return map
    },
  })

  // 依存関係追加
  const addDep = useMutation({
    mutationFn: async ({ taskId, dependsOn }: { taskId: string; dependsOn: string }) => {
      await api.post(`/tasks/${taskId}/dependencies`, { depends_on_task_id: dependsOn })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gantt-deps'] })
      setAddDepModal(false)
      setSelectedDepId(undefined)
    },
  })

  // 依存関係削除
  const removeDep = useMutation({
    mutationFn: async ({ taskId, depId }: { taskId: string; depId: string }) => {
      await api.delete(`/tasks/${taskId}/dependencies/${depId}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gantt-deps'] }),
  })

  const ganttTasks = useMemo(
    () => tasks.map((t) => toGanttTask(t, depMap)),
    [tasks, depMap]
  )

  const handleDateChange = (ganttTask: GanttTask) => {
    const task = tasks.find((t) => t.id === ganttTask.id)
    if (!task) return
    const newStart = ganttTask.start.toISOString().slice(0, 10)
    const newEnd = ganttTask.end.toISOString().slice(0, 10)
    reschedule.mutate({
      taskId: ganttTask.id,
      body: { new_start_date: newStart, new_due_date: newEnd },
    })
  }

  if (!projectId) {
    return (
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Space align="center">
          <Title level={3} style={{ margin: 0 }}>ガント</Title>
          <Select
            placeholder="プロジェクトを選択してください"
            style={{ width: 300 }}
            options={projects.map((p) => ({ value: p.id, label: p.name }))}
            onChange={(v) => setProjectId(v)}
          />
        </Space>
        <Alert message="ガントを表示するにはプロジェクトを選択してください" type="info" showIcon />
      </Space>
    )
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space align="center" wrap>
        <Title level={3} style={{ margin: 0 }}>ガント</Title>
        <Select
          value={projectId}
          style={{ width: 240 }}
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          onChange={(v) => setProjectId(v)}
        />
      </Space>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : ganttTasks.length === 0 ? (
        <Alert message="このプロジェクトにタスクがありません" type="info" showIcon />
      ) : (
        <>
          <Gantt
            tasks={ganttTasks}
            viewMode={ViewMode.Day}
            onDateChange={handleDateChange}
            onDoubleClick={(task) => navigate(`/tasks/${task.id}`)}
            columnWidth={65}
            listCellWidth="200px"
            locale="ja"
          />
          <Space wrap>
            <Button
              onClick={() => {
                if (ganttTasks[0]) {
                  setAddDepTarget(ganttTasks[0].id)
                  setAddDepModal(true)
                }
              }}
              disabled={ganttTasks.length === 0}
            >
              依存関係を追加
            </Button>
          </Space>
        </>
      )}

      <Modal
        title="依存関係を追加"
        open={addDepModal}
        onOk={() => {
          if (addDepTarget && selectedDepId) {
            addDep.mutate({ taskId: addDepTarget, dependsOn: selectedDepId })
          }
        }}
        onCancel={() => {
          setAddDepModal(false)
          setSelectedDepId(undefined)
        }}
        okText="追加"
        cancelText="キャンセル"
        confirmLoading={addDep.isPending}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="依存元タスク（このタスクが完了後に開始）"
            style={{ width: '100%' }}
            options={tasks.map((t) => ({ value: t.id, label: t.title }))}
            value={addDepTarget ?? undefined}
            onChange={setAddDepTarget}
          />
          <Select
            placeholder="依存先タスク（depends_on）"
            style={{ width: '100%' }}
            options={tasks
              .filter((t) => t.id !== addDepTarget)
              .map((t) => ({ value: t.id, label: t.title }))}
            value={selectedDepId}
            onChange={setSelectedDepId}
          />
        </Space>
      </Modal>
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript チェック**

```powershell
npx tsc -b --noEmit
```

Expected: エラー 0。`gantt-task-react` の型定義に関するエラーが出た場合は `@ts-expect-error` コメントまたは `as any` で回避する。

- [ ] **Step 3: 全バックエンドテスト実行**

```powershell
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket"
.venv\Scripts\python -m pytest tests/unit/ -q
```

Expected: 118 passed 以上（Task 1 で 4 件追加）

- [ ] **Step 4: docs/tasks.md を更新**

`docs/tasks.md` の Phase 2B セクションを以下に更新:

```markdown
## Web App Phase 2B-1: マルチビュー ✅ 完了（2026-05-19）

- [x] **バックエンド API 拡張**: due_date_gte/lte・assignee_ids フィルタ・reschedule エンドポイント
- [x] **カンバンビュー** (`/board`): ステータス 4 列・dnd-kit D&D・プロジェクトセクション切り替え
- [x] **カレンダービュー** (`/calendar`): 月次・担当者フィルタ・密度ヒートマップ
- [x] **ガントチャート** (`/gantt`): gantt-task-react・バー D&D・依存関係矢印・F-36 自動リスケジュール
```

- [ ] **Step 5: コミット**

```bash
git add frontend/src/pages/Gantt/index.tsx docs/tasks.md
git commit -m "feat: implement Gantt chart with dependency arrows and F-36 auto-reschedule"
```

---

## 全体チェックリスト（完了後確認）

- [ ] バックエンドテスト: `pytest tests/unit/ -q` → 118 passed 以上
- [ ] TypeScript: `cd frontend && npx tsc -b --noEmit` → エラー 0
- [ ] `/board` → カンバン表示、D&D でカラム移動できること
- [ ] `/calendar` → 月次カレンダー、タスクが期間バーまたは点で表示されること
- [ ] `/gantt` → プロジェクト選択後にタスクバーが表示、バー移動で日程が変わること
- [ ] サイドバーに カンバン・カレンダー・ガント が表示されていること

---

## 型整合性チェック（自己レビュー）

- `Task.start_date?: string | null` → `parseISO(task.start_date)` で Date に変換（Calendar・Gantt）
- `GanttTask.end` は `Date` 型。文字列の `due_date` を `new Date(task.due_date)` で変換
- `RescheduleRequest.new_due_date` は `string`（ISO date 形式）。`ganttTask.end.toISOString().slice(0, 10)`
- `useUpdateTask().mutate({ id: string, status?: string, section_id?: string })` → 既存のシグネチャと合致
- `depMap[taskId]` は `string[]`（depends_on_task_id の配列）→ `GanttTask.dependencies` と合致
