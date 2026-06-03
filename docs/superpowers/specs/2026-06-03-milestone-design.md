# マイルストーン設定 設計書

> **For agentic workers:** この設計書を実装する際は `superpowers:writing-plans` スキルで実装計画を作成してから着手すること。

**Goal:** プロジェクト詳細ページに横軸タイムラインでマイルストーンを表示し、作成・編集・削除・手動完了マークができる機能を追加する。

**Architecture:** バックエンドは既存 `milestones` テーブルに `completed`/`completed_at` を追加し、CRUD + 完了トグル の 5 エンドポイントを新規ルーターとして追加する。フロントエンドはプロジェクト詳細ページのセクション一覧上部にカスタム CSS タイムラインコンポーネントを追加する。

**Tech Stack:** React 18 + TypeScript + Ant Design 5.x + TanStack Query 5.x / FastAPI + SQLAlchemy 2.x + Pydantic v2 + Alembic

---

## 1. 方針

| 項目 | 決定 |
|------|------|
| UI 形式 | 横軸タイムラインバー（ひし形マーカー） |
| 達成判定 | 手動（「完了」トグルボタン） |
| 操作範囲 | 作成・編集（タイトル・期日）・削除・完了マーク |
| タスクとの関係 | 独立（マイルストーンはタスクに紐づけない） |
| 配置 | プロジェクト詳細ページのセクション一覧の上部 |
| 権限（変更） | プロジェクト作成者 or `leader` ロール以上 |
| 権限（閲覧） | 全認証済みユーザー |
| 外部ライブラリ | 追加なし（カスタム CSS + Ant Design のみ） |

---

## 2. バックエンド

### 2-1. DB マイグレーション（Alembic 0008）

`milestones` テーブルに 2 列追加:

```sql
ALTER TABLE milestones ADD COLUMN completed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE milestones ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;
```

SQLAlchemy モデル (`src/db/models.py`) の `Milestone` クラスに追加:

```python
completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 2-2. Pydantic モデル

`src/models/task_web.py` の末尾（`# --- Weekly Summary ---` の前）に追加:

```python
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

### 2-3. 新規ルーター

`src/api/routers/milestones.py` を新規作成。`src/api/main.py` に `include_router` 追加。

**エンドポイント一覧:**

| メソッド | パス | 機能 | ステータス |
|---------|------|------|---------|
| GET | `/api/v1/projects/{project_id}/milestones` | 一覧（due_date 昇順） | 200 |
| POST | `/api/v1/projects/{project_id}/milestones` | 作成 | 201 |
| PUT | `/api/v1/projects/{project_id}/milestones/{milestone_id}` | タイトル・期日編集 | 200 |
| PATCH | `/api/v1/projects/{project_id}/milestones/{milestone_id}/complete` | 完了トグル | 200 |
| DELETE | `/api/v1/projects/{project_id}/milestones/{milestone_id}` | 削除 | 204 |

**処理フロー（共通）:**

1. `project_id` でプロジェクトを SELECT → 存在しなければ 404
2. 変更系操作: `project.created_by == current_user.sub` または `user_role >= ROLE_HIERARCHY["leader"]` → 不満足なら 403
3. マイルストーン操作実行
4. `await db.commit()`

**完了トグル詳細:**

```python
if milestone.completed:
    milestone.completed = False
    milestone.completed_at = None
else:
    milestone.completed = True
    milestone.completed_at = datetime.now(UTC)
```

### 2-4. テスト

`tests/unit/test_milestones_router.py` に 5 件:

| テスト名 | 内容 |
|---------|------|
| `test_list_milestones` | 一覧取得 → 200・due_date 昇順 |
| `test_create_milestone` | 作成 → 201・レスポンス確認 |
| `test_update_milestone` | タイトル・期日編集 → 200 |
| `test_toggle_complete` | 完了トグル → 200・completed=True / 再トグルで False |
| `test_delete_milestone` | 削除 → 204 |

---

## 3. フロントエンド

### 3-1. ファイル構成

```
# 新規作成
frontend/src/hooks/useMilestones.ts
frontend/src/pages/Projects/MilestoneTimeline.tsx

# 変更
frontend/src/lib/api.ts              ← Milestone 型・API 関数追加
frontend/src/pages/Projects/index.tsx ← MilestoneTimeline を組み込む
```

### 3-2. `api.ts` 追加

```typescript
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

export async function updateMilestone(projectId: string, milestoneId: string, body: MilestoneUpdate): Promise<Milestone> {
  const { data } = await api.put<Milestone>(`/projects/${projectId}/milestones/${milestoneId}`, body)
  return data
}

export async function toggleMilestoneComplete(projectId: string, milestoneId: string): Promise<Milestone> {
  const { data } = await api.patch<Milestone>(`/projects/${projectId}/milestones/${milestoneId}/complete`)
  return data
}

export async function deleteMilestone(projectId: string, milestoneId: string): Promise<void> {
  await api.delete(`/projects/${projectId}/milestones/${milestoneId}`)
}
```

### 3-3. `useMilestones.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  type Milestone, type MilestoneCreate, type MilestoneUpdate,
  getMilestones, createMilestone, updateMilestone,
  toggleMilestoneComplete, deleteMilestone,
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

### 3-4. `MilestoneTimeline.tsx`

**Props:** `projectId: string`

**タイムライン軸の計算:**
- 期日の最小値 − 7日 〜 最大値 + 7日 を横軸範囲とする
- マイルストーンが0件の場合: 「マイルストーンはまだありません」+ 追加ボタンのみ表示
- 各マーカーの left 位置 = `(due_date - rangeStart) / (rangeEnd - rangeStart) * 100` %

**マーカー色:**
- `completed = true` → 緑（`#52c41a`）
- `completed = false` かつ `due_date >= 今日` → 青（`#1677ff`）
- `completed = false` かつ `due_date < 今日` → 赤（`#ff4d4f`）

**インタラクション:**
- マーカーホバー: `Tooltip`（タイトル・期日・残日数 or "期限超過N日"）
- マーカークリック: 編集 Modal を開く
  - タイトル Input・DatePicker・完了チェックボックス・削除 Popconfirm ボタン
- 「＋ マイルストーン追加」ボタン: 作成 Modal を開く
  - タイトル Input・DatePicker

### 3-5. `Projects/index.tsx` 変更点

```tsx
import MilestoneTimeline from './MilestoneTimeline'

// セクション一覧の上部に追加
<MilestoneTimeline projectId={projectId} />
```

---

## 4. 変更しないもの

| 対象 | 理由 |
|------|------|
| `milestones` テーブルの既存列 | `id`, `project_id`, `title`, `due_date`, `created_at` はそのまま |
| タスク・サブタスク | マイルストーンとは独立 |
| プロジェクト CRUD | 既存エンドポイントは変更なし |
