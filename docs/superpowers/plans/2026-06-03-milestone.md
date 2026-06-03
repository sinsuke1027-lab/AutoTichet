# マイルストーン設定 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** プロジェクト詳細ページに横軸タイムラインでマイルストーンを表示し、作成・編集・削除・手動完了マークができる機能を追加する。

**Architecture:** 既存の `milestones` テーブル（初期スキーマで作成済み）に `completed`/`completed_at` を追加する Alembic 0008 マイグレーションを適用し、新規ルーター `milestones.py` で CRUD + 完了トグルの5エンドポイントを提供する。フロントエンドは新規コンポーネント `MilestoneTimeline.tsx` をプロジェクト詳細ページのセクション上部に追加する。

**Tech Stack:** React 18 + TypeScript + Ant Design 5.x + dayjs + TanStack Query 5.x / FastAPI + SQLAlchemy 2.x + Pydantic v2 + Alembic

---

## ファイル構成

| 操作 | ファイル | 内容 |
|------|---------|------|
| 修正 | `src/db/models.py` | Milestone クラスに `completed`/`completed_at` 追加、`Boolean` import 追加 |
| 作成 | `alembic/versions/0008_milestone_complete.py` | `milestones` テーブルに 2 列追加 |
| 修正 | `src/models/task_web.py` | `MilestoneCreate` / `MilestoneUpdate` / `MilestoneResponse` 追加 |
| 作成 | `src/api/routers/milestones.py` | 5 エンドポイント |
| 修正 | `src/api/main.py` | milestones ルーター登録 |
| 作成 | `tests/unit/test_milestones_router.py` | 5 テスト |
| 修正 | `frontend/src/lib/api.ts` | Milestone 型・API 関数追加 |
| 作成 | `frontend/src/hooks/useMilestones.ts` | 5 フック |
| 作成 | `frontend/src/pages/Projects/MilestoneTimeline.tsx` | タイムライン UI |
| 修正 | `frontend/src/pages/Projects/index.tsx` | MilestoneTimeline 組み込み |

---

### Task 1: DB モデル更新 + Alembic 0008 マイグレーション

**Files:**
- Modify: `src/db/models.py`
- Create: `alembic/versions/0008_milestone_complete.py`

- [ ] **Step 1: `src/db/models.py` の `Milestone` クラスに `completed`/`completed_at` を追加**

`src/db/models.py` の先頭 import に `Boolean` を追加（現在の import は `Float` の後）:

```python
from sqlalchemy import (
    JSON,
    UUID,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
```

`Milestone` クラス（現在 `created_at` の後に `project` リレーションがある）を以下に置き換え:

```python
class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project: Mapped["Project"] = relationship("Project", back_populates="milestones")
```

- [ ] **Step 2: Alembic 0008 マイグレーションファイルを作成**

ファイルを作成: `alembic/versions/0008_milestone_complete.py`

```python
"""milestone complete columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "milestones",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("milestones", "completed_at")
    op.drop_column("milestones", "completed")
```

- [ ] **Step 3: マイグレーション実行**

```
alembic upgrade head
```

Expected output: `Running upgrade 0007 -> 0008, milestone complete columns`

- [ ] **Step 4: インポート確認**

```
python -c "from src.db.models import Milestone; print(Milestone.completed)"
```

Expected: `Milestone.completed` の列情報が表示される（エラーなし）

- [ ] **Step 5: コミット**

```
git add src/db/models.py alembic/versions/0008_milestone_complete.py
git commit -m "feat: Milestone モデルに completed/completed_at を追加・Alembic 0008"
```

---

### Task 2: Pydantic モデル + milestones ルーター + テスト 5 件

**Files:**
- Modify: `src/models/task_web.py`
- Create: `src/api/routers/milestones.py`
- Modify: `src/api/main.py`
- Create: `tests/unit/test_milestones_router.py`

- [ ] **Step 1: テストを先に書く（TDD）**

`tests/unit/test_milestones_router.py` を新規作成:

