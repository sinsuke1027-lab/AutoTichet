# プロジェクトアーカイブ機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** プロジェクトをアーカイブして一覧・タスク一覧から非表示にし、復元もできるようにする

**Architecture:** 既存の `Project.status` 列を利用（`"archived"` 値）してスキーマ変更なしに実装。バックエンドに `PATCH /archive` / `/unarchive` エンドポイントと `include_archived` クエリパラメータを追加。フロントエンドにはプロジェクトカードの Dropdown メニューと Switch フィルタを追加する。

**Tech Stack:** FastAPI, SQLAlchemy 2.x (async), React 18, Ant Design 5.x, TanStack Query 5.x

---

## ファイル構成

| 種別 | ファイル | 変更内容 |
|------|---------|---------|
| Create | `tests/unit/test_project_archive.py` | archive/unarchive テスト 8 件 |
| Modify | `src/api/routers/projects.py` | PATCH /archive・/unarchive 追加、GET に include_archived 追加 |
| Modify | `src/api/routers/tasks_crud.py` | list_tasks に include_archived_projects フィルタ追加 |
| Modify | `frontend/src/lib/api.ts` | archiveProject / unarchiveProject 関数追加 |
| Modify | `frontend/src/hooks/useProjects.ts` | useProjects 更新・useArchiveProject / useUnarchiveProject 追加 |
| Modify | `frontend/src/hooks/useTasks.ts` | TaskFilters に include_archived_projects 追加 |
| Modify | `frontend/src/pages/Projects/List.tsx` | Dropdown・Switch・グレーアウト追加 |
| Modify | `frontend/src/pages/Tasks/index.tsx` | Switch 追加 |

---

## Task 1: バックエンド — archive/unarchive エンドポイント + list フィルタ

**Files:**
- Create: `tests/unit/test_project_archive.py`
- Modify: `src/api/routers/projects.py`

- [ ] **Step 1: テストファイルを作成する（失敗することを確認）**

`tests/unit/test_project_archive.py` を以下の内容で作成する。

```python
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.projects import router
from src.db.engine import get_db

_creator = TokenPayload(
    sub="creator-1", name="Creator", email="c@t.com", roles=["member"], tid="tid"
)
_other_member = TokenPayload(
    sub="other-1", name="Other", email="o@t.com", roles=["member"], tid="tid"
)
_leader = TokenPayload(
    sub="leader-1", name="Leader", email="l@t.com", roles=["leader"], tid="tid"
)


def _make_project(*, created_by: str = "creator-1", status: str = "active") -> MagicMock:
    from src.db.models import Project

    p = MagicMock(spec=Project)
    p.id = uuid.uuid4()
    p.name = "テストプロジェクト"
    p.description = None
    p.status = status
    p.created_by = created_by
    p.created_at = datetime(2026, 1, 1)
    p.updated_at = datetime(2026, 1, 1)
    return p


def _make_db(project: MagicMock | None) -> AsyncMock:
    """archive/unarchive エンドポイント用 DB モック（scalar_one_or_none）"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = project
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _make_list_db(projects: list) -> AsyncMock:
    """list_projects 用 DB モック（scalars().all()）"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = projects
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _make_client(user: TokenPayload, db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_archive_by_creator_returns_200() -> None:
    """作成者がアーカイブ → status が archived に変わり 200"""
    project = _make_project(created_by="creator-1")
    client = _make_client(_creator, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/archive")
    assert resp.status_code == 200
    assert project.status == "archived"


def test_unarchive_by_creator_returns_200() -> None:
    """作成者がアーカイブ解除 → status が active に戻り 200"""
    project = _make_project(created_by="creator-1", status="archived")
    client = _make_client(_creator, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/unarchive")
    assert resp.status_code == 200
    assert project.status == "active"


def test_archive_by_non_creator_member_returns_403() -> None:
    """非作成者の member がアーカイブ → 403"""
    project = _make_project(created_by="creator-1")
    client = _make_client(_other_member, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/archive")
    assert resp.status_code == 403


def test_archive_by_leader_returns_200() -> None:
    """leader が他人のプロジェクトをアーカイブ → 200"""
    project = _make_project(created_by="creator-1")
    client = _make_client(_leader, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/archive")
    assert resp.status_code == 200


def test_archive_not_found_returns_404() -> None:
    """存在しないプロジェクトをアーカイブ → 404"""
    client = _make_client(_creator, _make_db(None))
    resp = client.patch(f"/api/v1/projects/{uuid.uuid4()}/archive")
    assert resp.status_code == 404


def test_list_projects_default_excludes_archived() -> None:
    """GET /projects（デフォルト）→ 200（アーカイブ済みは含まない想定でモック）"""
    active_project = _make_project(status="active")
    client = _make_client(_creator, _make_list_db([active_project]))
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_projects_include_archived_true() -> None:
    """GET /projects?include_archived=true → 200（アーカイブ済みも含む想定でモック）"""
    active_project = _make_project(status="active")
    archived_project = _make_project(status="archived")
    client = _make_client(_creator, _make_list_db([active_project, archived_project]))
    resp = client.get("/api/v1/projects?include_archived=true")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_unarchive_by_non_creator_member_returns_403() -> None:
    """非作成者の member がアーカイブ解除 → 403"""
    project = _make_project(created_by="creator-1", status="archived")
    client = _make_client(_other_member, _make_db(project))
    resp = client.patch(f"/api/v1/projects/{project.id}/unarchive")
    assert resp.status_code == 403
```

