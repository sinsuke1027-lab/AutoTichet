# F-27 / F-28 工数実績参照 & 自動初期値設定 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク作成時にタグを選択すると過去の同タグ完了タスクの avg/min/max 実績工数を表示し、avg を予定工数フィールドへ自動入力する。

**Architecture:** 既存の `GET /api/v1/tasks/estimate-hours` エンドポイントに MIN/MAX を追加（SQL 1 クエリ拡張）。フロントエンドはタグ変更を `useEffect` で監視して自動入力し、バッジで min/max を表示する。工数タブの過去実績表示は `WorkHoursPanel.tsx` の `PastPerformanceSection` が既に実装済みのため対象外。

**Tech Stack:** Python / SQLAlchemy `func.min` `func.max` / FastAPI / React 18 / Ant Design 5 / TanStack Query

---

## ファイル構成

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `tests/unit/test_estimate_hours.py` | 修正 | ヘルパー更新・アサーション追加・新規テスト追加 |
| `src/models/task_web.py` | 修正 L487-489 | `HourEstimate` に `min_actual_hours` / `max_actual_hours` 追加 |
| `src/api/routers/tasks_crud.py` | 修正 L287-313 | `estimate_hours()` の SQL に MIN/MAX 追加 |
| `frontend/src/lib/api.ts` | 修正 L70-73 | `HourEstimate` 型に `min_actual_hours` / `max_actual_hours` 追加 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | `useRef` / `useEffect` 追加、バッジ更新、自動入力実装 |

---

## Task 1: テスト作成（失敗を先に確認する）

**Files:**
- Modify: `tests/unit/test_estimate_hours.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_estimate_hours.py` を以下の内容で全置き換えする：

```python
from unittest.mock import AsyncMock, MagicMock

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


def _exec_aggregate(
    avg_hours: float | None,
    task_count: int,
    min_hours: float | None = None,
    max_hours: float | None = None,
) -> MagicMock:
    """aggregate クエリ結果（.one() で row を返す）を模倣するモック。"""
    row = MagicMock()
    row.avg = avg_hours
    row.min = min_hours
    row.max = max_hours
    row.cnt = task_count
    m = MagicMock()
    m.one.return_value = row
    return m


def test_estimate_hours_with_matching_completed_tasks() -> None:
    """タグ一致あり・完了タスクがある場合 avg > 0, task_count >= 1 を返す。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=3.5, task_count=2, min_hours=2.0, max_hours=5.0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=backend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_actual_hours"] == 3.5
    assert data["task_count"] == 2
    assert data["min_actual_hours"] == 2.0
    assert data["max_actual_hours"] == 5.0


def test_estimate_hours_no_matching_tags() -> None:
    """タグ一致なしのとき task_count: 0, avg/min/max: null を返す。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=None, task_count=0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None
    assert data["min_actual_hours"] is None
    assert data["max_actual_hours"] is None


def test_estimate_hours_empty_tags() -> None:
    """タグ空リストのとき DB クエリ不要で task_count: 0 を返す。"""
    mock_db = AsyncMock()
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None
    assert data["min_actual_hours"] is None
    assert data["max_actual_hours"] is None
    mock_db.execute.assert_not_called()


def test_estimate_hours_excludes_in_progress_tasks() -> None:
    """進行中タスクは集計対象外（avg=None, task_count=0 を返す）。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=None, task_count=0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=design")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_count"] == 0
    assert data["avg_actual_hours"] is None


def test_estimate_hours_multiple_tags_or_search() -> None:
    """複数タグで OR 検索し、いずれか一致タスクが集計される。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=5.0, task_count=3, min_hours=3.0, max_hours=7.0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=backend&tags=frontend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_actual_hours"] == 5.0
    assert data["task_count"] == 3
    assert data["min_actual_hours"] == 3.0
    assert data["max_actual_hours"] == 7.0


def test_estimate_hours_returns_min_max() -> None:
    """単一タグで min/max/avg が正しく返る。"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_exec_aggregate(avg_hours=2.5, task_count=4, min_hours=1.0, max_hours=4.0)
    )
    client = _make_client(mock_db)
    resp = client.get("/api/v1/tasks/estimate-hours?tags=design")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_actual_hours"] == 2.5
    assert data["min_actual_hours"] == 1.0
    assert data["max_actual_hours"] == 4.0
    assert data["task_count"] == 4
```

