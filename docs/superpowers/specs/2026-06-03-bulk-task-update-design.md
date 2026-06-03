# タスク一括操作 設計書

> **For agentic workers:** この設計書を実装する際は `superpowers:writing-plans` スキルで実装計画を作成してから着手すること。

**Goal:** タスク一覧でチェックボックス複数選択 → ステータス/担当者を一括変更できる機能を追加する。一括削除は対象外。

**Architecture:** バックエンドに `PATCH /api/v1/tasks/bulk` を1本追加し、フロントエンドはテーブルに `rowSelection` と固定表示の一括操作バーを追加する。既存の D&D 並び替えとは独立して動作する。

**Tech Stack:** React 18 + TypeScript + Ant Design 5.x + TanStack Query 5.x / FastAPI + SQLAlchemy 2.x + Pydantic v2

---

## 1. 方針

| 項目 | 決定 |
|------|------|
| 一括操作の種類 | ステータス変更・担当者変更のみ（削除は除外） |
| チェックボックスと D&D | 共存（rowSelection と DraggableRow は独立） |
| UI 表示タイミング | 1件以上選択時に画面下部固定バーを表示 |
| 原子性 | バックエンドで1トランザクション一括更新 |
| 権限 | 権限のないタスクが1件でも含まれていたら 403 |

---

## 2. バックエンド

### 2-1. 新規 Pydantic モデル

`src/models/task_web.py` の末尾（`# --- Weekly Summary ---` の前）に追加:

```python
class TaskBulkUpdate(BaseModel):
    task_ids: list[uuid.UUID]
    status: TaskStatus | None = None
    assignee_id: str | None = None
```

制約: `task_ids` は 1〜100件（バリデーションはエンドポイント側で行う）。`status` と `assignee_id` は両方 `None` の場合はバリデーションエラー。

### 2-2. 新規エンドポイント

`PATCH /api/v1/tasks/bulk` を `src/api/routers/tasks_crud.py` に追加。

**処理フロー:**

1. `task_ids` が空または 100件超 → 422
2. `status` と `assignee_id` が両方 `None` → 422
3. `SELECT ... WHERE id IN (task_ids)` で一括取得
4. 権限チェック: 各タスクが `current_user.sub` のもの、または `manager`/`admin` ロール。1件でも権限不足があれば **403**
5. 各タスクに `status` / `assignee_id` を設定（`exclude_unset` 相当: 指定されたフィールドのみ更新）
6. `status` が `completed`/`cancelled` になるタスクには `_spawn_next_recurrence` を適用
7. `await db.commit()`
8. レスポンス: `{"updated_count": N}`

**Response モデル（`task_web.py` に追加）:**

```python
class BulkUpdateResponse(BaseModel):
    updated_count: int
```

### 2-3. テスト

`tests/unit/test_bulk_update.py` に 4件追加:

| テスト名 | 内容 |
|---------|------|
| `test_bulk_status_update` | 複数タスクのステータスを一括変更 → 200・updated_count 確認 |
| `test_bulk_assignee_update` | 担当者を一括変更 → 200・updated_count 確認 |
| `test_bulk_forbidden_task` | 権限のないタスクが混在 → 403 |
| `test_bulk_unauthenticated` | 認証なし → 401 |

---

## 3. フロントエンド

### 3-1. ファイル構成

```
# 変更するファイル
frontend/src/lib/api.ts              ← TaskBulkUpdate 型・bulkUpdateTasks 関数追加
frontend/src/hooks/useTasks.ts       ← useBulkUpdateTasks フック追加
frontend/src/pages/Tasks/index.tsx   ← rowSelection・一括操作バー追加
```

### 3-2. `api.ts` 追加

```typescript
export interface TaskBulkUpdate {
  task_ids: string[]
  status?: string | null
  assignee_id?: string | null
}

export async function bulkUpdateTasks(body: TaskBulkUpdate): Promise<{ updated_count: number }> {
  const { data } = await api.patch<{ updated_count: number }>('/tasks/bulk', body)
  return data
}
```

### 3-3. `useTasks.ts` 追加

```typescript
export function useBulkUpdateTasks() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: TaskBulkUpdate) => bulkUpdateTasks(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
```

### 3-4. `Tasks/index.tsx` 変更点

**状態追加:**

```typescript
const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
const [bulkStatus, setBulkStatus] = useState<string | undefined>()
const [bulkAssignee, setBulkAssignee] = useState<string | undefined>()
const bulkUpdate = useBulkUpdateTasks()
```

**`<Table>` に `rowSelection` を追加:**

```tsx
rowSelection={{
  selectedRowKeys,
  onChange: (keys) => setSelectedRowKeys(keys as string[]),
}}
```

**一括操作バー（`selectedRowKeys.length > 0` のとき表示）:**

```tsx
{selectedRowKeys.length > 0 && (
  <div style={{
    position: 'fixed', bottom: 0, left: 0, right: 0,
    background: '#fff', borderTop: '1px solid #f0f0f0',
    padding: '12px 24px', zIndex: 100,
    display: 'flex', alignItems: 'center', gap: 12,
    boxShadow: '0 -2px 8px rgba(0,0,0,0.08)',
  }}>
    <Typography.Text strong>{selectedRowKeys.length}件選択中</Typography.Text>
    <Select
      placeholder="ステータスを変更"
      allowClear
      style={{ width: 160 }}
      options={STATUS_OPTIONS.filter(o => o.value)}
      value={bulkStatus}
      onChange={setBulkStatus}
    />
    <Select
      placeholder="担当者を変更"
      allowClear
      style={{ width: 160 }}
      options={users.map(u => ({ label: u.display_name, value: u.user_id }))}
      value={bulkAssignee}
      onChange={setBulkAssignee}
    />
    <Button
      type="primary"
      loading={bulkUpdate.isPending}
      disabled={!bulkStatus && !bulkAssignee}
      onClick={() => void handleBulkApply()}
    >
      適用
    </Button>
    <Button onClick={() => {
      setSelectedRowKeys([])
      setBulkStatus(undefined)
      setBulkAssignee(undefined)
    }}>
      選択解除
    </Button>
  </div>
)}
```

**`handleBulkApply` 関数:**

```typescript
const handleBulkApply = async () => {
  try {
    const res = await bulkUpdate.mutateAsync({
      task_ids: selectedRowKeys,
      ...(bulkStatus ? { status: bulkStatus } : {}),
      ...(bulkAssignee ? { assignee_id: bulkAssignee } : {}),
    })
    void message.success(`${res.updated_count}件を更新しました`)
    setSelectedRowKeys([])
    setBulkStatus(undefined)
    setBulkAssignee(undefined)
  } catch {
    void message.error('一括更新に失敗しました')
  }
}
```

---

## 4. 変更しないもの

| 対象 | 理由 |
|------|------|
| `PATCH /tasks/{id}` | 単体更新は既存のまま |
| D&D 並び替えロジック | rowSelection と独立して動作 |
| `DELETE /tasks/{id}` | 一括削除は今回対象外 |