- [ ] **Step 2: テストが失敗することを確認する**

```
pytest tests/unit/test_project_archive.py -v
```

期待: FAIL（エンドポイントが存在しないため 404 / AttributeError）

- [ ] **Step 3: `src/api/routers/projects.py` を実装する**

既存ファイルを以下に全置き換えする。

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser, require_role
from src.db.engine import get_db
from src.db.models import Project
from src.models.task_web import ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class _ProjectCreate(ProjectUpdate):
    """リクエストボディ用モデル。created_by はサーバー側でセットするため除外。"""

    name: str


def _check_project_permission(project: Project, current_user: CurrentUser) -> None:
    """作成者または leader 以上でなければ 403 を発生させる。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if project.created_by != current_user.sub and user_role < ROLE_HIERARCHY["leader"]:
        raise HTTPException(
            status_code=403, detail="このプロジェクトを操作する権限がありません"
        )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: DbDep,
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
) -> list[ProjectResponse]:
    query = select(Project).order_by(Project.created_at.desc())
    if not include_archived:
        query = query.where(Project.status != "archived")
    result = await db.execute(query)
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: _ProjectCreate, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    project = Project(
        name=body.name,
        description=body.description,
        status=body.status or "active",
        created_by=current_user.sub,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    _check_project_permission(project, current_user)
    project.status = "archived"
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}/unarchive", response_model=ProjectResponse)
async def unarchive_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    _check_project_permission(project, current_user)
    project.status = "active"
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: DbDep,
    current_user: Annotated[CurrentUser, Depends(require_role("leader"))],
) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    await db.delete(project)
    await db.commit()
```

- [ ] **Step 4: テストが通ることを確認する**

```
pytest tests/unit/test_project_archive.py -v
```

期待: 8 passed

- [ ] **Step 5: 全テストが通ることを確認する**

```
pytest tests/ -v --tb=short -q
```

期待: 全テスト passed（既存テストが壊れていないこと）

- [ ] **Step 6: コミットする**

```bash
git add tests/unit/test_project_archive.py src/api/routers/projects.py
git commit -m "feat: プロジェクト archive/unarchive エンドポイント追加・list に include_archived フィルタ追加"
```

---

## Task 2: バックエンド — タスク一覧からアーカイブ済みプロジェクトのタスクを除外

**Files:**
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: インポート行に `Project` を追加する**

`src/api/routers/tasks_crud.py` の17行目を変更する。

変更前:
```python
from src.db.models import Task, TaskAssignee, TaskDependency, TaskTag, TaskWorkHour, UserProfile
```

変更後:
```python
from src.db.models import Project, Task, TaskAssignee, TaskDependency, TaskTag, TaskWorkHour, UserProfile
```

- [ ] **Step 2: `list_tasks` 関数シグネチャに `include_archived_projects` を追加する**

`list_tasks` 関数（`@router.get("", ...)` の下）のパラメータリストに追加する。

変更前（`my_tasks_only` の行）:
```python
    my_tasks_only: bool = Query(default=False),
) -> TaskListResponse:
```

変更後:
```python
    my_tasks_only: bool = Query(default=False),
    include_archived_projects: bool = Query(default=False),
) -> TaskListResponse:
```

- [ ] **Step 3: アーカイブフィルタを `count_result` の直前に追加する**

`# manager / admin はフィルタなし（全件）` のコメントの直後（`count_result = ...` の直前）に以下を追加する。

```python
    # アーカイブ済みプロジェクトのタスクを除外（project_id=None の個人 ToDo は対象外）
    if not include_archived_projects:
        query = query.outerjoin(Project, Task.project_id == Project.id).where(
            or_(Task.project_id.is_(None), Project.status != "archived")
        )
```

- [ ] **Step 4: 全テストが通ることを確認する**

```
pytest tests/ -v --tb=short -q
```

期待: 全テスト passed

- [ ] **Step 5: コミットする**

```bash
git add src/api/routers/tasks_crud.py
git commit -m "feat: タスク一覧にアーカイブ済みプロジェクトを除外するフィルタを追加"
```

---

## Task 3: フロントエンド — api.ts・useProjects.ts・useTasks.ts 更新

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useProjects.ts`
- Modify: `frontend/src/hooks/useTasks.ts`

- [ ] **Step 1: `frontend/src/lib/api.ts` に archive/unarchive 関数を追加する**

`api.ts` のファイル末尾（`export default api` より後ろ）に追加する。既存の `export interface Project { ... }` ブロックは変更しない。
ファイルに `generateHandover` などの関数が既にエクスポートされているので、同じパターンで追記する。

```typescript
export async function archiveProject(id: string): Promise<Project> {
  const { data } = await api.patch<Project>(`/projects/${id}/archive`)
  return data
}

export async function unarchiveProject(id: string): Promise<Project> {
  const { data } = await api.patch<Project>(`/projects/${id}/unarchive`)
  return data
}
```

- [ ] **Step 2: `frontend/src/hooks/useProjects.ts` を以下に全置き換えする**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { type Project, archiveProject, unarchiveProject } from '../lib/api'

export function useProjects(includeArchived = false) {
  return useQuery<Project[]>({
    queryKey: ['projects', { includeArchived }],
    queryFn: async () => {
      const { data } = await api.get('/projects', {
        params: includeArchived ? { include_archived: true } : {},
      })
      return data
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const { data } = await api.post('/projects', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useArchiveProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => archiveProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useUnarchiveProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => unarchiveProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
```

- [ ] **Step 3: `frontend/src/hooks/useTasks.ts` の `TaskFilters` に `include_archived_projects` を追加する**

変更前:
```typescript
interface TaskFilters {
  status?: string
  assignee?: string
  project_id?: string
  section_id?: string
  q?: string
  tag?: string
  limit?: number
  offset?: number
  my_tasks_only?: boolean
}
```

変更後:
```typescript
interface TaskFilters {
  status?: string
  assignee?: string
  project_id?: string
  section_id?: string
  q?: string
  tag?: string
  limit?: number
  offset?: number
  my_tasks_only?: boolean
  include_archived_projects?: boolean
}
```

- [ ] **Step 4: TypeScript チェックを通す**

```
cd frontend && npx tsc --noEmit
```

期待: エラーなし

- [ ] **Step 5: コミットする**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useProjects.ts frontend/src/hooks/useTasks.ts
git commit -m "feat: archive/unarchive フック追加・TaskFilters に include_archived_projects 追加"
```

---

## Task 4: フロントエンド — Projects/List.tsx UI 更新

**Files:**
- Modify: `frontend/src/pages/Projects/List.tsx`

- [ ] **Step 1: `frontend/src/pages/Projects/List.tsx` を以下に全置き換えする**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Col,
  Dropdown,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd'
import { EllipsisOutlined, PlusOutlined } from '@ant-design/icons'
import {
  useProjects,
  useCreateProject,
  useArchiveProject,
  useUnarchiveProject,
} from '../../hooks/useProjects'

export default function ProjectList() {
  const navigate = useNavigate()
  const [includeArchived, setIncludeArchived] = useState(false)
  const { data: projects = [], isLoading } = useProjects(includeArchived)
  const createProject = useCreateProject()
  const archiveProject = useArchiveProject()
  const unarchiveProject = useUnarchiveProject()
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await createProject.mutateAsync(values)
      form.resetFields()
      setOpen(false)
    } catch {
      // validation error — do nothing
    }
  }

  const handleArchive = async (id: string) => {
    try {
      await archiveProject.mutateAsync(id)
      void message.success('アーカイブしました')
    } catch {
      void message.error('アーカイブに失敗しました')
    }
  }

  const handleUnarchive = async (id: string) => {
    try {
      await unarchiveProject.mutateAsync(id)
      void message.success('アーカイブを解除しました')
    } catch {
      void message.error('アーカイブ解除に失敗しました')
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          プロジェクト一覧
        </Typography.Title>
        <Space>
          <Switch checked={includeArchived} onChange={setIncludeArchived} />
          <Typography.Text>アーカイブ済みを表示</Typography.Text>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            プロジェクト作成
          </Button>
        </Space>
      </Space>

      {isLoading ? (
        <Typography.Text>読み込み中...</Typography.Text>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((p) => {
            const isArchived = p.status === 'archived'
            return (
              <Col key={p.id} xs={24} sm={12} lg={8}>
                <Card
                  hoverable={!isArchived}
                  onClick={() => !isArchived && navigate(`/projects/${p.id}`)}
                  style={isArchived ? { opacity: 0.5, cursor: 'default' } : undefined}
                  title={p.name}
                  extra={
                    <Space>
                      <Tag color={isArchived ? 'default' : 'green'}>
                        {isArchived ? 'アーカイブ済み' : 'active'}
                      </Tag>
                      <Dropdown
                        menu={{
                          items: isArchived
                            ? [{ key: 'unarchive', label: 'アーカイブ解除' }]
                            : [{ key: 'archive', label: 'アーカイブ' }],
                          onClick: ({ key, domEvent }) => {
                            domEvent.stopPropagation()
                            if (key === 'archive') void handleArchive(p.id)
                            else void handleUnarchive(p.id)
                          },
                        }}
                        trigger={['click']}
                      >
                        <Button
                          type="text"
                          icon={<EllipsisOutlined />}
                          size="small"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Dropdown>
                    </Space>
                  }
                >
                  <Typography.Text type="secondary">
                    {p.description ?? '説明なし'}
                  </Typography.Text>
                </Card>
              </Col>
            )
          })}
          {projects.length === 0 && (
            <Col span={24}>
              <Typography.Text type="secondary">プロジェクトがありません</Typography.Text>
            </Col>
          )}
        </Row>
      )}

      <Modal
        title="プロジェクト作成"
        open={open}
        onOk={handleCreate}
        onCancel={() => {
          setOpen(false)
          form.resetFields()
        }}
        confirmLoading={createProject.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="プロジェクト名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="説明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript チェックを通す**

```
cd frontend && npx tsc --noEmit
```

期待: エラーなし

- [ ] **Step 3: コミットする**

```bash
git add frontend/src/pages/Projects/List.tsx
git commit -m "feat: プロジェクト一覧に archive/unarchive ボタンと Switch フィルタ追加"
```

---

## Task 5: フロントエンド — Tasks/index.tsx にアーカイブ済みプロジェクト Switch 追加

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: `includeArchivedProjects` state を追加する**

`Tasks/index.tsx` の既存 `useState` 群（`myTasksOnly` の直下）に追加する。

変更前:
```tsx
  const [myTasksOnly, setMyTasksOnly] = useState(false)
```

変更後:
```tsx
  const [myTasksOnly, setMyTasksOnly] = useState(false)
  const [includeArchivedProjects, setIncludeArchivedProjects] = useState(false)
```

- [ ] **Step 2: `useTasks` の呼び出しにパラメータを追加する**

変更前:
```tsx
  const { data: taskList, isLoading } = useTasks({
    status: statusFilter || undefined,
    assignee: assigneeFilter,
    project_id: projectFilter,
    section_id: sectionFilter,
    q: searchQ || undefined,
    my_tasks_only: myTasksOnly || undefined,
  })
```

変更後:
```tsx
  const { data: taskList, isLoading } = useTasks({
    status: statusFilter || undefined,
    assignee: assigneeFilter,
    project_id: projectFilter,
    section_id: sectionFilter,
    q: searchQ || undefined,
    my_tasks_only: myTasksOnly || undefined,
    include_archived_projects: includeArchivedProjects || undefined,
  })
```

- [ ] **Step 3: フィルター行に Switch を追加する**

`Tasks/index.tsx` のフィルター `<Space wrap>` 内、「自分の ToDo のみ」Switch の直下に追加する。

変更前:
```tsx
        <Space>
          <Switch
            checked={myTasksOnly}
            onChange={(v) => {
              setMyTasksOnly(v)
              if (v) setAssigneeFilter(undefined)
            }}
          />
          <span>自分の ToDo のみ</span>
        </Space>
```

変更後:
```tsx
        <Space>
          <Switch
            checked={myTasksOnly}
            onChange={(v) => {
              setMyTasksOnly(v)
              if (v) setAssigneeFilter(undefined)
            }}
          />
          <span>自分の ToDo のみ</span>
        </Space>
        <Space>
          <Switch
            checked={includeArchivedProjects}
            onChange={setIncludeArchivedProjects}
          />
          <span>アーカイブ済みプロジェクトを含む</span>
        </Space>
```

- [ ] **Step 4: TypeScript チェックとビルドを通す**

```
cd frontend && npx tsc --noEmit && npm run build
```

期待: エラーなし・ビルド成功

- [ ] **Step 5: 全バックエンドテストを通す**

```
pytest tests/ -v --tb=short -q
```

期待: 全テスト passed

- [ ] **Step 6: コミットする**

```bash
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: タスク一覧にアーカイブ済みプロジェクト含む Switch 追加"
```
