# マイページ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ログインユーザー自身のプロフィール編集・今週タスク・工数グラフを一画面で確認できる `/mypage` を追加する。

**Architecture:** ダッシュボードは変更せず `/mypage` を独立ルートとして追加。バックエンドは `GET /users/me/profile`・`PATCH /users/me`・`GET /dashboard/my-weekly-summary` の3本を追加し、今週タスクや期限超過は既存 `GET /tasks` を流用する。

**Tech Stack:** FastAPI + SQLAlchemy 2.x / Pydantic v2 / React 18 + TypeScript + Ant Design 5.x + recharts + date-fns + TanStack Query 5.x

**Design doc:** `docs/superpowers/specs/2026-06-03-mypage-design.md`

---

## ファイル構成

```
# 変更するファイル
src/models/task_web.py                     ← UserProfileUpdate / WeeklyWorkSummary モデル追加
src/api/routers/users.py                   ← GET /me/profile, PATCH /me 追加
src/api/routers/dashboard.py               ← GET /my-weekly-summary 追加
frontend/src/lib/api.ts                    ← 型定義追加 + API 関数追加
frontend/src/hooks/useTasks.ts             ← TaskFilters に due_date_gte/lte 追加
frontend/src/App.tsx                       ← /mypage ルート・ナビ追加

# 新規作成するファイル
tests/unit/test_update_me.py
tests/unit/test_my_weekly_summary.py
frontend/src/hooks/useMyPage.ts
frontend/src/pages/MyPage/index.tsx
frontend/src/pages/MyPage/ProfileCard.tsx
frontend/src/pages/MyPage/WeeklySummary.tsx
```

---

### Task 1: Pydantic モデル追加

**Files:**
- Modify: `src/models/task_web.py`（末尾 User セクションに追記）

- [ ] **Step 1: `UserProfileUpdate` と `WeeklyWorkSummary` を追加する**

`src/models/task_web.py` の末尾（`# --- Similar Task ---` の手前）に追記:

```python
class UserProfileUpdate(BaseModel):
    display_name: str | None = None
    capacity_hours_per_day: float | None = None
    department_tags: list[str] | None = None
```

さらに末尾に追記:

```python
# --- Weekly Summary ---


class WeeklyWorkSummary(BaseModel):
    week_start: date
    planned_hours: float
    actual_hours: float
    task_count: int
    completed_count: int
    overdue_count: int
```

- [ ] **Step 2: import 確認**

`from datetime import date, datetime` が既に先頭にあることを確認する（既存）。

- [ ] **Step 3: Python の構文チェック**

Run: `python -c "from src.models.task_web import UserProfileUpdate, WeeklyWorkSummary; print('ok')"`
Expected: `ok`

- [ ] **Step 4: コミット**

```bash
git add src/models/task_web.py
git commit -m "feat: UserProfileUpdate / WeeklyWorkSummary Pydantic モデル追加"
```

---

### Task 2: バックエンド API + テスト

**Files:**
- Modify: `src/api/routers/users.py`
- Modify: `src/api/routers/dashboard.py`
- Create: `tests/unit/test_update_me.py`
- Create: `tests/unit/test_my_weekly_summary.py`

#### 2-A: `GET /users/me/profile` + `PATCH /users/me` テストを書く

- [ ] **Step 1: テストファイルを作成する**