```python
import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.db.engine import get_db

_leader = TokenPayload(sub="lead-1", name="Leader", email="l@l.com", roles=["leader"], tid="t")
_member = TokenPayload(sub="mem-1", name="Member", email="m@m.com", roles=["member"], tid="t")


def _make_project(created_by: str = "lead-1") -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.created_by = created_by
    return p


def _make_milestone(project_id: uuid.UUID | None = None) -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.project_id = project_id or uuid.uuid4()
    m.title = "ベータリリース"
    m.due_date = date(2026, 7, 1)
    m.completed = False
    m.completed_at = None
    m.created_at = datetime.now(UTC)
    return m


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


def _make_client(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    from src.api.routers.milestones import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_list_milestones(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = [_make_milestone(project.id)]

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    milestone_result = MagicMock()
    milestone_result.scalars.return_value.all.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, milestone_result])

    client = _make_client(_leader, mock_db)
    resp = client.get(f"/api/v1/projects/{project.id}/milestones")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_milestone(mock_db: AsyncMock) -> None:
    project = _make_project()
    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    mock_db.execute = AsyncMock(return_value=project_result)
    mock_db.commit = AsyncMock()

    async def _refresh(obj: object) -> None:
        # server_default で設定される created_at を Python 側で補完する
        if getattr(obj, "created_at", None) is None:
            setattr(obj, "created_at", datetime.now(UTC))

    mock_db.refresh = _refresh

    client = _make_client(_leader, mock_db)
    resp = client.post(
        f"/api/v1/projects/{project.id}/milestones",
        json={"title": "ベータリリース", "due_date": "2026-07-01"},
    )
    assert resp.status_code == 201


def test_update_milestone(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = _make_milestone(project.id)

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    ms_result = MagicMock()
    ms_result.scalar_one_or_none.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, ms_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    client = _make_client(_leader, mock_db)
    resp = client.put(
        f"/api/v1/projects/{project.id}/milestones/{ms.id}",
        json={"title": "GA リリース"},
    )
    assert resp.status_code == 200


def test_toggle_complete(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = _make_milestone(project.id)

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    ms_result = MagicMock()
    ms_result.scalar_one_or_none.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, ms_result])
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    client = _make_client(_leader, mock_db)
    resp = client.patch(f"/api/v1/projects/{project.id}/milestones/{ms.id}/complete")
    assert resp.status_code == 200


def test_delete_milestone(mock_db: AsyncMock) -> None:
    project = _make_project()
    ms = _make_milestone(project.id)

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    ms_result = MagicMock()
    ms_result.scalar_one_or_none.return_value = ms
    mock_db.execute = AsyncMock(side_effect=[project_result, ms_result])
    mock_db.commit = AsyncMock()

    client = _make_client(_leader, mock_db)
    resp = client.delete(f"/api/v1/projects/{project.id}/milestones/{ms.id}")
    assert resp.status_code == 204
```

- [ ] **Step 2: テストが FAIL することを確認（router が存在しないため ImportError/404 になる）**

```
python -m pytest tests/unit/test_milestones_router.py -v
```

Expected: `ImportError` または全テスト FAILED（`milestones` モジュールが未存在）

- [ ] **Step 3: Pydantic モデルを `src/models/task_web.py` に追加**

`BulkUpdateResponse` クラス（末尾付近）の直後、`# --- Weekly Summary ---` の前に追加:

```python
# --- Milestone ---


class MilestoneCreate(BaseModel):
    title: str
    due_date: date


class MilestoneUpdate(BaseModel):
    title: str | None = None
    due_date: date | None = None


class MilestoneResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    due_date: date
    completed: bool
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: `src/api/routers/milestones.py` を新規作成**

```python
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import Milestone, Project
from src.models.task_web import MilestoneCreate, MilestoneResponse, MilestoneUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["milestones"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return project


def _check_permission(project: Project, current_user: CurrentUser) -> None:
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if project.created_by != current_user.sub and user_role < ROLE_HIERARCHY["leader"]:
        raise HTTPException(status_code=403, detail="このプロジェクトを操作する権限がありません")


@router.get("/{project_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[MilestoneResponse]:
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.due_date.asc())
    )
    return [MilestoneResponse.model_validate(m) for m in result.scalars().all()]


