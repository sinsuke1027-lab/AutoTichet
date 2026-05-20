# F-14 負荷アラート（ワークロードバッジ）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ヘッダーに今後7日間の workload 超過日数を示すバッジを追加し、クリックで日別棒グラフを Popover 表示する。

**Architecture:** バックエンドに `GET /dashboard/daily-workload` エンドポイントを追加（due_date ベース日別集計、ロール別スコープ）。フロントエンドは `WorkloadAlertBadge` コンポーネントとして実装し、App.tsx の `Layout.Header` 右端に配置する。

**Tech Stack:** FastAPI / SQLAlchemy 2.x / Pydantic v2 / React 18 / TypeScript strict / Ant Design 5 / recharts / TanStack Query 5

---

## 事前確認

**既存コードの重要ポイント（読み込み不要・記載のまま使うこと）:**

- `src/api/routers/dashboard.py` のルーターは `prefix="/api/v1/dashboard"` で `router` として定義済み。
- `src/api/auth.py` の `ROLE_HIERARCHY = {"member":0,"leader":1,"manager":2,"admin":3}` / `CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]`。
- `src/db/models.py`: `Task`（`due_date`, `assignee_id`, `status`）/ `TaskWorkHour`（`task_id`, `estimated_hours`）/ `UserProfile`（`user_id`, `capacity_hours_per_day`, `department_tags`）が既存。
- `frontend/src/App.tsx` line 74: `<Header style={{ color: 'white', fontSize: 18, padding: '0 24px' }}>AutoTicket</Header>` — ここを変更。
- `frontend/src/pages/Workload/index.tsx` は recharts `BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer` を import 済み（`Cell`, `ReferenceLine` は未使用だが recharts に含まれる）。
- テストパターン: `tests/unit/test_visibility.py` の `_make_app` / `_db_with_results` パターンを踏襲。

---

## Task 1: DailyWorkloadItem Pydantic モデル追加

**Files:**
- Modify: `src/models/task_web.py`（末尾に追記）

- [ ] **Step 1: `DailyWorkloadItem` モデルを `task_web.py` 末尾に追加**

`src/models/task_web.py` の最終行（現在 `class SimilarTaskResponse` が最後）の後に追加:

```python
# --- Daily Workload ---


class DailyWorkloadItem(BaseModel):
    date: str           # "YYYY-MM-DD"
    total_hours: float  # due_date がその日のタスクの estimated_hours 合計
    capacity_hours: float  # ロール別 capacity（member=個人、leader=部署平均、manager/admin=全体平均）
    overload: bool      # total_hours > capacity_hours
    task_count: int
```

- [ ] **Step 2: モデルが正しくインポートできることを確認**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket"
.venv\Scripts\python.exe -c "from src.models.task_web import DailyWorkloadItem; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/models/task_web.py
git commit -m "feat: DailyWorkloadItem Pydantic モデル追加"
```

---

## Task 2: GET /dashboard/daily-workload エンドポイント TDD

**Files:**
- Create: `tests/unit/test_daily_workload.py`
- Modify: `src/api/routers/dashboard.py`

### Step 1: テストファイルを作成（失敗することを先に確認）

- [ ] **Step 1-1: テストファイルを作成**

`tests/unit/test_daily_workload.py` を新規作成:

```python
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.dashboard import router
from src.db.engine import get_db


def _make_app(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _db_with_results(side_effects: list) -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=side_effects)
    return db


def _capacity_scalar(value: float) -> MagicMock:
    m = MagicMock()
    m.scalar_one.return_value = value
    return m


def _make_row(task_date: date, total_hours: float, task_count: int) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda i: [task_date, total_hours, task_count][i])
    return row


def _workload_rows_result(rows_data: list[tuple]) -> MagicMock:
    m = MagicMock()
    m.all.return_value = [_make_row(*r) for r in rows_data]
    return m


def _empty_workload() -> MagicMock:
    m = MagicMock()
    m.all.return_value = []
    return m


