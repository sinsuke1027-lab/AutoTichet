# Web App Phase 2B-1 — マルチビュー設計書

最終更新: 2026-05-19
ステータス: 承認済み

---

## 1. 概要

**Goal:** カンバン・カレンダー・ガントの 3 ビューを独立ページとして追加し、プロジェクト管理と個人 ToDo の可視化を強化する。F-36 自動リスケジュールをガントと一体で実装する。

**対象機能:** F-11（D&D）, F-22（マルチビュー）, F-23（依存関係可視化）, F-36（リスケジュール）

**前提:** Web App Phase 2A 完了 ✅

---

## 2. アーキテクチャ方針

既存の `GET /api/v1/tasks` に期間フィルタを追加して 3 ビュー共通のデータソースとして使い回す（専用エンドポイントは作らない）。F-36 リスケジュールのみ `POST /tasks/{id}/reschedule` を新設し、バックエンドで依存グラフを BFS 走査して一括更新する。

---

## 3. DB スキーマ変更

### Alembic 0003

`tasks` テーブルに `start_date DATE NULL` を追加。既存行はすべて NULL。

```sql
ALTER TABLE tasks ADD COLUMN start_date DATE NULL;
```

downgrade: `ALTER TABLE tasks DROP COLUMN start_date`

---

## 4. バックエンド API

### 4-1. 既存エンドポイント拡張

#### `src/models/task_web.py`

`TaskCreate`・`TaskUpdate`・`TaskResponse` に以下を追加:

```python
start_date: date | None = None
```

#### `GET /api/v1/tasks`（`src/api/routers/tasks_crud.py`）

新規クエリパラメータ:

| パラメータ | 型 | 説明 |
|-----------|---|------|
| `due_date_gte` | `date \| None` | 期限日 以上でフィルタ（カレンダー・ガントの期間始端） |
| `due_date_lte` | `date \| None` | 期限日 以下でフィルタ（カレンダー・ガントの期間終端） |
| `assignee_ids` | `list[str] \| None` | 複数担当者で OR フィルタ（カレンダーの Multi-Select 対応）。`Query(default=None)` で繰り返しパラメータとして受け取る |

実装: `Task.due_date >= due_date_gte` / `Task.due_date <= due_date_lte` を条件に追加。`assignee_ids` 指定時は `Task.assignee_id.in_(assignee_ids)` を追加。

### 4-2. 新規エンドポイント

#### `POST /api/v1/tasks/{task_id}/reschedule`

```
src/api/routers/tasks_crud.py に追加
```

**リクエストボディ:**

```python
class RescheduleRequest(BaseModel):
    new_start_date: date | None = None
    new_due_date: date
```

**処理フロー:**

1. 対象タスクの `start_date` / `due_date` を更新
2. `task_dependencies` テーブルから「このタスクを `depends_on_task_id` に持つ」タスクを取得
3. BFS で依存グラフを走査
4. 各依存タスクの期間（`due_date - start_date`）を保ちながら `start_date` / `due_date` を push
5. 更新された全タスクを返す

**レスポンス:**

```python
class RescheduleResponse(BaseModel):
    updated_tasks: list[TaskResponse]
```

**エラー:** 循環依存は `task_dependencies` の UniqueConstraint と自己参照チェックで防止済み（Phase 2A 実装）。

---

## 5. フロントエンド

### 5-1. 新規ページ・ルート

| ルート | ファイル | 説明 |
|-------|--------|------|
| `/board` | `frontend/src/pages/Board/index.tsx` | カンバンビュー |
| `/calendar` | `frontend/src/pages/Calendar/index.tsx` | カレンダービュー |
| `/gantt` | `frontend/src/pages/Gantt/index.tsx` | ガントチャート |

`App.tsx` のサイドバー（Sider Menu）にボード・カレンダー・ガントの 3 項目を追加。

### 5-2. 新規フック

| フック | ファイル | 役割 |
|-------|--------|-----|
| `useTasksForView(filters)` | `frontend/src/hooks/useTasksForView.ts` | 3 ビュー共通タスク取得。`due_date_gte`/`lte`・`project_id`・`assignee_id`（複数）対応 |
| `useReschedule()` | `frontend/src/hooks/useReschedule.ts` | `POST /tasks/{id}/reschedule` mutation。レスポンスの `updated_tasks` でキャッシュ更新 |

### 5-3. 追加ライブラリ

```json
"@dnd-kit/core": "^6.x",
"@dnd-kit/sortable": "^8.x",
"react-big-calendar": "^1.x",
"date-fns": "^3.x",
"gantt-task-react": "^0.x"
```

### 5-4. `frontend/src/lib/api.ts` 追加インターフェース

```typescript
export interface RescheduleRequest {
  new_start_date?: string | null  // ISO date
  new_due_date: string
}

export interface RescheduleResponse {
  updated_tasks: Task[]
}
```

また `Task` インターフェースに `start_date?: string | null` を追加。

---

## 6. 各ビュー詳細設計

### 6-1. カンバンビュー（`/board`）

**構成:**
- 上部: プロジェクト Select（任意）
- デフォルト: ステータス 4 列（`not_started`・`in_progress`・`in_review`・`completed`）
- プロジェクト選択時: そのプロジェクトのセクションをカラムに切り替え（`useSections` 流用）

**タスクカード表示項目:** タイトル・期限（`due_date`）・優先度バッジ（色分け）・担当者アバター（イニシャル）