@router.post(
    "/{project_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    project_id: uuid.UUID, body: MilestoneCreate, db: DbDep, current_user: CurrentUser
) -> MilestoneResponse:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    milestone = Milestone(
        project_id=project_id,
        title=body.title,
        due_date=body.due_date,
    )
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.put("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    db: DbDep,
    current_user: CurrentUser,
) -> MilestoneResponse:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    result = await db.execute(
        select(Milestone).where(
            Milestone.id == milestone_id, Milestone.project_id == project_id
        )
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="マイルストーンが見つかりません")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(milestone, field, value)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.patch(
    "/{project_id}/milestones/{milestone_id}/complete", response_model=MilestoneResponse
)
async def toggle_milestone_complete(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> MilestoneResponse:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    result = await db.execute(
        select(Milestone).where(
            Milestone.id == milestone_id, Milestone.project_id == project_id
        )
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="マイルストーンが見つかりません")
    if milestone.completed:
        milestone.completed = False
        milestone.completed_at = None
    else:
        milestone.completed = True
        milestone.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.delete(
    "/{project_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    result = await db.execute(
        select(Milestone).where(
            Milestone.id == milestone_id, Milestone.project_id == project_id
        )
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="マイルストーンが見つかりません")
    await db.delete(milestone)
    await db.commit()
```

- [ ] **Step 5: `src/api/main.py` にルーターを登録**

`from src.api.routers import (` ブロックに `milestones,` を追加:

```python
from src.api.routers import (
    admin,
    dashboard,
    dev,
    health,
    import_router,
    milestones,
    projects,
    sections,
    task_details,
    tasks,
    tasks_crud,
    templates,
    users,
)
```

ファイル末尾の `app.include_router(templates.router)` の後に追加:

```python
app.include_router(milestones.router)
```

- [ ] **Step 6: テスト実行（5 件 PASS を確認）**

```
python -m pytest tests/unit/test_milestones_router.py -v
```

Expected:
```
test_list_milestones PASSED
test_create_milestone PASSED
test_update_milestone PASSED
test_toggle_complete PASSED
test_delete_milestone PASSED
5 passed
```

- [ ] **Step 7: フルテストスイートを実行（既存テスト全パス確認）**

```
python -m pytest tests/ -q --tb=short
```

Expected: `245 passed` (240 + 5 新規)

- [ ] **Step 8: コミット**

```
git add src/models/task_web.py src/api/routers/milestones.py src/api/main.py tests/unit/test_milestones_router.py
git commit -m "feat: マイルストーン CRUD + 完了トグル エンドポイント追加・テスト 5 件"
```

---

### Task 3: フロントエンド API 型・関数 + useMilestones フック

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useMilestones.ts`

- [ ] **Step 1: `frontend/src/lib/api.ts` の末尾に追加**

ファイルの末尾（`bulkUpdateTasks` 関数の後）に追加:

```typescript
// --- Milestone ---

export interface Milestone {
  id: string
  project_id: string
  title: string
  due_date: string        // "YYYY-MM-DD"
  completed: boolean
  completed_at: string | null
  created_at: string
}

export interface MilestoneCreate {
  title: string
  due_date: string
}

export interface MilestoneUpdate {
  title?: string
  due_date?: string
}

export async function getMilestones(projectId: string): Promise<Milestone[]> {
  const { data } = await api.get<Milestone[]>(`/projects/${projectId}/milestones`)
  return data
}

export async function createMilestone(projectId: string, body: MilestoneCreate): Promise<Milestone> {
  const { data } = await api.post<Milestone>(`/projects/${projectId}/milestones`, body)
  return data
}

export async function updateMilestone(
  projectId: string,
  milestoneId: string,
  body: MilestoneUpdate,
): Promise<Milestone> {
  const { data } = await api.put<Milestone>(
    `/projects/${projectId}/milestones/${milestoneId}`,
    body,
  )
  return data
}

export async function toggleMilestoneComplete(
  projectId: string,
  milestoneId: string,
): Promise<Milestone> {
  const { data } = await api.patch<Milestone>(
    `/projects/${projectId}/milestones/${milestoneId}/complete`,
  )
  return data
}

export async function deleteMilestone(projectId: string, milestoneId: string): Promise<void> {
  await api.delete(`/projects/${projectId}/milestones/${milestoneId}`)
}
```

- [ ] **Step 2: `frontend/src/hooks/useMilestones.ts` を新規作成**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  type Milestone,
  type MilestoneCreate,
  type MilestoneUpdate,
  createMilestone,
  deleteMilestone,
  getMilestones,
  toggleMilestoneComplete,
  updateMilestone,
} from '../lib/api'

export function useMilestones(projectId: string) {
  return useQuery<Milestone[]>({
    queryKey: ['milestones', projectId],
    queryFn: () => getMilestones(projectId),
    enabled: !!projectId,
  })
}

export function useCreateMilestone(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MilestoneCreate) => createMilestone(projectId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}

export function useUpdateMilestone(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ milestoneId, body }: { milestoneId: string; body: MilestoneUpdate }) =>
      updateMilestone(projectId, milestoneId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}

