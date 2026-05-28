# F-27 / F-28 工数実績参照 & 自動初期値設定 — 設計書

最終更新: 2026-05-28

---

## 概要

| F-ID | 機能名 | 説明 |
|------|--------|------|
| F-27 | 過去実績参照 | 同タグの完了タスクから実績工数（平均・最小・最大・件数）を参考情報として表示 |
| F-28 | 工数自動初期値設定 | タグ選択時に推奨工数を予定工数フィールドへ自動入力（ユーザー手動入力は上書きしない） |

---

## 選定アプローチ

**Option A: 既存 `estimate-hours` エンドポイントを拡張**

既存の `GET /api/v1/tasks/estimate-hours` に `min_actual_hours` / `max_actual_hours` を追加する。
フロントエンドは既存フック `useEstimateHours(tags)` をそのまま使い回す。
変更量最小で後方互換性あり（フィールド追加のみ）。

---

## アーキテクチャ

```
タグ選択
  ↓
useEstimateHours(tags)         ← 既存フック（戻り値に min/max 追加）
  ↓ GET /api/v1/tasks/estimate-hours?tags[]=xxx
estimate_hours()               ← 既存エンドポイント（SQL に MIN/MAX 追加）
  ↓
HourEstimate { avg, min, max, task_count }
  ↓
[タスク作成モーダル]            [タスク詳細 工数タブ]
  F-28: 自動入力                F-27: 過去実績 Alert 表示
  F-27: バッジで min/max 表示
```

---

## バックエンド設計

### 変更ファイル

#### `src/models/task_web.py` — HourEstimate 拡張

```python
class HourEstimate(BaseModel):
    avg_actual_hours: float | None
    min_actual_hours: float | None   # 追加
    max_actual_hours: float | None   # 追加
    task_count: int
```

#### `src/api/routers/tasks_crud.py` — estimate_hours エンドポイント

AVG のみだった集計クエリに MIN / MAX を追加する。1 クエリで完結。

```python
@router.get("/estimate-hours", response_model=HourEstimate)
async def estimate_hours(
    db: DbDep,
    current_user: CurrentUser,
    tags: list[str] = Query(default=[]),
) -> HourEstimate:
    if not tags:
        return HourEstimate(
            avg_actual_hours=None,
            min_actual_hours=None,
            max_actual_hours=None,
            task_count=0,
        )
    row = (await db.execute(
        select(
            func.avg(TaskWorkHour.actual_hours).label("avg"),
            func.min(TaskWorkHour.actual_hours).label("min"),
            func.max(TaskWorkHour.actual_hours).label("max"),
            func.count(TaskWorkHour.actual_hours).label("cnt"),
        )
        .join(Task, Task.id == TaskWorkHour.task_id)
        .join(TaskTag, TaskTag.task_id == Task.id)
        .where(
            TaskTag.tag.in_(tags),
            Task.status == "done",
            TaskWorkHour.actual_hours.is_not(None),
        )
    )).one()
    return HourEstimate(
        avg_actual_hours=float(row.avg) if row.avg is not None else None,
        min_actual_hours=float(row.min) if row.min is not None else None,
        max_actual_hours=float(row.max) if row.max is not None else None,
        task_count=row.cnt or 0,
    )
```

### テスト変更

`tests/unit/test_estimate_hours.py` — 既存 5 件のレスポンスアサーションに
`min_actual_hours` / `max_actual_hours` の検証を追加。
新規ケース: 複数件データで min/max が正しく計算されることを確認。

---

## フロントエンド設計

### 変更ファイル

#### `frontend/src/lib/api.ts` — HourEstimate 型

```typescript
export interface HourEstimate {
  avg_actual_hours: number | null
  min_actual_hours: number | null   // 追加
  max_actual_hours: number | null   // 追加
  task_count: number
}
```

#### `frontend/src/pages/Tasks/index.tsx` — タスク作成モーダル（F-27 + F-28）

**F-28: タグ変更時に自動入力**

`autoFilledRef` でユーザーの手動入力を追跡し、手動入力済みの場合は上書きしない。

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

予定工数フィールドの `onChange` で `autoFilledRef.current = false` をセットし、
手動編集を検知する。

**F-27: バッジで min/max/avg 表示**

バッジはクリック不要の参照情報表示に変更（自動入力済みのため）。

```tsx
{estimate && estimate.task_count >= 1 && estimate.avg_actual_hours != null && (
  <Form.Item label=" " colon={false}>
    <Tag color="blue">
      🤖 過去{estimate.task_count}件: 平均 {estimate.avg_actual_hours}h
      {estimate.min_actual_hours != null &&
        ` / 最小 ${estimate.min_actual_hours}h / 最大 ${estimate.max_actual_hours}h`}
    </Tag>
  </Form.Item>
)}
```

#### `frontend/src/pages/Tasks/TaskDetail.tsx` — 工数タブ（F-27）

工数タブ先頭に同タグの過去実績を Alert で表示する。
タスクが持つタグ配列を `useEstimateHours` に渡す。

```tsx
const { data: estimate } = useEstimateHours(task.tags.map(t => t.tag))

{estimate && estimate.task_count >= 1 && estimate.avg_actual_hours != null && (
  <Alert
    type="info"
    showIcon
    message={
      `同タグの過去実績（${estimate.task_count}件）: ` +
      `平均 ${estimate.avg_actual_hours}h` +
      (estimate.min_actual_hours != null
        ? ` / 最小 ${estimate.min_actual_hours}h / 最大 ${estimate.max_actual_hours}h`
        : '')
    }
    style={{ marginBottom: 16 }}
  />
)}
```

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/models/task_web.py` | 修正 | `HourEstimate` に `min_actual_hours` / `max_actual_hours` 追加 |
| `src/api/routers/tasks_crud.py` | 修正 | `estimate_hours()` の SQL クエリに MIN / MAX 追加 |
| `tests/unit/test_estimate_hours.py` | 修正 | 既存テストに min/max アサーション追加・新規ケース追加 |
| `frontend/src/lib/api.ts` | 修正 | `HourEstimate` 型に `min_actual_hours` / `max_actual_hours` 追加 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | `autoFilledRef` + `useEffect` で自動入力・バッジ表示強化 |
| `frontend/src/pages/Tasks/TaskDetail.tsx` | 修正 | 工数タブ先頭に過去実績 `Alert` 追加 |

---

## 非機能要件

- 追加クエリなし（既存 estimate-hours の SQL 1 本を拡張するのみ）
- `staleTime: 2分`（既存 `useEstimateHours` の設定を踏襲）
- 認証: 既存の `CurrentUser` 依存注入を踏襲
- Pattern B 分類: 工数データは機密対象外のため分類不要

---

## 対象外（YAGNI）

- タスク種別マスター（種別ごとに固定工数を設定するテーブル）: タグで代替可能
- 工数の信頼区間・標準偏差表示: avg/min/max で十分
- 工数予測 ML モデル: Gemini 不使用、集計のみで実現
