# タスク手動並び替え機能 設計書

**作成日**: 2026-06-03
**ステータス**: 確定

---

## 目的

タスク一覧（`/tasks`）とボード（`/board`）で、タスクをドラッグ＆ドロップで手動並び替えできるようにする。
並び替えはセクション内スコープで永続化される。フィルタ適用中でも動作する。

---

## アーキテクチャ方針

- **フラクショナルインデックス方式**: 移動先の前後タスクの `order_index` 中間値を1件だけ更新
- `Task.order_index` を `Integer` → `Float` に変更（Alembic マイグレーション）
- バックエンド: `PATCH /api/v1/tasks/{task_id}/order` を新規追加
- フロントエンド: `@dnd-kit/sortable`（既導入）を両ページに適用
- 楽観的更新で UI は即座に反応、エラー時はロールバック

---

## データモデル変更

### `Task.order_index`

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| 型 | `Integer` | `Float` |
| デフォルト | `0` | `0.0` |

### マイグレーション処理

1. `order_index` カラムを `FLOAT` に変更
2. 既存タスクをセクション内 `created_at` 昇順で `1000.0, 2000.0, 3000.0, ...` に再採番
3. セクションなし（`section_id IS NULL`）のタスクはプロジェクト内で同様に採番

---

## バックエンド設計

### 新規エンドポイント

#### `PATCH /api/v1/tasks/{task_id}/order`

**リクエストボディ:**

```json
{
  "before_id": "uuid | null",
  "after_id": "uuid | null"
}
```

| フィールド | 説明 |
|-----------|------|
| `before_id` | 新位置のひとつ前のタスク ID（先頭移動なら `null`） |
| `after_id` | 新位置のひとつ後のタスク ID（末尾移動なら `null`） |

**処理フロー:**

1. `task_id` のタスクを取得（なければ 404）
2. `before_id` / `after_id` が指定されている場合は各タスクの `order_index` を取得
3. 新 `order_index` を計算:
   - `before_id` と `after_id` 両方あり → `(before.order_index + after.order_index) / 2.0`
   - `before_id` のみ（末尾移動）→ `before.order_index + 1000.0`
   - `after_id` のみ（先頭移動）→ `after.order_index - 1000.0`
   - 両方 `null`（単独タスク）→ `1000.0`
4. 差が `0.001` 未満なら再採番: 同セクション全タスクを `order_index` 昇順で `1000.0, 2000.0, ...` に更新してから再計算
5. タスクの `order_index` を更新
6. `204 No Content` を返す

**モデル:**

```python
class TaskReorderRequest(BaseModel):
    before_id: uuid.UUID | None = None
    after_id: uuid.UUID | None = None
```

**実装ファイル:** `src/api/routers/tasks_crud.py`（`GET /{task_id}` の前に配置）

---

## フロントエンド設計

### 共通: `useReorderTask` フック

**ファイル:** `frontend/src/hooks/useTasks.ts`

```typescript
interface ReorderTaskParams {
  taskId: string
  beforeId: string | null
  afterId: string | null
}

export function useReorderTask(): UseMutationResult<void, Error, ReorderTaskParams>
```

- `api.patch('/tasks/{taskId}/order', { before_id, after_id })` を呼び出す
- `onSuccess`: `queryClient.invalidateQueries(['tasks'])`
- 楽観的更新はページ側で管理

**API 関数:** `frontend/src/lib/api.ts` に `reorderTask` を追加

---

### タスク一覧（`Tasks/index.tsx`）

**変更内容:**

1. `@dnd-kit/core` から `DndContext`, `DragEndEvent`, `PointerSensor`, `useSensor` をインポート
2. `@dnd-kit/sortable` から `SortableContext`, `useSortable`, `verticalListSortingStrategy`, `arrayMove` をインポート
3. ドラッグハンドル列をテーブル左端に追加（幅 40px、`HolderOutlined` アイコン）
4. `DraggableRow` コンポーネントを追加:
   - `useSortable(id)` で行をドラッグ可能にする
   - `transform`・`transition` スタイルを適用
5. `DndContext` で Table をラップ、`SortableContext` に現在の `dataSource` の ID 列を渡す
6. `onDragEnd` で `arrayMove` でローカル state を更新し、`useReorderTask.mutate` を呼び出す
7. エラー時は元の順序に戻す（ロールバック）

---

### ボード（`Board/index.tsx`）

**変更内容:**

1. 各カラムの `SortableContext` を追加（既存の `DndContext` はカラム間移動用として維持）
2. `onDragEnd` で判定を追加:
   - ドロップ先が同一カラム → `useReorderTask` でカラム内並び替え
   - ドロップ先が別カラム → 既存のステータス更新処理（変更なし）
3. カード（`TaskCard`）に `useSortable` を適用

---

## 影響範囲

| ファイル | 変更種別 |
|---------|---------|
| `src/db/models.py` | `Task.order_index`: `Integer` → `Float` |
| `alembic/versions/xxxx_task_order_index_float.py` | マイグレーション新規作成 |
| `src/api/routers/tasks_crud.py` | `PATCH /{task_id}/order` エンドポイント追加 |
| `src/models/task_web.py` | `TaskReorderRequest` モデル追加 |
| `frontend/src/lib/api.ts` | `reorderTask` 関数追加 |
| `frontend/src/hooks/useTasks.ts` | `useReorderTask` フック追加 |
| `frontend/src/pages/Tasks/index.tsx` | ドラッグハンドル列・`DndContext` 追加 |
| `frontend/src/pages/Board/index.tsx` | カラム内 `SortableContext` 追加 |
| `tests/unit/test_task_reorder.py` | 新規作成（5件） |

---

## テスト計画（5件）

| # | テストケース | 期待結果 |
|---|-------------|---------|
| 1 | セクション中間へ移動（before/after 両方あり） | `(before + after) / 2.0` で更新、204 |
| 2 | 先頭移動（`before_id=null`） | `after.order_index - 1000.0` で更新、204 |
| 3 | 末尾移動（`after_id=null`） | `before.order_index + 1000.0` で更新、204 |
| 4 | 再採番トリガー（差 < 0.001） | セクション全タスクが 1000.0 刻みに正規化されてから中間値で更新 |
| 5 | 存在しない `task_id` | 404 |

テストファイル: `tests/unit/test_task_reorder.py`

---

## スコープ外

- プロジェクト間をまたいだ並び替え
- セクション間でのドラッグ移動（ボードの別カラムへのドロップは既存のステータス更新で対応）
- 並び替え順序のエクスポート（CSV エクスポートは `due_date` ソートで対応済み）
- タッチデバイスでのドラッグ（`PointerSensor` は対応するが動作保証外）