export function useToggleComplete(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (milestoneId: string) => toggleMilestoneComplete(projectId, milestoneId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}

export function useDeleteMilestone(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (milestoneId: string) => deleteMilestone(projectId, milestoneId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}
```

- [ ] **Step 3: TypeScript 型チェック**

```
cd frontend; npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 4: コミット**

```
git add frontend/src/lib/api.ts frontend/src/hooks/useMilestones.ts
git commit -m "feat: Milestone 型・API 関数・useMilestones フック追加"
```

---

### Task 4: MilestoneTimeline コンポーネント + Projects/index.tsx 統合

**Files:**
- Create: `frontend/src/pages/Projects/MilestoneTimeline.tsx`
- Modify: `frontend/src/pages/Projects/index.tsx`

- [ ] **Step 1: `frontend/src/pages/Projects/MilestoneTimeline.tsx` を新規作成**

```tsx
import { useState } from 'react'
import {
  Button,
  DatePicker,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Tooltip,
  Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { Milestone } from '../../lib/api'
import {
  useCreateMilestone,
  useDeleteMilestone,
  useMilestones,
  useToggleComplete,
  useUpdateMilestone,
} from '../../hooks/useMilestones'

interface Props {
  projectId: string
}

function getMarkerColor(m: Milestone): string {
  if (m.completed) return '#52c41a'
  return dayjs(m.due_date).isBefore(dayjs().startOf('day')) ? '#ff4d4f' : '#1677ff'
}

function getDaysLabel(m: Milestone): string {
  if (m.completed) return '完了済み'
  const diff = dayjs(m.due_date).diff(dayjs().startOf('day'), 'day')
  if (diff < 0) return `期限超過 ${Math.abs(diff)} 日`
  if (diff === 0) return '今日が期限'
  return `残 ${diff} 日`
}

export default function MilestoneTimeline({ projectId }: Props) {
  const { data: milestones = [] } = useMilestones(projectId)
  const createMilestone = useCreateMilestone(projectId)
  const updateMilestone = useUpdateMilestone(projectId)
  const toggleComplete = useToggleComplete(projectId)
  const deleteMilestone = useDeleteMilestone(projectId)

  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Milestone | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const handleCreate = async () => {
    const values = await createForm.validateFields()
    try {
      await createMilestone.mutateAsync({
        title: values.title as string,
        due_date: (values.due_date as dayjs.Dayjs).format('YYYY-MM-DD'),
      })
      createForm.resetFields()
      setCreateOpen(false)
    } catch {
      void message.error('マイルストーンの作成に失敗しました')
    }
  }

  const handleEdit = async () => {
    if (!editTarget) return
    const values = await editForm.validateFields()
    try {
      await updateMilestone.mutateAsync({
        milestoneId: editTarget.id,
        body: {
          title: values.title as string,
          due_date: (values.due_date as dayjs.Dayjs).format('YYYY-MM-DD'),
        },
      })
      setEditTarget(null)
    } catch {
      void message.error('マイルストーンの更新に失敗しました')
    }
  }

  const handleToggle = async (id: string) => {
    try {
      await toggleComplete.mutateAsync(id)
    } catch {
      void message.error('完了状態の変更に失敗しました')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteMilestone.mutateAsync(id)
      setEditTarget(null)
    } catch {
      void message.error('マイルストーンの削除に失敗しました')
    }
  }

  const openEdit = (m: Milestone) => {
    setEditTarget(m)
    editForm.setFieldsValue({ title: m.title, due_date: dayjs(m.due_date) })
  }

  // タイムライン軸の範囲計算
  const sorted = [...milestones].sort((a, b) => a.due_date.localeCompare(b.due_date))
  const rangeStart =
    sorted.length > 0
      ? dayjs(sorted[0].due_date).subtract(7, 'day')
      : dayjs().subtract(7, 'day')
  const rangeEnd =
    sorted.length > 0
      ? dayjs(sorted[sorted.length - 1].due_date).add(7, 'day')
      : dayjs().add(7, 'day')
  const rangeDays = rangeEnd.diff(rangeStart, 'day') || 1

  const getLeft = (dueDate: string) =>
    `${(dayjs(dueDate).diff(rangeStart, 'day') / rangeDays) * 100}%`

  return (
    <div style={{ marginBottom: 24 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <Typography.Text strong>マイルストーン</Typography.Text>
        <Button icon={<PlusOutlined />} size="small" onClick={() => setCreateOpen(true)}>
          追加
        </Button>
      </div>

      {milestones.length === 0 ? (
        <Typography.Text type="secondary">マイルストーンはまだありません</Typography.Text>
      ) : (
        <div
          style={{ position: 'relative', height: 48, background: '#f5f5f5', borderRadius: 4 }}
        >
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              right: 0,
              height: 2,
              background: '#d9d9d9',
            }}
          />
          {milestones.map((m) => (
            <Tooltip
              key={m.id}
              title={
                <div>
                  <div>{m.title}</div>
                  <div>{m.due_date}</div>
                  <div>{getDaysLabel(m)}</div>
                </div>
              }
            >
              <div
                onClick={() => openEdit(m)}
                style={{
                  position: 'absolute',
                  left: getLeft(m.due_date),
                  top: '50%',
                  transform: 'translate(-50%, -50%) rotate(45deg)',
                  width: 16,
                  height: 16,
                  background: getMarkerColor(m),
                  cursor: 'pointer',
                  border: '2px solid white',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
                }}
              />
            </Tooltip>
          ))}
        </div>
      )}

      {/* 作成モーダル */}
      <Modal
        title="マイルストーン追加"
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => {
          setCreateOpen(false)
          createForm.resetFields()
        }}
        confirmLoading={createMilestone.isPending}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="due_date" label="期日" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 編集モーダル */}
      <Modal
        title="マイルストーン編集"
        open={!!editTarget}
        onOk={() => void handleEdit()}
        onCancel={() => setEditTarget(null)}
        confirmLoading={updateMilestone.isPending}
        footer={[
          <Popconfirm
            key="delete"
            title="このマイルストーンを削除しますか？"
            onConfirm={() => editTarget && void handleDelete(editTarget.id)}
          >
            <Button danger>削除</Button>
          </Popconfirm>,
          <Button
            key="toggle"
            onClick={() => editTarget && void handleToggle(editTarget.id)}
            loading={toggleComplete.isPending}
          >
            {editTarget?.completed ? '完了を解除' : '完了にする'}
          </Button>,
          <Button key="cancel" onClick={() => setEditTarget(null)}>
            キャンセル
          </Button>,
          <Button
            key="ok"
            type="primary"
            onClick={() => void handleEdit()}
            loading={updateMilestone.isPending}
          >
            保存
          </Button>,
        ]}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="due_date" label="期日" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/pages/Projects/index.tsx` に MilestoneTimeline を追加**

先頭 import 行に追加:
```tsx
import MilestoneTimeline from './MilestoneTimeline'
```

`return (` 内の `<Collapse` の直前（`<Space direction="vertical" ...>` 内）に追加:
```tsx
<MilestoneTimeline projectId={projectId ?? ''} />
```

具体的には、`<Collapse items={sectionItems} ...` の直前の行に挿入する。

- [ ] **Step 3: TypeScript 型チェック**

```
cd frontend; npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 4: フルテストスイート確認**

```
python -m pytest tests/ -q --tb=short
```

Expected: `245 passed`

- [ ] **Step 5: コミット**

```
git add frontend/src/pages/Projects/MilestoneTimeline.tsx frontend/src/pages/Projects/index.tsx
git commit -m "feat: MilestoneTimeline コンポーネント追加・プロジェクト詳細ページに統合"
```