**D&D 実装:**
- `@dnd-kit/core` の `DndContext` + `@dnd-kit/sortable` の `SortableContext`
- カラム間ドロップ: ステータス列なら `PATCH /tasks/{id}` で `status` 更新、セクション列なら `section_id` 更新
- 空カラム: `useDroppable` でドロップ可能に設定

**データ取得:** `useTasksForView({ project_id?, status? })` → カラムごとにフィルタしてカード表示

### 6-2. カレンダービュー（`/calendar`）

**構成:**
- 上部フィルタ: プロジェクト Select + 担当者 Multi-Select（`useUsers` 流用）
  - デフォルト: ログイン中ユーザーのみ選択
- 月次ビュー固定（`react-big-calendar` の `views={['month']}`）

**イベント表示:**
- `start_date` + `due_date` 両方あり → 期間バー（allDay イベント）
- `due_date` のみ → 1 日点イベント（allDay・当日のみ）

**色分け:**
- 担当者ごとにユーザー ID をハッシュして固有色を生成（HSL で彩度・明度を固定、色相のみ変化）
- 期限超過タスク（`due_date < today` かつ未完了）は担当者色に関わらず赤で上書き

**タスク密度ヒートマップ:**
- `dateCellWrapper` カスタムコンポーネントで実装
- その日のタスク数（表示中担当者全体）に応じてセル背景色を変化（0 件=white, 1-2=`#e6f4ff`, 3-5=`#91caff`, 6+=`#1677ff` 薄め）
- 担当者フィルタ変更時にタスク数を再計算

**溢れ制御:** `react-big-calendar` の自動「+N 件」折り畳み（デフォルト動作）

**クリック:** `onSelectEvent` → `/tasks/{id}` へ遷移

**データ取得:** `useTasksForView({ due_date_gte: 月初, due_date_lte: 月末, assignee_id: 選択中ユーザー[] })`

### 6-3. ガントチャート（`/gantt`）

**構成:**
- 上部: プロジェクト Select（**必須**。未選択時は選択を促すメッセージを表示）
- `gantt-task-react` の `Gantt` コンポーネントを使用

**バー表示:**
- `start_date` + `due_date` あり → バー幅 = 期間
- `start_date` なし → `due_date` 当日のみの 1 日バー（`start = due_date`）

**D&D（日程変更）:**
- `gantt-task-react` の `onDateChange` コールバック
- バーをドラッグ後: `PATCH /tasks/{id}` で `start_date` / `due_date` を更新
- 更新後: `POST /tasks/{id}/reschedule` を呼び、レスポンスの `updated_tasks` でキャッシュを一括更新（F-36）

**依存関係矢印:**
- `gantt-task-react` の `dependencies` prop に `task_dependencies` データを渡して矢印描画
- 矢印は Finish-to-Start（前タスクの終了 → 後タスクの開始）

**依存関係の追加・削除:**
- タスク行にホバーすると表示される操作ボタン（追加・削除）
- 追加: 依存先タスクを Select で選択 → `POST /tasks/{id}/dependencies`
- 削除: 操作ボタンから依存関係一覧を表示し選択削除 → `DELETE /tasks/{id}/dependencies/{dep_id}`

**F-36 自動リスケジュール:**
- ガントでバーを移動すると `onDateChange` が発火
- `PATCH /tasks/{id}` で自タスクを更新後、`POST /tasks/{id}/reschedule` を呼ぶ
- レスポンスの `updated_tasks` で TanStack Query キャッシュを `setQueryData` で一括置換
- UI はキャッシュ更新により即座に再描画

---

## 7. テスト方針

### バックエンド（pytest）

| テストファイル | 内容 |
|-------------|------|
| `tests/unit/test_tasks_crud_router.py` | `due_date_gte`/`lte` フィルタが正しく機能すること |
| `tests/unit/test_reschedule.py` | reschedule エンドポイント: 単一タスク・依存チェーン・依存なし の 3 ケース |

### フロントエンド（TypeScript チェック）

`npx tsc -b --noEmit` でエラー 0 を確認（Vitest は別途）

---

## 8. ファイル構成まとめ

### 新規作成

```
alembic/versions/0003_add_start_date.py
tests/unit/test_reschedule.py
frontend/src/pages/Board/index.tsx
frontend/src/pages/Calendar/index.tsx
frontend/src/pages/Gantt/index.tsx
frontend/src/hooks/useTasksForView.ts
frontend/src/hooks/useReschedule.ts
```

### 変更

```
src/db/models.py                    ← Task に start_date 列追加
src/models/task_web.py              ← start_date・RescheduleRequest/Response 追加
src/api/routers/tasks_crud.py       ← due_date_gte/lte・assignee_ids フィルタ・reschedule エンドポイント追加
frontend/src/lib/api.ts             ← start_date・RescheduleRequest/Response 追加
frontend/src/App.tsx                ← サイドバーに /board・/calendar・/gantt 追加
frontend/src/hooks/useTasks.ts      ← due_date_gte/lte・assignee_ids パラメータ追加
```

---

## 9. 非機能要件への対応

| NFR | 対応 |
|----|------|
| NFR-03 操作性 | D&D はすべて `@dnd-kit` でアクセシブルに実装。ガントのバー移動後は即座に UI 反映 |
| NFR-04 性能 | カンバン・カレンダーは期間・プロジェクトでフィルタして取得量を絞る。ガントはプロジェクト選択必須 |
| NFR-05 型安全 | TypeScript strict + verbatimModuleSyntax。Python mypy --strict |
| NFR-07 非同期 | 全 DB 操作は async/await。reschedule の BFS も async |