- [ ] **Step 2: テストが失敗することを確認する**

```powershell
pytest tests/unit/test_estimate_hours.py -v
```

Expected: FAIL（`min_actual_hours` キーがレスポンスにない等）。PASS になった場合は実装が先行しているので Task 2 へスキップ可。

---

## Task 2: バックエンド — HourEstimate モデル + SQL クエリ拡張

**Files:**
- Modify: `src/models/task_web.py:487-489`
- Modify: `src/api/routers/tasks_crud.py:287-313`

- [ ] **Step 1: `HourEstimate` に min/max フィールドを追加する**

`src/models/task_web.py` の 487-489 行を以下に置き換える：

```python
class HourEstimate(BaseModel):
    avg_actual_hours: float | None
    min_actual_hours: float | None
    max_actual_hours: float | None
    task_count: int
```

- [ ] **Step 2: `estimate_hours` エンドポイントの SQL に MIN/MAX を追加する**

`src/api/routers/tasks_crud.py` の `estimate_hours` 関数全体（L287-313）を以下に置き換える：

```python
@router.get("/estimate-hours", response_model=HourEstimate)
async def estimate_hours(
    db: DbDep,
    current_user: CurrentUser,
    tags: list[str] = Query(default=[]),  # noqa: B008
) -> HourEstimate:
    if not tags:
        return HourEstimate(
            avg_actual_hours=None,
            min_actual_hours=None,
            max_actual_hours=None,
            task_count=0,
        )

    similar_ids = select(TaskTag.task_id).where(TaskTag.tag.in_(tags)).distinct()
    result = await db.execute(
        select(
            func.avg(TaskWorkHour.actual_hours).label("avg"),
            func.min(TaskWorkHour.actual_hours).label("min"),
            func.max(TaskWorkHour.actual_hours).label("max"),
            func.count(distinct(TaskWorkHour.task_id)).label("cnt"),
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
        avg_actual_hours=float(row.avg) if row.avg is not None else None,
        min_actual_hours=float(row.min) if row.min is not None else None,
        max_actual_hours=float(row.max) if row.max is not None else None,
        task_count=row.cnt or 0,
    )
```

- [ ] **Step 3: テストが通ることを確認する**

```powershell
pytest tests/unit/test_estimate_hours.py -v
```

Expected: **6/6 PASSED**

- [ ] **Step 4: 全テストが壊れていないことを確認する**

```powershell
pytest tests/ -v --ignore=tests/integration
```

Expected: 全件 PASSED（既存テスト数より 1 件増）

- [ ] **Step 5: コミット**

```powershell
git add tests/unit/test_estimate_hours.py src/models/task_web.py src/api/routers/tasks_crud.py
git commit -m "feat: F-27/F-28 estimate-hours に min/max を追加"
```

---

## Task 3: フロントエンド — `api.ts` 型更新

**Files:**
- Modify: `frontend/src/lib/api.ts:70-73`

- [ ] **Step 1: `HourEstimate` インターフェースに min/max を追加する**

`frontend/src/lib/api.ts` の `HourEstimate` インターフェース（70-73 行）を以下に置き換える：

```typescript
export interface HourEstimate {
  avg_actual_hours: number | null
  min_actual_hours: number | null
  max_actual_hours: number | null
  task_count: number
}
```

- [ ] **Step 2: TypeScript 型チェックが通ることを確認する**