def test_daily_workload_member_returns_7_items() -> None:
    """member ユーザー: 2 回 execute（capacity + workload）→ 7 件返却"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7


def test_daily_workload_manager_returns_7_items() -> None:
    """manager ユーザー: 2 回 execute（capacity avg + workload）→ 7 件返却"""
    manager = TokenPayload(sub="mg1", roles=["manager"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(manager, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7


def test_daily_workload_leader_with_dept_tags() -> None:
    """leader（部署タグあり）: 3 回 execute（dept_ids + capacity avg + workload）"""
    leader = TokenPayload(sub="l1", roles=["leader"], department_tags=["営業部"])
    dept_result = MagicMock()
    dept_result.scalars.return_value.all.return_value = ["u-x"]
    db = _db_with_results([dept_result, _capacity_scalar(8.0), _empty_workload()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    assert len(resp.json()) == 7


def test_overload_flag_true_when_hours_exceed_capacity() -> None:
    """total_hours > capacity_hours → overload=True"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    today = date.today()
    workload = _workload_rows_result([(today, 10.0, 3)])
    db = _db_with_results([_capacity_scalar(8.0), workload])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    assert resp.status_code == 200
    data = resp.json()
    today_item = next(d for d in data if d["date"] == today.isoformat())
    assert today_item["overload"] is True
    assert today_item["total_hours"] == 10.0
    assert today_item["task_count"] == 3


