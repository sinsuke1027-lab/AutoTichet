# 繰り返しタスク 設計書

## Goal

タスクに繰り返しルール（daily / weekly / monthly）を設定し、完了時または APScheduler による深夜バックフィルで次インスタンスを自動生成する。タスク一覧には「次の1件のみ」表示する。

## Architecture

`tasks` テーブルに3カラムを直接追加する（Alembic 0007）。生成ロジックは `_spawn_next_recurrence` ヘルパーに集約し、完了トリガーと APScheduler バックフィルの両方から呼ぶ。新規エンドポイントは `DELETE /tasks/{id}/recurrence` のみ。

## Tech Stack

- Backend: FastAPI + SQLAlchemy Async + APScheduler（既存）
- Frontend: React + Ant Design 5.x（既存）
- Migration: Alembic

---

## 1. DB・データモデル

### Alembic 0007: `tasks` テーブルへのカラム追加

```sql
ALTER TABLE tasks ADD COLUMN recurrence_rule VARCHAR(10) DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN recurrence_end_date DATE DEFAULT NULL;
ALTER TABLE tasks ADD COLUMN recurrence_origin_id UUID DEFAULT NULL
    REFERENCES tasks(id) ON DELETE SET NULL;
```

| カラム | 型 | NULL | 説明 |
|-------|-----|------|------|
| `recurrence_rule` | `VARCHAR(10)` | YES | `"daily"` / `"weekly"` / `"monthly"` / NULL（繰り返しなし） |
| `recurrence_end_date` | `DATE` | YES | この日付を超えたら次インスタンスを生成しない |
| `recurrence_origin_id` | `UUID` | YES | 連鎖の初代タスク ID。初代は `self.id`、2代目以降は初代の ID |

### SQLAlchemy モデル追加（`src/db/models.py`）

```python
recurrence_rule: Mapped[str | None] = mapped_column(String(10), default=None)
recurrence_end_date: Mapped[date | None] = mapped_column(Date, default=None)
recurrence_origin_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), default=None
)
```

### Pydantic モデル追加（`src/models/task_web.py`）

`TaskCreate` に追加：
```python
recurrence_rule: Literal["daily", "weekly", "monthly"] | None = None
recurrence_end_date: date | None = None
```

`TaskResponse` に追加：
```python
recurrence_rule: str | None = None
recurrence_end_date: date | None = None
recurrence_origin_id: uuid.UUID | None = None
```

`api.ts` の `Task` インターフェースに追加：
```typescript
recurrence_rule?: 'daily' | 'weekly' | 'monthly' | null
recurrence_end_date?: string | null
recurrence_origin_id?: string | null
```

---

## 2. バックエンドロジック

### `_spawn_next_recurrence` ヘルパー（`src/api/routers/tasks_crud.py`）

```python
async def _spawn_next_recurrence(task: Task, db: AsyncSession) -> None
```

**生成条件（すべて満たす場合のみ生成）：**
1. `task.recurrence_rule` が設定されている
2. 次の due_date を計算したとき `recurrence_end_date` が未設定 OR 次の due_date ≤ end_date
3. 同じ `recurrence_origin_id` を持つ status が `not_started` / `in_progress` のタスクが存在しない

**due_date 計算：**

| rule | interval |
|------|----------|
| daily | +1日（`timedelta(days=1)`） |
| weekly | +7日（`timedelta(days=7)`） |
| monthly | +1ヶ月（`dateutil.relativedelta.relativedelta(months=1)`） |

`start_date` が設定されている場合は同じ interval をずらす。

**新タスクの生成：**
- 元タスクの全フィールドをコピー（`title`, `description`, `priority`, `assignee_id`, `visibility`, `tags`, `project_id`, `section_id` など）
- `status = "not_started"`, `completed_at = None`
- `due_date` / `start_date` を interval 分ずらした値
- `recurrence_rule` / `recurrence_end_date` を引き継ぐ
- `recurrence_origin_id = task.recurrence_origin_id`（初代の ID を引き継ぐ）
- `order_index` は section 末尾（`max + 1000.0`）

### トリガー 1: 完了時即生成

`PUT /tasks/{id}` 内で `status` が `completed` または `cancelled` に変化した場合、`await _spawn_next_recurrence(task, db)` を呼ぶ。

### トリガー 2: APScheduler 深夜バックフィル

`src/api/main.py` に新ジョブを追加：

```python
scheduler.add_job(
    recurrence_backfill_job,
    "cron",
    hour=2, minute=0,
    timezone="Asia/Tokyo",
)
```

`recurrence_backfill_job` は `recurrence_rule IS NOT NULL` かつ `status IN ('completed', 'cancelled')` のタスクを全件取得し、後継未生成のものに対して `_spawn_next_recurrence` を呼ぶ。

---

## 3. API

### 既存エンドポイント拡張

**`POST /tasks`**
- `TaskCreate` に `recurrence_rule`・`recurrence_end_date` を受け付ける
- 作成後: `recurrence_rule` が設定されている場合、`task.recurrence_origin_id = task.id` にセット（自己参照）

**`PUT /tasks/{id}`**
- `status` が `completed` / `cancelled` に変化した場合、コミット前に `_spawn_next_recurrence` を呼ぶ

**`GET /tasks`**
- `TaskResponse` に `recurrence_rule`・`recurrence_end_date`・`recurrence_origin_id` を含める（既存フィールドへの追加のみ）

### 新規エンドポイント

**`DELETE /tasks/{id}/recurrence`**

繰り返しを解除する。対象タスクの `recurrence_rule`・`recurrence_end_date`・`recurrence_origin_id` を NULL にクリアする。過去インスタンスは変更しない。レスポンス: `204 No Content`。

---

## 4. フロントエンド UI

### タスク作成モーダル

「繰り返し」Select を due_date の下に追加：
```
繰り返し: [なし ▼]  →  [毎日 / 毎週 / 毎月]
終了日:   [日付選択]  ← 繰り返し選択時のみ表示
```

### タスク詳細（`TaskDetail.tsx`）

Descriptions の「期限日」行の下に追加：
- 繰り返し設定あり: `毎週 ／ 2026-12-31まで`（end_date 未設定時は `毎週`）
- 「繰り返しを解除」ボタン（Popconfirm 付き） → `DELETE /tasks/{id}/recurrence`

### タスク一覧（`Tasks/index.tsx`）

タイトル列に `<RedoOutlined />` アイコンを小さく表示（`recurrence_rule` が設定されているタスクのみ）。

---

## 5. テスト

`tests/unit/test_task_recurrence.py` に以下を実装：

1. `test_spawn_next_daily` — daily タスク完了時に翌日 due_date で新タスク生成
2. `test_spawn_next_weekly` — weekly タスク完了時に +7日で生成
3. `test_spawn_next_monthly` — monthly タスク完了時に +1ヶ月で生成
4. `test_no_spawn_after_end_date` — 次の due_date が end_date を超える場合は生成しない
5. `test_no_spawn_if_pending_exists` — 同 origin の未完了タスクがあれば生成しない
6. `test_delete_recurrence_endpoint` — `DELETE /tasks/{id}/recurrence` で3カラムが NULL になる
7. `test_create_task_sets_origin_id` — `POST /tasks` で recurrence_rule 設定時に origin_id が self.id になる
