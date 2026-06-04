# F-12 工数自動算出 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク作成モーダルに過去完了タスクの実績工数から算出した「推奨工数」バッジを表示し、クリックひとつで予定工数フィールドへ自動入力できる機能を追加する。

**Architecture:** 新エンドポイント `GET /api/v1/tasks/estimate-hours?tags=...` がタグで完了タスクの実績工数を集計して返す。フロントエンドはタスク作成モーダルにタグ選択フィールド・推奨工数バッジ・予定工数入力欄を追加し、タスク作成後に工数レコードも登録する。

**Tech Stack:** FastAPI, SQLAlchemy 2.x (async), Pydantic v2, React 18 + TypeScript strict, TanStack Query, Ant Design 5.x

---

### Task 1: バックエンド — HourEstimate モデル + estimate-hours エンドポイント + テスト

**Files:**
- Modify: `src/models/task_web.py`（`HourEstimate` モデル追加）
- Modify: `src/api/routers/tasks_crud.py`（`distinct` import 追加 + エンドポイント追加）
- Create: `tests/unit/test_estimate_hours.py`（5件のユニットテスト）

#### 現在の状態

`src/models/task_web.py` の末尾は `StaleTaskItem` モデルで終わっており、`HourEstimate` はまだない。

`src/api/routers/tasks_crud.py` の冒頭 import:
```python
from sqlalchemy import func, or_, select
```
`distinct` がまだない。また `from src.models.task_web import ...` に `HourEstimate` も含まれていない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_estimate_hours.py` を新規作成:

```python
"""tests/unit/test_estimate_hours.py — F-12 工数自動算出テスト"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


def _make_row(avg: float | None, count: int) -> MagicMock:
    row = MagicMock()
    row.avg_hours = avg
    row.task_count = count
    return row


@pytest.fixture()
def client(mock_current_user: MagicMock) -> TestClient:  # noqa: ARG001
    return TestClient(app)


@pytest.fixture()
def mock_current_user() -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    user.role = "member"
    return user


class TestEstimateHours:
    """GET /api/v1/tasks/estimate-hours"""

    @patch("src.api.routers.tasks_crud.get_current_user")
    @patch("src.api.routers.tasks_crud.get_db")
    async def test_tags_match_completed_returns_avg(
        self, mock_db: AsyncMock, mock_user: MagicMock
    ) -> None:
        """タグ一致あり・完了タスク → avg と task_count を返す"""
        mock_user.return_value = MagicMock(id="user-1", role="member")
        mock_result = MagicMock()
        mock_result.one.return_value = _make_row(avg=3.5, count=4)
        session = AsyncMock()
        session.execute.return_value = mock_result
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        client = TestClient(app)
        response = client.get(
            "/api/v1/tasks/estimate-hours",
            params={"tags": ["人事", "勤怠"]},
            headers={"Authorization": "Bearer dummy"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["avg_actual_hours"] == pytest.approx(3.5)
        assert data["task_count"] == 4

    @patch("src.api.routers.tasks_crud.get_current_user")
    @patch("src.api.routers.tasks_crud.get_db")
    async def test_no_matching_tags_returns_zero(
        self, mock_db: AsyncMock, mock_user: MagicMock
    ) -> None:
        """タグ一致なし → task_count: 0, avg: null"""
        mock_user.return_value = MagicMock(id="user-1", role="member")
        mock_result = MagicMock()
        mock_result.one.return_value = _make_row(avg=None, count=0)
        session = AsyncMock()
        session.execute.return_value = mock_result
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        client = TestClient(app)
        response = client.get(
            "/api/v1/tasks/estimate-hours",
            params={"tags": ["存在しないタグ"]},
            headers={"Authorization": "Bearer dummy"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["avg_actual_hours"] is None
        assert data["task_count"] == 0

    async def test_empty_tags_returns_immediately(self) -> None:
        """タグ空リスト → DB クエリなしで即返す"""
        with patch("src.api.routers.tasks_crud.get_current_user") as mock_user, \
             patch("src.api.routers.tasks_crud.get_db") as mock_db:
            mock_user.return_value = MagicMock(id="user-1", role="member")
            session = AsyncMock()
            mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            client = TestClient(app)
            response = client.get(
                "/api/v1/tasks/estimate-hours",
                headers={"Authorization": "Bearer dummy"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["task_count"] == 0
            assert data["avg_actual_hours"] is None
            session.execute.assert_not_called()

    @patch("src.api.routers.tasks_crud.get_current_user")
    @patch("src.api.routers.tasks_crud.get_db")
    async def test_in_progress_tasks_excluded(
        self, mock_db: AsyncMock, mock_user: MagicMock
    ) -> None:
        """進行中タスクは集計対象外 → task_count: 0"""
        mock_user.return_value = MagicMock(id="user-1", role="member")
        mock_result = MagicMock()
        mock_result.one.return_value = _make_row(avg=None, count=0)
        session = AsyncMock()
        session.execute.return_value = mock_result
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        client = TestClient(app)
        response = client.get(
            "/api/v1/tasks/estimate-hours",
            params={"tags": ["進行中タグ"]},
            headers={"Authorization": "Bearer dummy"},
        )
        assert response.status_code == 200
        assert response.json()["task_count"] == 0

    @patch("src.api.routers.tasks_crud.get_current_user")
    @patch("src.api.routers.tasks_crud.get_db")
    async def test_multiple_tags_or_search(
        self, mock_db: AsyncMock, mock_user: MagicMock
    ) -> None:
        """複数タグで OR 検索 → いずれか一致タスクが集計される"""
        mock_user.return_value = MagicMock(id="user-1", role="member")
        mock_result = MagicMock()
        mock_result.one.return_value = _make_row(avg=2.0, count=2)
        session = AsyncMock()
        session.execute.return_value = mock_result
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        client = TestClient(app)
        response = client.get(
            "/api/v1/tasks/estimate-hours",
            params={"tags": ["タグA", "タグB"]},
            headers={"Authorization": "Bearer dummy"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["avg_actual_hours"] == pytest.approx(2.0)
        assert data["task_count"] == 2
```

- [ ] **Step 2: テストが失敗することを確認**

```
pytest tests/unit/test_estimate_hours.py -v
```
期待: `ImportError` または `404` — `HourEstimate` モデルも `/estimate-hours` エンドポイントも存在しないため失敗する。

- [ ] **Step 3: `HourEstimate` モデルを `src/models/task_web.py` に追加**

`src/models/task_web.py` の末尾（`StaleTaskItem` の後）に追記:

```python
class HourEstimate(BaseModel):
    avg_actual_hours: float | None
    task_count: int
```

- [ ] **Step 4: `tasks_crud.py` の import を修正して `HourEstimate` を追加**

`src/api/routers/tasks_crud.py` の sqlalchemy import 行:
```python
from sqlalchemy import func, or_, select
```
を以下に変更:
```python
from sqlalchemy import distinct, func, or_, select
```

同ファイル内の `from src.models.task_web import ...` に `HourEstimate` を追加する。
現在の import の末尾に `, HourEstimate` を加える（既存の並び順に従う）。

- [ ] **Step 5: `GET /estimate-hours` エンドポイントを追加**

`src/api/routers/tasks_crud.py` の末尾に追記:

```python
@router.get("/estimate-hours", response_model=HourEstimate)
async def estimate_hours(
    tags: list[str] = Query(default=[]),
    db: DbDep = Depends(),
    _current_user: CurrentUser = Depends(get_current_user),
) -> HourEstimate:
    if not tags:
        return HourEstimate(avg_actual_hours=None, task_count=0)

    async with db() as session:
        similar_ids = select(TaskTag.task_id).where(TaskTag.tag.in_(tags)).distinct()
        result = await session.execute(
            select(
                func.avg(TaskWorkHour.actual_hours).label("avg_hours"),
                func.count(distinct(TaskWorkHour.task_id)).label("task_count"),
            )
            .join(Task, Task.id == TaskWorkHour.task_id)
            .where(
                TaskWorkHour.task_id.in_(similar_ids),
                Task.status == "completed",
                TaskWorkHour.actual_hours.is_not(None),
            )
        )
        row = result.one()
        return HourEstimate(
            avg_actual_hours=float(row.avg_hours) if row.avg_hours is not None else None,
            task_count=row.task_count or 0,
        )
```

なお `Query` は `from fastapi import Query` — 既存の import に `Query` が含まれているか確認し、なければ追加する。`TaskTag` と `TaskWorkHour` が既存 import に含まれているか確認し、なければ追加する。`DbDep` と `CurrentUser` は既存のエイリアスを使用する。

- [ ] **Step 6: テストを実行して全件パスを確認**

```
pytest tests/unit/test_estimate_hours.py -v
```
期待: 5/5 passed

- [ ] **Step 7: 既存テスト全体が壊れていないか確認**

```
pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```
期待: 全件 passed（失敗なし）

- [ ] **Step 8: ruff チェック**

```
ruff check src/api/routers/tasks_crud.py src/models/task_web.py
```
期待: エラーなし

- [ ] **Step 9: コミット**

```bash
git add src/models/task_web.py src/api/routers/tasks_crud.py tests/unit/test_estimate_hours.py
git commit -m "feat: F-12 HourEstimate モデル・estimate-hours エンドポイント・テスト 5 件"
```

---

### Task 2: フロントエンド — HourEstimate 型 + useEstimateHours / useRecordEstimatedHours フック

**Files:**
- Modify: `frontend/src/lib/api.ts`（`HourEstimate` インターフェース追加）
- Modify: `frontend/src/hooks/useTasks.ts`（`useEstimateHours` + `useRecordEstimatedHours` フック追加）

#### 現在の状態

`frontend/src/lib/api.ts` の `Task` インターフェースは L35 から始まり `risk_level?: 'high' | 'medium' | null` が L53 にある。`HourEstimate` インターフェースはまだない。

`frontend/src/hooks/useTasks.ts` の import:
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { type Task, type TaskListResponse } from '../lib/api'
```
現在エクスポートされているフック: `useTasks`, `useTask`, `useCreateTask`, `useUpdateTask`, `useDeleteTask`

- [ ] **Step 1: `HourEstimate` インターフェースを `frontend/src/lib/api.ts` に追加**

既存の `StaleTaskItem` インターフェースの後に追記:

```typescript
export interface HourEstimate {
  avg_actual_hours: number | null
  task_count: number
}
```

また既存の API 関数群の末尾に以下を追加:

```typescript
export const getEstimateHours = async (tags: string[]): Promise<HourEstimate> => {
  const params = new URLSearchParams()
  tags.forEach(t => params.append('tags', t))
  const { data } = await api.get<HourEstimate>(`/tasks/estimate-hours?${params.toString()}`)
  return data
}
```

- [ ] **Step 2: `useEstimateHours` と `useRecordEstimatedHours` を `frontend/src/hooks/useTasks.ts` に追加**

`useTasks.ts` の import に `type HourEstimate` を追加:
```typescript
import api, { type Task, type TaskListResponse, type HourEstimate, getEstimateHours } from '../lib/api'
```

ファイル末尾に追記:

```typescript
export function useEstimateHours(tags: string[]) {
  return useQuery<HourEstimate>({
    queryKey: ['tasks', 'estimate-hours', tags],
    queryFn: () => getEstimateHours(tags),
    enabled: tags.length > 0,
    staleTime: 2 * 60 * 1000,
  })
}

export function useRecordEstimatedHours() {
  return useMutation({
    mutationFn: async ({
      taskId,
      estimatedHours,
    }: {
      taskId: string
      estimatedHours: number
    }) => {
      await api.post(`/tasks/${taskId}/work-hours`, {
        date: new Date().toISOString().slice(0, 10),
        planned_hours: estimatedHours,
        actual_hours: null,
      })
    },
  })
}
```

- [ ] **Step 3: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
期待: エラーなし

- [ ] **Step 4: コミット**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useTasks.ts
git commit -m "feat: F-12 HourEstimate 型・useEstimateHours・useRecordEstimatedHours フック追加"
```

---

### Task 3: タスク作成モーダル UI — tags フィールド・推奨工数バッジ・estimated_hours フィールド

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`（フォーム拡張）

#### 現在の状態

`frontend/src/pages/Tasks/index.tsx` の antd import（現在）:
```typescript
import { Alert, Button, DatePicker, Divider, Form, Input, message, Modal, Progress, Select, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
```
`InputNumber` がまだない。

フォーム定義（L307〜342 付近）は `title`, `description`, `visibility` の 3 フィールドのみ。

`handleCreate`（L81 付近）は `createTask.mutateAsync(values)` を呼び出す。

- [ ] **Step 1: antd import に `InputNumber` を追加**

```typescript
import { Alert, Button, DatePicker, Divider, Form, Input, InputNumber, message, Modal, Progress, Select, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
```

- [ ] **Step 2: フック import に `useEstimateHours` と `useRecordEstimatedHours` を追加**

既存の import（`useTasks`, `useCreateTask` 等）の行に追記:
```typescript
import { useTasks, useCreateTask, useUpdateTask, useDeleteTask, useEstimateHours, useRecordEstimatedHours } from '../../hooks/useTasks'
```

- [ ] **Step 3: コンポーネント内に `Form.useWatch` と フック呼び出しを追加**

コンポーネント関数の先頭付近（`form` 定義の直後）に追記:

```typescript
const watchedTags = Form.useWatch('tags', form) as string[] | undefined ?? []
const { data: estimate } = useEstimateHours(watchedTags)
const recordEstimatedHours = useRecordEstimatedHours()
```

- [ ] **Step 4: `handleCreate` を修正して estimated_hours を工数登録**

現在の `handleCreate`（L81 付近）:
```typescript
const handleCreate = async (values: Record<string, unknown>) => {
  await createTask.mutateAsync(values)
  setCreateModalOpen(false)
  form.resetFields()
}
```

以下に変更:

```typescript
const handleCreate = async (values: Record<string, unknown>) => {
  const { estimated_hours, ...taskValues } = values as {
    estimated_hours?: number
    [key: string]: unknown
  }
  const created = await createTask.mutateAsync(taskValues)
  if (estimated_hours != null && created?.id) {
    await recordEstimatedHours.mutateAsync({
      taskId: created.id as string,
      estimatedHours: estimated_hours,
    })
  }
  setCreateModalOpen(false)
  form.resetFields()
}
```

- [ ] **Step 5: フォームにタグフィールド・推奨工数バッジ・予定工数フィールドを追加**

`description` フィールドの `Form.Item` の後（`visibility` フィールドの前）に追記:

```tsx
<Form.Item name="tags" label="タグ">
  <Select
    mode="tags"
    style={{ width: '100%' }}
    placeholder="タグを入力（Enter で確定）"
    tokenSeparators={[',']}
  />
</Form.Item>

{/* 推奨工数バッジ */}
{estimate && estimate.task_count >= 1 && estimate.avg_actual_hours != null ? (
  <Form.Item label=" " colon={false}>
    <Tag
      color="blue"
      style={{ cursor: 'pointer' }}
      onClick={() => form.setFieldValue('estimated_hours', estimate.avg_actual_hours)}
    >
      🤖 推奨工数: {estimate.avg_actual_hours}h（過去{estimate.task_count}件）
    </Tag>
  </Form.Item>
) : watchedTags.length > 0 ? (
  <Form.Item label=" " colon={false}>
    <Tag color="default">🤖 データ不足（0件）</Tag>
  </Form.Item>
) : null}

<Form.Item name="estimated_hours" label="予定工数（h）">
  <InputNumber min={0} step={0.5} style={{ width: '100%' }} placeholder="例: 2.0" />
</Form.Item>
```

- [ ] **Step 6: TypeScript 型チェック**

```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
期待: エラーなし

- [ ] **Step 7: フロントエンドビルド確認**

```
cd frontend && npm run build 2>&1 | tail -10
```
期待: `✓ built in ...` (エラーなし)

- [ ] **Step 8: コミット**

```bash
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: F-12 タスク作成モーダルにタグ・推奨工数バッジ・予定工数フィールド追加"
```

---

### Task 4: 最終確認・ドキュメント更新

**Files:**
- Modify: `docs/tasks.md`（F-12 完了チェック）
- Modify: `docs/progress.md`（進捗ログ追記）

- [ ] **Step 1: バックエンドテスト全体確認**

```
pytest tests/unit/ -v --tb=short 2>&1 | tail -5
```
期待: 全件 passed（F-12 の 5 件含む）

- [ ] **Step 2: ruff check 全体**

```
ruff check src/ tests/ 2>&1 | head -20
```
期待: エラーなし

- [ ] **Step 3: TypeScript 最終確認**

```
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
期待: エラーなし

- [ ] **Step 4: `docs/tasks.md` を更新**

以下の行:
```
- [ ] **F-12 工数自動算出**: 蓄積データから 🤖 目標工数を自動算出・提案
```
を以下に変更:
```
- [x] **F-12 工数自動算出**: 蓄積データから 🤖 目標工数を自動算出・提案（2026-05-28）
```

また全体進捗サマリーテーブルの `Web App Phase 2B（Should 機能 残タスク）` 行を更新:
```
| Web App Phase 2B（Should 機能 残タスク） | 10 / 10 | 1 タスク（F-21 残） | Phase 2B-6 完了 ✅ → 着手可能 |
```

- [ ] **Step 5: `docs/progress.md` に追記**

progress.md の末尾に追記:

```markdown
## 2026-05-28（F-12 工数自動算出）

- `HourEstimate` Pydantic モデル追加（`src/models/task_web.py`）
- `GET /api/v1/tasks/estimate-hours` エンドポイント追加（タグ OR 一致・完了タスク集計）
- ユニットテスト 5 件追加（`tests/unit/test_estimate_hours.py`）
- `HourEstimate` 型・`useEstimateHours` フック・`useRecordEstimatedHours` フック追加
- タスク作成モーダルにタグフィールド・推奨工数バッジ・予定工数フィールド追加
- F-12 完了 ✅
```

- [ ] **Step 6: コミット**

```bash
git add docs/tasks.md docs/progress.md
git commit -m "docs: F-12 完了マーク・進捗ログ更新"
```