def test_days_without_tasks_have_zero_hours() -> None:
    """タスクがない日は total_hours=0, task_count=0, overload=False"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    data = resp.json()
    for item in data:
        assert item["total_hours"] == 0.0
        assert item["task_count"] == 0
        assert item["overload"] is False


def test_returned_dates_are_consecutive_from_today() -> None:
    """今日から連続 7 日の日付が返る"""
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_capacity_scalar(8.0), _empty_workload()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/dashboard/daily-workload")
    data = resp.json()
    expected = [(date.today() + timedelta(days=i)).isoformat() for i in range(7)]
    assert [d["date"] for d in data] == expected
```

- [ ] **Step 1-2: テストが失敗することを確認**

```bash
pytest tests/unit/test_daily_workload.py -v
```

Expected: FAIL（エンドポイントが未実装のため 404 or ImportError）

### Step 2: エンドポイントを実装

- [ ] **Step 2-1: `src/api/routers/dashboard.py` を修正**

ファイル冒頭の import を変更:

**現在（1〜19行目）:**
```python
from datetime import date, datetime, timedelta
from datetime import time as time_type
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskWorkHour, UserProfile
from src.models.task_web import (
    DashboardSummary,
    OverdueTaskItem,
    TaskStatus,
    TodayTaskItem,
    TrendPoint,
    WorkloadItem,
)
```

**変更後:**
```python
from datetime import date, datetime, timedelta
from datetime import time as time_type
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskWorkHour, UserProfile
from src.models.task_web import (
    DailyWorkloadItem,
    DashboardSummary,
    OverdueTaskItem,
    TaskStatus,
    TodayTaskItem,
    TrendPoint,
    WorkloadItem,
)
```

- [ ] **Step 2-2: `dashboard.py` の末尾（`get_completion_trend` の後）に新エンドポイントを追加**

```python
@router.get("/daily-workload", response_model=list[DailyWorkloadItem])
async def get_daily_workload(db: DbDep, current_user: CurrentUser) -> list[DailyWorkloadItem]:
    today = date.today()
    end_date = today + timedelta(days=6)

    user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )

    # estimated_hours: task ごとに最大値を採用（複数エントリ対策）
    wh_sub = (
        select(
            TaskWorkHour.task_id,
            func.max(TaskWorkHour.estimated_hours).label("estimated_hours"),
        )
        .group_by(TaskWorkHour.task_id)
        .subquery()
    )

    base_query = (
        select(
            Task.due_date.label("task_date"),
            func.sum(func.coalesce(wh_sub.c.estimated_hours, 1.0)).label("total_hours"),
            func.count(Task.id).label("task_count"),
        )
        .outerjoin(wh_sub, wh_sub.c.task_id == Task.id)
        .where(
            Task.due_date >= today,
            Task.due_date <= end_date,
            Task.status.notin_(["completed", "cancelled"]),
            Task.due_date.isnot(None),
        )
    )

    capacity_hours: float = 8.0

    if user_role < ROLE_HIERARCHY["manager"]:
        if user_role >= ROLE_HIERARCHY["leader"] and current_user.department_tags:
            dept_result = await db.execute(
                select(UserProfile.user_id).where(
                    UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
                )
            )
            dept_user_ids = list(dept_result.scalars().all())
            base_query = base_query.where(Task.assignee_id.in_(dept_user_ids))
            cap_result = await db.execute(
                select(func.avg(UserProfile.capacity_hours_per_day)).where(
                    UserProfile.user_id.in_(dept_user_ids)
                )
            )
            capacity_hours = float(cap_result.scalar_one() or 8.0)
        else:
            base_query = base_query.where(Task.assignee_id == current_user.sub)
            cap_result = await db.execute(
                select(UserProfile.capacity_hours_per_day).where(
                    UserProfile.user_id == current_user.sub
                )
            )
            capacity_hours = float(cap_result.scalar_one() or 8.0)
    else:
        cap_result = await db.execute(
            select(func.avg(UserProfile.capacity_hours_per_day))
        )
        capacity_hours = float(cap_result.scalar_one() or 8.0)

    result = await db.execute(base_query.group_by(Task.due_date))
    rows: dict[str, tuple[float, int]] = {
        str(row[0]): (float(row[1] or 0.0), int(row[2] or 0))
        for row in result.all()
    }

    return [
        DailyWorkloadItem(
            date=(today + timedelta(days=i)).isoformat(),
            total_hours=round(rows.get((today + timedelta(days=i)).isoformat(), (0.0, 0))[0], 1),
            capacity_hours=round(capacity_hours, 1),
            overload=rows.get((today + timedelta(days=i)).isoformat(), (0.0, 0))[0] > capacity_hours,
            task_count=rows.get((today + timedelta(days=i)).isoformat(), (0.0, 0))[1],
        )
        for i in range(7)
    ]
```

- [ ] **Step 2-3: テストが通ることを確認**

```bash
pytest tests/unit/test_daily_workload.py -v
```

Expected:
```
tests/unit/test_daily_workload.py::test_daily_workload_member_returns_7_items PASSED
tests/unit/test_daily_workload.py::test_daily_workload_manager_returns_7_items PASSED
tests/unit/test_daily_workload.py::test_daily_workload_leader_with_dept_tags PASSED
tests/unit/test_daily_workload.py::test_overload_flag_true_when_hours_exceed_capacity PASSED
tests/unit/test_daily_workload.py::test_days_without_tasks_have_zero_hours PASSED
tests/unit/test_daily_workload.py::test_returned_dates_are_consecutive_from_today PASSED
6 passed
```

- [ ] **Step 2-4: 既存テストが壊れていないことを確認**

```bash
pytest tests/unit/ -v --ignore=tests/unit/test_connectors.py --ignore=tests/unit/test_teams_chat.py --ignore=tests/unit/test_onenote.py
```

Expected: 全 passed（6 件追加で合計 124 passed）

- [ ] **Step 2-5: Commit**

```bash
git add src/api/routers/dashboard.py src/models/task_web.py tests/unit/test_daily_workload.py
git commit -m "feat: GET /dashboard/daily-workload エンドポイント追加（due_date 日別集計・ロール別スコープ）"
```

---

## Task 3: フロントエンド型定義追加

**Files:**
- Modify: `frontend/src/lib/api.ts`（末尾に追記）

- [ ] **Step 1: `api.ts` に `DailyWorkloadItem` 型を追加**

`frontend/src/lib/api.ts` の現在の末尾（`export interface SimilarTask { ... }` の後）に追加:

```typescript
export interface DailyWorkloadItem {
  date: string
  total_hours: number
  capacity_hours: number
  overload: boolean
  task_count: number
}
```

- [ ] **Step 2: TypeScript 型チェック**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: DailyWorkloadItem 型を api.ts に追加"
```

---

## Task 4: useDailyWorkload フック作成

**Files:**
- Create: `frontend/src/hooks/useDailyWorkload.ts`

- [ ] **Step 1: フックファイルを作成**

`frontend/src/hooks/useDailyWorkload.ts` を新規作成:

```typescript
import { useQuery } from '@tanstack/react-query'
import api, { type DailyWorkloadItem } from '../lib/api'

export function useDailyWorkload() {
  return useQuery<DailyWorkloadItem[]>({
    queryKey: ['daily-workload'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/daily-workload')
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}
```

- [ ] **Step 2: TypeScript 型チェック**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDailyWorkload.ts
git commit -m "feat: useDailyWorkload フック追加"
```

---

## Task 5: WorkloadAlertBadge コンポーネント作成

**Files:**
- Create: `frontend/src/components/WorkloadAlertBadge.tsx`

- [ ] **Step 1: `src/components/` ディレクトリが存在するか確認**

```bash
ls "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend\src\components" 2>$null
```

存在しない場合は作成:
```bash
mkdir "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend\src\components"
```

- [ ] **Step 2: `WorkloadAlertBadge.tsx` を作成**

`frontend/src/components/WorkloadAlertBadge.tsx`:

```tsx
import { useState } from 'react'
import { Badge, Button, Popover, Space, Tag, Typography } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useDailyWorkload } from '../hooks/useDailyWorkload'

export default function WorkloadAlertBadge() {
  const [open, setOpen] = useState(false)
  const { data = [] } = useDailyWorkload()

  const overloadDays = data.filter((d) => d.overload)
  const capacityHours = data[0]?.capacity_hours ?? 8

  const chartData = data.map((d) => ({
    date: d.date.slice(5).replace('-', '/'),  // "MM/DD"
    total: d.total_hours,
    overload: d.overload,
  }))

  const content = (
    <div style={{ width: 320 }}>
      <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
        今後7日間のワークロード
      </Typography.Text>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis unit="h" tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => [`${v}h`, '工数']} />
          <ReferenceLine
            y={capacityHours}
            stroke="#faad14"
            strokeDasharray="4 2"
            label={{ value: 'cap', fontSize: 10, fill: '#faad14' }}
          />
          <Bar dataKey="total" isAnimationActive={false}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.overload ? '#ff4d4f' : '#1677ff'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {overloadDays.length > 0 && (
        <Space wrap style={{ marginTop: 8 }}>
          {overloadDays.map((d) => (
            <Tag key={d.date} color="red">
              {d.date.slice(5).replace('-', '/')} 超過: {d.total_hours}h / {d.capacity_hours}h
            </Tag>
          ))}
        </Space>
      )}
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Link to="/workload" onClick={() => setOpen(false)}>
          詳細を見る →
        </Link>
      </div>
    </div>
  )

  return (
    <Popover
      content={content}
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
    >
      <Badge count={overloadDays.length} showZero={false}>
        <Button
          type="text"
          icon={<BellOutlined style={{ fontSize: 18, color: 'rgba(255,255,255,0.85)' }} />}
        />
      </Badge>
    </Popover>
  )
}
```

- [ ] **Step 3: TypeScript 型チェック**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/WorkloadAlertBadge.tsx
git commit -m "feat: WorkloadAlertBadge コンポーネント（バッジ + Popover 日別棒グラフ）"
```

---

## Task 6: App.tsx ヘッダー統合

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: `WorkloadAlertBadge` を import に追加**

`frontend/src/App.tsx` の import ブロックに追加（`AdminUsers` の次の行）:

**現在（30行目付近）:**
```typescript
import AdminUsers from './pages/Admin/Users'
```

**変更後:**
```typescript
import AdminUsers from './pages/Admin/Users'
import WorkloadAlertBadge from './components/WorkloadAlertBadge'
```

- [ ] **Step 2: Header を変更してバッジを右端に配置**

**現在（74行目）:**
```tsx
<Header style={{ color: 'white', fontSize: 18, padding: '0 24px' }}>AutoTicket</Header>
```

**変更後:**
```tsx
<Header
  style={{
    color: 'white',
    fontSize: 18,
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  }}
>
  <span>AutoTicket</span>
  <WorkloadAlertBadge />
</Header>
```

- [ ] **Step 3: TypeScript 型チェック**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 4: フロントエンドビルド成功確認**

```bash
npm run build
```

Expected: ビルド成功（エラーなし）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: App.tsx ヘッダーに WorkloadAlertBadge を統合"
```

---

## Task 7: ドキュメント更新

**Files:**
- Modify: `docs/progress.md`
- Modify: `docs/tasks.md`

- [ ] **Step 1: `docs/tasks.md` の F-14 チェックボックスを完了にする**

`docs/tasks.md` の以下の行を変更:

**現在:**
```markdown
- [ ] **F-14 負荷アラート**: ワークロード超過・期限超過のブラウザ通知 or バッジ
```

**変更後:**
```markdown
- [x] **F-14 負荷アラート**: ワークロード超過・期限超過のブラウザ通知 or バッジ
```

- [ ] **Step 2: `docs/tasks.md` の全体進捗サマリーテーブルを更新**

**現在:**
```markdown
| Web App Phase 2B（Should 機能 残タスク） | 3 / 7 | 4 タスク（F-14・F-21・F-12 残） | Phase 2B-2 完了 ✅ → 着手可能 |
```

**変更後:**
```markdown
| Web App Phase 2B（Should 機能 残タスク） | 4 / 7 | 3 タスク（F-21・F-12 残） | Phase 2B-2 完了 ✅ → 着手可能 |
```

- [ ] **Step 3: `docs/progress.md` を更新**

`docs/progress.md` の冒頭「現在のフェーズ」を更新:

**現在:**
```markdown
## 現在のフェーズ
**Phase: Web App Phase 2B-2（ユーザー管理・権限制御・UX 強化）✅ 完了 → Phase 2B-3 以降へ**
ステータス: F-08 ユーザー管理・ロール制御・F-07 個人 ToDo・F-04 類似タスク警告・F-11 週次 D&D グリッド 全実装完了・Graph API 申請中（承認待ち）
```

**変更後:**
```markdown
## 現在のフェーズ
**Phase: Web App Phase 2B-3（F-14 負荷アラート）✅ 完了 → F-21 Teams 通知 or F-12 工数自動算出へ**
ステータス: F-14 日別ワークロードバッジ（GET /dashboard/daily-workload + WorkloadAlertBadge）実装完了・Graph API 申請中（承認待ち）
```

「最終更新」セクションの日付を `2026-05-20` に更新し、完了した作業として以下を追記（既存記録の前に挿入）:

```markdown
  - **[Web App Phase 2B-3 — F-14 全タスク完了]** 負荷アラート（ワークロードバッジ）実装
    - `DailyWorkloadItem` Pydantic モデル追加（`src/models/task_web.py`）
    - `GET /dashboard/daily-workload` エンドポイント（due_date 日別集計・ロール別スコープ・1.0h デフォルト）
    - `tests/unit/test_daily_workload.py`（6 件追加 → 合計 130 passed）
    - `frontend/src/hooks/useDailyWorkload.ts`（5 分キャッシュ）
    - `frontend/src/components/WorkloadAlertBadge.tsx`（Badge + Popover + recharts BarChart + Cell 着色 + ReferenceLine）
    - `frontend/src/App.tsx` ヘッダー右端に WorkloadAlertBadge 統合
    - TypeScript チェック通過・フロントエンドビルド成功
```

- [ ] **Step 4: Commit**

```bash
git add docs/progress.md docs/tasks.md
git commit -m "docs: F-14 負荷アラート完了・進捗ドキュメント更新"
```

---

## 最終確認

- [ ] **全テスト実行**

```bash
pytest tests/unit/ -v --ignore=tests/unit/test_connectors.py --ignore=tests/unit/test_teams_chat.py --ignore=tests/unit/test_onenote.py
```

Expected: 130 passed（6 件増加）

- [ ] **フロントエンドビルド最終確認**

```bash
cd "C:\Users\shinsuke-imanaka\OneDrive - 株式会社デジタルフォルン\デスクトップ\研修・各スキル\Google Antigravity Apps\AutoTicket\frontend"
npm run build
```

Expected: ビルド成功

---

## 動作確認チェックリスト（実装者向け）

| 確認項目 | 手順 |
|---------|------|
| エンドポイント疎通 | バックエンド起動後 `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/dashboard/daily-workload` |
| バッジ表示 | フロントエンド起動後、超過タスクが存在する場合にヘッダー右端に赤数字バッジが表示される |
| Popover 展開 | バッジをクリックすると 7 日間の棒グラフが表示される |
| 超過日赤バー | total_hours > capacity_hours の日のバーが赤（`#ff4d4f`）になっている |
| capacity ライン | 黄色点線（`#faad14`）が capacity_hours の高さに表示される |
| 詳細リンク | 「詳細を見る →」クリックで `/workload` に遷移し Popover が閉じる |
| 超過 0 日のとき | バッジが表示されない（`showZero={false}`） |