`tests/unit/test_update_me.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.users import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="User One", email="u@u.com", roles=["member"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_profile() -> MagicMock:
    p = MagicMock()
    p.user_id = "user-1"
    p.display_name = "User One"
    p.email = "u@u.com"
    p.role = "member"
    p.department_tags = ["dev"]
    p.capacity_hours_per_day = 8.0
    return p


def test_get_my_profile_returns_200(client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = _make_profile()
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/users/me/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "user-1"
    assert data["display_name"] == "User One"
    assert data["department_tags"] == ["dev"]


def test_get_my_profile_no_db_record_returns_404(
    client: TestClient, mock_db: AsyncMock
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/users/me/profile")
    assert resp.status_code == 404


def test_patch_me_updates_display_name(client: TestClient, mock_db: AsyncMock) -> None:
    profile = _make_profile()
    profile.display_name = "Updated"
    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    resp = client.patch("/api/v1/users/me", json={"display_name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated"


def test_patch_me_not_found_returns_404(client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.patch("/api/v1/users/me", json={"display_name": "X"})
    assert resp.status_code == 404
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `python -m pytest tests/unit/test_update_me.py -v`
Expected: FAIL (404 / 405 — エンドポイント未実装のため)

#### 2-B: `GET /users/me/profile` + `PATCH /users/me` を実装する

- [ ] **Step 3: `src/api/routers/users.py` を更新する**

既存の import 行を以下に置き換える（`select` を追加、`UserProfileUpdate`・`AdminUserResponse` を追加）:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import UserProfile
from src.models.task_web import AdminUserResponse, MeResponse, UserProfileUpdate, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: CurrentUser) -> MeResponse:
    return MeResponse(
        user_id=current_user.sub,
        name=current_user.name,
        email=current_user.email,
        roles=current_user.roles,
    )


@router.get("/me/profile", response_model=AdminUserResponse)
async def get_my_profile(db: DbDep, current_user: CurrentUser) -> AdminUserResponse:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.sub))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="プロフィールが見つかりません")
    return AdminUserResponse.model_validate(profile)


@router.patch("/me", response_model=AdminUserResponse)
async def update_my_profile(
    body: UserProfileUpdate, db: DbDep, current_user: CurrentUser
) -> AdminUserResponse:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.sub))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="プロフィールが見つかりません")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return AdminUserResponse.model_validate(profile)


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: DbDep,
    current_user: CurrentUser,
) -> list[UserResponse]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.display_name))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `python -m pytest tests/unit/test_update_me.py -v`
Expected: 4 passed

#### 2-C: `GET /dashboard/my-weekly-summary` テストを書く

- [ ] **Step 5: テストファイルを作成する**

`tests/unit/test_my_weekly_summary.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user
from src.api.routers.dashboard import router
from src.api.auth import TokenPayload
from src.db.engine import get_db