```powershell
cd frontend
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 3: コミット**

```powershell
git add frontend/src/lib/api.ts
git commit -m "feat: F-27 HourEstimate 型に min/max フィールド追加"
```

---

## Task 4: フロントエンド — タスク作成モーダル自動入力 & バッジ強化

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: `useEffect` と `useRef` を import に追加する**

`frontend/src/pages/Tasks/index.tsx` の 1 行目を以下に置き換える：

```typescript
import { useState, useEffect, useRef } from 'react'
```

- [ ] **Step 2: `autoFilledRef` を追加し、`useEffect` で自動入力を実装する**

`index.tsx` の `const { data: estimate } = useEstimateHours(watchedTags)` の直後（63 行目の後）に以下を追加する：

```typescript
  const autoFilledRef = useRef(false)

  useEffect(() => {
    if (!estimate || estimate.task_count === 0 || estimate.avg_actual_hours == null) return
    const current = form.getFieldValue('estimated_hours') as number | undefined
    if (current == null || autoFilledRef.current) {
      form.setFieldValue('estimated_hours', estimate.avg_actual_hours)
      autoFilledRef.current = true
    }
  }, [estimate, form])
```

- [ ] **Step 3: モーダルクローズ時に `autoFilledRef` をリセットする**

`handleCreate` 内の `form.resetFields()` 直後（101-103 行付近）に `autoFilledRef.current = false` を追加する：

```typescript
    setOpen(false)
    form.resetFields()
    autoFilledRef.current = false
    setNewTitle('')
```

- [ ] **Step 4: バッジを min/max 表示に更新し、InputNumber に onChange を追加する**

`index.tsx` のバッジ〜InputNumber 部分（364-382 行付近）を以下に置き換える：

```tsx
          {estimate && estimate.task_count >= 1 && estimate.avg_actual_hours != null ? (
            <Form.Item label=" " colon={false}>
              <Tag color="blue">
                🤖 過去{estimate.task_count}件: 平均 {estimate.avg_actual_hours}h
                {estimate.min_actual_hours != null &&
                  ` / 最小 ${estimate.min_actual_hours}h / 最大 ${estimate.max_actual_hours}h`}
              </Tag>
            </Form.Item>
          ) : watchedTags.length > 0 ? (
            <Form.Item label=" " colon={false}>
              <Tag color="default">過去データなし</Tag>
            </Form.Item>
          ) : null}

          <Form.Item name="estimated_hours" label="予定工数（h）">
            <InputNumber
              min={0}
              step={0.5}
              style={{ width: '100%' }}
              placeholder="例: 2.0"
              onChange={() => { autoFilledRef.current = false }}
            />
          </Form.Item>
```

- [ ] **Step 5: TypeScript 型チェックが通ることを確認する**

```powershell
cd frontend
npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 6: 開発サーバーで動作確認する**

バックエンドを起動した状態でフロントを開く：

```powershell
# ターミナル1
uvicorn src.api.main:app --reload --port 8000

# ターミナル2
cd frontend
npm run dev
```

`http://localhost:5173` でタスク一覧を開き、以下を順番に確認する：

1. 「新規タスク」ボタン → モーダルを開く
2. タグ欄に過去の完了タスクと同じタグを入力（例: `backend`）
3. **予定工数フィールドに自動で数値が入ること**（F-28）
4. **バッジに「🤖 過去N件: 平均Xh / 最小Yh / 最大Zh」が表示されること**（F-27）
5. 予定工数を手動で書き換え → 別のタグを追加 → **上書きされないこと**

過去の完了タスクが DB にない場合は、まず1件タスクを作成して `status=completed` に変更し、工数タブで実績工数を記録してから確認する。

- [ ] **Step 7: コミット**

```powershell
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: F-27/F-28 タスク作成モーダルに工数自動入力・min/max バッジ追加"
```

---

## 完了確認チェックリスト

- [ ] `pytest tests/unit/test_estimate_hours.py -v` → 6/6 PASSED
- [ ] `pytest tests/ -v --ignore=tests/integration` → 全件 PASSED
- [ ] `npx tsc --noEmit` → エラーなし
- [ ] タグ選択 → 予定工数が自動入力される（F-28）
- [ ] バッジに avg/min/max が表示される（F-27）
- [ ] 手動入力後はタグ変更で上書きされない
