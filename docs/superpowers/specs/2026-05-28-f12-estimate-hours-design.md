# F-12 工数自動算出 設計書

作成日: 2026-05-28

---

## 概要

タスク作成モーダルにおいて、入力したタグと一致する過去完了タスクの実績工数から「推奨工数」を算出・提示する機能。クリックひとつで予定工数フィールドに自動入力できる。

---

## 算出ロジック

- 入力タグと OR 一致する `status = "completed"` タスクの `TaskWorkHour.actual_hours` を集計
- `avg_actual_hours`（平均）と `task_count`（件数）を返す
- タグ未入力・一致0件の場合は `task_count: 0`、`avg_actual_hours: null` を返す（エラーにしない）

---

## バックエンド

### 新エンドポイント

```
GET /api/v1/tasks/estimate-hours?tags=人事&tags=勤怠
```

- クエリパラメータ `tags`（リスト）を受け取る
- `tags` が空の場合は即座に `HourEstimate(avg_actual_hours=None, task_count=0)` を返す
- 実装ファイル: `src/api/routers/tasks_crud.py` 末尾に追加
- 認証必須（`CurrentUser` 依存）

### Pydantic モデル（`src/models/task_web.py`）

```python
class HourEstimate(BaseModel):
    avg_actual_hours: float | None
    task_count: int
```

### クエリロジック

```python
similar_ids = (
    select(TaskTag.task_id)
    .where(TaskTag.tag.in_(tags))
    .distinct()
)
agg = await db.execute(
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
```

---

## フロントエンド

### 新フック `useEstimateHours(tags: string[])`

- ファイル: `frontend/src/hooks/useTasks.ts` 末尾に追加
- `tags` が空配列なら fetch しない（`enabled: tags.length > 0`）
- `staleTime: 2 * 60 * 1000`（2分キャッシュ）
- `queryKey: ['tasks', 'estimate-hours', tags]`

### タスク作成モーダル（`frontend/src/pages/Tasks/index.tsx`）

#### 追加フィールド

フォームに `estimated_hours` 数値フィールドを追加（任意入力）:
```tsx
<Form.Item name="estimated_hours" label="予定工数（h）">
  <InputNumber min={0} step={0.5} style={{ width: '100%' }} placeholder="例: 2.0" />
</Form.Item>
```

#### 推奨工数バッジ

タグフィールドの下（`estimated_hours` フィールドの上）に表示:

- `task_count >= 1` かつ `avg_actual_hours != null`:
  ```tsx
  <Tag color="blue" style={{ cursor: 'pointer' }} onClick={() => form.setFieldValue('estimated_hours', avg)}>
    🤖 推奨工数: {avg}h（過去{task_count}件）
  </Tag>
  ```
- `task_count === 0` またはタグ未入力:
  ```tsx
  <Tag color="default">🤖 データ不足（0件）</Tag>
  ```

#### フォームの tags 値監視

```tsx
const watchedTags = Form.useWatch('tags', form) ?? []
const { data: estimate } = useEstimateHours(watchedTags)
```

---

## テスト

`tests/unit/test_estimate_hours.py` に 5件:

| テストケース | 期待値 |
|------------|-------|
| タグ一致あり・完了タスク → avg と task_count | avg > 0, task_count >= 1 |
| タグ一致なし → | task_count: 0 |
| タグ空リスト → | task_count: 0 |
| 進行中タスクは集計対象外 | task_count: 0 |
| 複数タグで OR 検索 | いずれか一致タスクが集計される |

---

## 非機能要件

- DB クエリは1本のみ（N+1 なし）
- Gemini API 不使用（蓄積データのみ）
- TypeScript strict モード準拠・Pydantic v2 型ヒント必須
- `tags` が空のときはフロントエンド側で fetch 自体をスキップ（不要なリクエストなし）

---

## 実装ファイルまとめ

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `src/models/task_web.py` | 修正 | `HourEstimate` モデル追加 |
| `src/api/routers/tasks_crud.py` | 修正 | `GET /estimate-hours` エンドポイント追加 |
| `tests/unit/test_estimate_hours.py` | 新規 | 5件のユニットテスト |
| `frontend/src/lib/api.ts` | 修正 | `HourEstimate` 型追加 |
| `frontend/src/hooks/useTasks.ts` | 修正 | `useEstimateHours` フック追加 |
| `frontend/src/pages/Tasks/index.tsx` | 修正 | `estimated_hours` フィールド・推奨工数バッジ追加 |