_user = TokenPayload(sub="u1", name="U", email="u@u.com", roles=["member"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_side_effects() -> list[MagicMock]:
    """週4件 × (タスク集計 + 工数集計) + 期限超過 = 9回のexecuteモック"""
    mocks = []
    for _ in range(4):
        task_m = MagicMock()
        task_m.all.return_value = []
        mocks.append(task_m)
        wh_m = MagicMock()
        wh_m.one.return_value = (0.0, 0.0)
        mocks.append(wh_m)
    overdue_m = MagicMock()
    overdue_m.scalar_one.return_value = 0
    mocks.append(overdue_m)
    return mocks


def test_returns_4_weeks(client: TestClient, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(side_effect=_make_side_effects())
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert "week_start" in data[0]
    assert "planned_hours" in data[0]
    assert "task_count" in data[0]


def test_empty_work_hours_returns_zeros(client: TestClient, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(side_effect=_make_side_effects())
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    assert resp.status_code == 200
    for item in resp.json():
        assert item["planned_hours"] == 0.0
        assert item["actual_hours"] == 0.0
        assert item["task_count"] == 0


def test_overdue_count_in_last_item(client: TestClient, mock_db: AsyncMock) -> None:
    mocks = _make_side_effects()
    mocks[-1].scalar_one.return_value = 3  # 3件期限超過
    mock_db.execute = AsyncMock(side_effect=mocks)
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data[-1]["overdue_count"] == 3
    assert data[0]["overdue_count"] == 0  # 過去週は 0
    assert data[1]["overdue_count"] == 0


def test_older_weeks_have_zero_overdue(client: TestClient, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(side_effect=_make_side_effects())
    resp = client.get("/api/v1/dashboard/my-weekly-summary")
    data = resp.json()
    for item in data[:-1]:  # 最新週以外
        assert item["overdue_count"] == 0
```

- [ ] **Step 6: テストが失敗することを確認する**

Run: `python -m pytest tests/unit/test_my_weekly_summary.py -v`
Expected: FAIL (404 — エンドポイント未実装のため)

#### 2-D: `GET /dashboard/my-weekly-summary` を実装する

- [ ] **Step 7: `src/api/routers/dashboard.py` の先頭 import に追記する**

既存の import 行に `WeeklyWorkSummary` を追加:

```python
from src.models.task_web import (
    DailyWorkloadItem,
    DashboardSummary,
    OverdueTaskItem,
    StaleTaskItem,
    TaskStatus,
    TodayTaskItem,
    TrendPoint,
    WeeklyWorkSummary,
    WorkloadItem,
)
```

- [ ] **Step 8: エンドポイントを `src/api/routers/dashboard.py` の末尾に追加する**

```python
@router.get("/my-weekly-summary", response_model=list[WeeklyWorkSummary])
async def get_my_weekly_summary(
    db: DbDep, current_user: CurrentUser
) -> list[WeeklyWorkSummary]:
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())

    results: list[WeeklyWorkSummary] = []
    for i in range(3, -1, -1):  # 3週前 → 今週（古い順）
        week_start = this_monday - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)

        # タスク集計
        task_result = await db.execute(
            select(Task.status, func.count(Task.id))
            .where(
                Task.assignee_id == current_user.sub,
                Task.due_date >= week_start,
                Task.due_date <= week_end,
                Task.due_date.isnot(None),
            )
            .group_by(Task.status)
        )
        status_counts: dict[str, int] = {row[0]: row[1] for row in task_result.all()}
        task_count = sum(status_counts.values())
        completed_count = status_counts.get("completed", 0)

        # 工数集計
        wh_result = await db.execute(
            select(
                func.coalesce(func.sum(TaskWorkHour.estimated_hours), 0.0),
                func.coalesce(func.sum(TaskWorkHour.actual_hours), 0.0),
            )
            .join(Task, Task.id == TaskWorkHour.task_id)
            .where(
                TaskWorkHour.user_id == current_user.sub,
                Task.due_date >= week_start,
                Task.due_date <= week_end,
                Task.due_date.isnot(None),
            )
        )
        planned_hours, actual_hours = wh_result.one()

        # 期限超過（最新週のみ）
        overdue_count = 0
        if i == 0:
            overdue_result = await db.execute(
                select(func.count(Task.id)).where(
                    Task.assignee_id == current_user.sub,
                    Task.due_date < today,
                    Task.status.notin_(["completed", "cancelled"]),
                )
            )
            overdue_count = overdue_result.scalar_one()

        results.append(
            WeeklyWorkSummary(
                week_start=week_start,
                planned_hours=float(planned_hours),
                actual_hours=float(actual_hours),
                task_count=task_count,
                completed_count=completed_count,
                overdue_count=overdue_count,
            )
        )

    return results
```

- [ ] **Step 9: テストが通ることを確認する**

Run: `python -m pytest tests/unit/test_my_weekly_summary.py tests/unit/test_update_me.py -v`
Expected: 8 passed

- [ ] **Step 10: 全テストが通ることを確認する**

Run: `python -m pytest tests/ -q`
Expected: 236 passed 以上, 0 failed

- [ ] **Step 11: コミット**

```bash
git add src/api/routers/users.py src/api/routers/dashboard.py \
        src/models/task_web.py \
        tests/unit/test_update_me.py tests/unit/test_my_weekly_summary.py
git commit -m "feat: GET /users/me/profile, PATCH /users/me, GET /dashboard/my-weekly-summary 追加"
```

---

### Task 3: フロントエンド型定義 + フック

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useTasks.ts`
- Create: `frontend/src/hooks/useMyPage.ts`

- [ ] **Step 1: `frontend/src/lib/api.ts` に型定義と API 関数を追加する**

`deleteRecurrence` 関数の直後（ファイル末尾）に追記:

```typescript
export interface UserProfileUpdate {
  display_name?: string | null
  capacity_hours_per_day?: number | null
  department_tags?: string[] | null
}

export interface WeeklyWorkSummary {
  week_start: string
  planned_hours: number
  actual_hours: number
  task_count: number
  completed_count: number
  overdue_count: number
}

export async function updateMyProfile(body: UserProfileUpdate): Promise<AdminUser> {
  const { data } = await api.patch<AdminUser>('/users/me', body)
  return data
}

export async function getMyWeeklySummary(): Promise<WeeklyWorkSummary[]> {
  const { data } = await api.get<WeeklyWorkSummary[]>('/dashboard/my-weekly-summary')
  return data
}
```

- [ ] **Step 2: `frontend/src/hooks/useTasks.ts` の `TaskFilters` に日付フィルタを追加する**

`TaskFilters` インターフェースに2フィールドを追加:

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
  due_date_gte?: string   // 追加
  due_date_lte?: string   // 追加
}
```

- [ ] **Step 3: `frontend/src/hooks/useMyPage.ts` を新規作成する**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { endOfWeek, format, startOfWeek, subDays } from 'date-fns'
import api, {
  type AdminUser,
  type UserProfileUpdate,
  type WeeklyWorkSummary,
  getMyWeeklySummary,
  updateMyProfile,
} from '../lib/api'
import { useTasks } from './useTasks'

export function useMyProfile() {
  return useQuery<AdminUser>({
    queryKey: ['my-profile'],
    queryFn: async () => {
      const { data } = await api.get<AdminUser>('/users/me/profile')
      return data
    },
  })
}

export function useUpdateMyProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UserProfileUpdate) => updateMyProfile(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['my-profile'] })
    },
  })
}

export function useMyWeeklySummary() {
  return useQuery<WeeklyWorkSummary[]>({
    queryKey: ['my-weekly-summary'],
    queryFn: getMyWeeklySummary,
    staleTime: 5 * 60 * 1000,
  })
}

export function useMyWeeklyTasks() {
  const now = new Date()
  const weekStart = format(startOfWeek(now, { weekStartsOn: 1 }), 'yyyy-MM-dd')
  const weekEnd = format(endOfWeek(now, { weekStartsOn: 1 }), 'yyyy-MM-dd')
  return useTasks({
    my_tasks_only: true,
    due_date_gte: weekStart,
    due_date_lte: weekEnd,
    limit: 20,
  })
}

export function useMyOverdueTasks() {
  const yesterday = format(subDays(new Date(), 1), 'yyyy-MM-dd')
  return useTasks({
    my_tasks_only: true,
    due_date_lte: yesterday,
    limit: 10,
  })
}
```

- [ ] **Step 4: TypeScript の型チェックを実行する**

Run: `cd frontend && npx tsc --noEmit`
Expected: エラーなし（出力なし）

- [ ] **Step 5: コミット**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useTasks.ts frontend/src/hooks/useMyPage.ts
git commit -m "feat: マイページ フロントエンド型定義・フック追加"
```

---

### Task 4: ProfileCard コンポーネント

**Files:**
- Create: `frontend/src/pages/MyPage/ProfileCard.tsx`

- [ ] **Step 1: `frontend/src/pages/MyPage/ProfileCard.tsx` を作成する**

```tsx
import { useState } from 'react'
import {
  Button,
  Card,
  Form,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  Input,
  message,
} from 'antd'
import { EditOutlined, UserOutlined } from '@ant-design/icons'
import { useMyProfile, useUpdateMyProfile } from '../../hooks/useMyPage'

const ROLE_LABELS: Record<string, string> = {
  member: 'メンバー',
  leader: 'リーダー',
  manager: 'マネージャー',
  admin: '管理者',
}

const ROLE_COLORS: Record<string, string> = {
  member: 'default',
  leader: 'blue',
  manager: 'orange',
  admin: 'red',
}

export default function ProfileCard() {
  const { data: profile, isLoading } = useMyProfile()
  const updateProfile = useUpdateMyProfile()
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  if (isLoading) return <Card><Spin /></Card>
  if (!profile) return <Card><Typography.Text type="secondary">プロフィールが見つかりません</Typography.Text></Card>

  const handleOpen = () => {
    form.setFieldsValue({
      display_name: profile.display_name,
      capacity_hours_per_day: profile.capacity_hours_per_day,
      department_tags: profile.department_tags,
    })
    setOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    try {
      await updateProfile.mutateAsync(values)
      void message.success('プロフィールを更新しました')
      setOpen(false)
    } catch {
      void message.error('更新に失敗しました')
    }
  }

  return (
    <>
      <Card
        title={
          <Space>
            <UserOutlined />
            プロフィール
          </Space>
        }
        extra={
          <Button icon={<EditOutlined />} size="small" onClick={handleOpen}>
            編集
          </Button>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Typography.Title level={4} style={{ margin: 0 }}>
            {profile.display_name}
          </Typography.Title>
          <Typography.Text type="secondary">{profile.email ?? '—'}</Typography.Text>
          <Space wrap>
            <Tag color={ROLE_COLORS[profile.role] ?? 'default'}>
              {ROLE_LABELS[profile.role] ?? profile.role}
            </Tag>
            {profile.department_tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </Space>
          <Typography.Text>
            1日稼働時間: <strong>{profile.capacity_hours_per_day}h</strong>
          </Typography.Text>
        </Space>
      </Card>

      <Modal
        title="プロフィールを編集"
        open={open}
        onOk={handleSave}
        onCancel={() => setOpen(false)}
        confirmLoading={updateProfile.isPending}
        okText="保存"
        cancelText="キャンセル"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="表示名"
            name="display_name"
            rules={[{ required: true, message: '表示名を入力してください' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="1日稼働時間（時間）" name="capacity_hours_per_day">
            <InputNumber min={1} max={24} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="部門タグ" name="department_tags">
            <Select mode="tags" placeholder="タグを入力して Enter" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
```

- [ ] **Step 2: TypeScript の型チェックを実行する**

Run: `cd frontend && npx tsc --noEmit`
Expected: エラーなし

- [ ] **Step 3: コミット**

```bash
git add frontend/src/pages/MyPage/ProfileCard.tsx
git commit -m "feat: ProfileCard コンポーネント追加"
```

---

### Task 5: WeeklySummary コンポーネント

**Files:**
- Create: `frontend/src/pages/MyPage/WeeklySummary.tsx`

- [ ] **Step 1: `frontend/src/pages/MyPage/WeeklySummary.tsx` を作成する**

```tsx
import { Card, Col, Row, Spin, Statistic } from 'antd'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useMyWeeklySummary } from '../../hooks/useMyPage'

export default function WeeklySummary() {
  const { data: summaries, isLoading } = useMyWeeklySummary()

  if (isLoading) return <Spin />
  if (!summaries || summaries.length === 0) return null

  const current = summaries[summaries.length - 1]
  const completionRate =
    current.task_count > 0
      ? Math.round((current.completed_count / current.task_count) * 100)
      : 0

  const chartData = summaries.map((s) => ({
    week: `${s.week_start.slice(5, 10).replace('-', '/')}週`,
    予定: s.planned_hours,
    実績: s.actual_hours,
  }))

  return (
    <Card title="今週のサマリー">
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Statistic title="今週タスク数" value={current.task_count} />
        </Col>
        <Col span={6}>
          <Statistic title="完了率" value={completionRate} suffix="%" />
        </Col>
        <Col span={6}>
          <Statistic title="予定工数" value={current.planned_hours} suffix="h" />
        </Col>
        <Col span={6}>
          <Statistic
            title="期限超過"
            value={current.overdue_count}
            valueStyle={{ color: current.overdue_count > 0 ? '#cf1322' : undefined }}
          />
        </Col>
      </Row>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={{ fontSize: 12 }} />
          <YAxis unit="h" tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v: number) => `${v}h`} />
          <Legend />
          <Bar dataKey="予定" fill="#1677ff" />
          <Bar dataKey="実績" fill="#52c41a" />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}
```

- [ ] **Step 2: TypeScript の型チェックを実行する**

Run: `cd frontend && npx tsc --noEmit`
Expected: エラーなし

- [ ] **Step 3: コミット**

```bash
git add frontend/src/pages/MyPage/WeeklySummary.tsx
git commit -m "feat: WeeklySummary コンポーネント追加（KPI + 工数グラフ）"
```

---

### Task 6: MyPage index + App.tsx 接続

**Files:**
- Create: `frontend/src/pages/MyPage/index.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: `frontend/src/pages/MyPage/index.tsx` を作成する**

```tsx
import { Card, Col, List, Row, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useMyOverdueTasks, useMyWeeklyTasks } from '../../hooks/useMyPage'
import ProfileCard from './ProfileCard'
import WeeklySummary from './WeeklySummary'
import type { Task } from '../../lib/api'

const STATUS_COLORS: Record<string, string> = {
  not_started: 'default',
  in_progress: 'processing',
  completed: 'success',
  cancelled: 'error',
}

const STATUS_LABELS: Record<string, string> = {
  not_started: '未着手',
  in_progress: '進行中',
  completed: '完了',
  cancelled: 'キャンセル',
}

export default function MyPage() {
  const navigate = useNavigate()
  const { data: weeklyTasksData } = useMyWeeklyTasks()
  const { data: overdueTasksData } = useMyOverdueTasks()

  const weeklyTasks = weeklyTasksData?.items ?? []
  const overdueTasks = (overdueTasksData?.items ?? []).filter(
    (t) => t.status !== 'completed' && t.status !== 'cancelled',
  )

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Typography.Title level={4} style={{ margin: 0 }}>
        マイページ
      </Typography.Title>

      <Row gutter={16}>
        <Col span={10}>
          <ProfileCard />
        </Col>
        <Col span={14}>
          <WeeklySummary />
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card
            title="今週のタスク"
            extra={<Tag color="blue">{weeklyTasks.length}件</Tag>}
          >
            <List
              dataSource={weeklyTasks}
              renderItem={(task: Task) => (
                <List.Item
                  key={task.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/tasks/${task.id}`)}
                >
                  <Space>
                    <Tag color={STATUS_COLORS[task.status]}>
                      {STATUS_LABELS[task.status] ?? task.status}
                    </Tag>
                    <Typography.Text>{task.title}</Typography.Text>
                  </Space>
                </List.Item>
              )}
              locale={{ emptyText: '今週のタスクはありません' }}
              style={{ maxHeight: 300, overflowY: 'auto' }}
            />
          </Card>
        </Col>

        <Col span={12}>
          <Card
            title="期限超過タスク"
            extra={
              overdueTasks.length > 0 ? (
                <Tag color="red">{overdueTasks.length}件</Tag>
              ) : null
            }
          >
            <List
              dataSource={overdueTasks}
              renderItem={(task: Task) => (
                <List.Item
                  key={task.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/tasks/${task.id}`)}
                >
                  <Space>
                    <Tag color="red">{task.due_date ?? '—'}</Tag>
                    <Typography.Text>{task.title}</Typography.Text>
                  </Space>
                </List.Item>
              )}
              locale={{ emptyText: '期限超過タスクはありません' }}
              style={{ maxHeight: 300, overflowY: 'auto' }}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
```

- [ ] **Step 2: `frontend/src/App.tsx` にルートとナビを追加する**

import 文に `MyPage` を追加:

```typescript
import MyPage from './pages/MyPage'
```

`NAV_ITEMS` の配列でダッシュボードの直後（`{ key: '/tasks', ... }` の前）に追加:

```typescript
const NAV_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'ダッシュボード' },
  { key: '/mypage', icon: <UserOutlined />, label: 'マイページ' },   // ← 追加
  { key: '/tasks', icon: <CheckSquareOutlined />, label: 'タスク一覧' },
  // ... 以下既存のまま
]
```

`Routes` に追加（`<Route path="/tasks" ...>` の直前）:

```tsx
<Route path="/mypage" element={<MyPage />} />
```

- [ ] **Step 3: TypeScript の型チェックを実行する**

Run: `cd frontend && npx tsc --noEmit`
Expected: エラーなし

- [ ] **Step 4: 全バックエンドテストが通ることを確認する**

Run: `python -m pytest tests/ -q`
Expected: 236 passed 以上, 0 failed

- [ ] **Step 5: コミット**

```bash
git add frontend/src/pages/MyPage/index.tsx frontend/src/App.tsx
git commit -m "feat: マイページ (/mypage) 追加・ナビ接続"
```

---

## 完了チェック

全タスク完了後に以下を確認する:

```bash
# バックエンドテスト全件通過
python -m pytest tests/ -q

# TypeScript エラーなし
cd frontend && npx tsc --noEmit

# 動作確認（ブラウザで http://localhost:5175/mypage を開く）
# - サイドバーに「マイページ」が表示される
# - プロフィールカードに表示名・ロール・部門タグが表示される
# - 「編集」ボタンでモーダルが開き保存できる
# - 今週サマリーに KPI 4 枚と工数グラフが表示される
# - 今週のタスクと期限超過タスクが表示される
```
