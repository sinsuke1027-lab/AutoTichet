# AutoTicket — DB定義書

最終更新: 2026-05-02  
フェーズ: Phase 1 実装中

---

## 1. DB選定方針

| 用途 | 採用DB | 理由 |
|------|--------|------|
| 処理済みメッセージID管理 | SQLite（aiosqlite） | 軽量・Docker不要・KVS用途（重複防止）に最適 |
| タスク本体の永続化 | Microsoft Planner / To Do | Graph API 経由でM365テナント内に保管 |
| 監査ログ・LLM呼び出し履歴 | Langfuse（PostgreSQL） | Docker で社内完結、Langfuse 組み込みスキーマを使用 |

SQLite のデータファイルは `data/processed.db` に配置し、`.gitignore` で除外する。

---

## 2. Phase 1 テーブル（SQLite）

### 2-1. `processed_messages`

処理済みメッセージIDを記録し、ポーリング時の重複処理を防止するテーブル。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| `message_id` | TEXT | PRIMARY KEY | Graph API が返すメッセージ固有ID（重複防止キー） |
| `source_type` | TEXT | NOT NULL | 入力ソース種別（下表参照） |
| `processed_at` | TEXT | NOT NULL | 処理完了日時（ISO 8601 UTC 形式 例: `2026-05-02T09:00:00Z`） |

**`source_type` 許容値:**

| 値 | 説明 |
|----|------|
| `email` | Outlook メール |
| `meeting` | Teams 会議文字起こし |
| `chat` | Teams チャットメッセージ（Phase 2〜） |
| `onenote` | OneNote ページ（Phase 2〜） |
| `teams_bot` | Teamsボット経由（Phase 3〜） |

**DDL:**

```sql
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id  TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    processed_at TEXT NOT NULL
);
```

**インデックス:**  
`message_id` が PRIMARY KEY のため、追加インデックスは不要。

**利用パターン:**

```sql
-- 処理済みかチェック
SELECT 1 FROM processed_messages WHERE message_id = :message_id;

-- 処理完了を記録
INSERT OR IGNORE INTO processed_messages (message_id, source_type, processed_at)
VALUES (:message_id, :source_type, :processed_at);
```

---

## 3. 将来テーブル（Phase 5〜6 で追加予定）

Phase 5 以降でカスタムUIとの連携が必要になった時点で追加する。Planner / To Do で管理できない情報のみ SQLite に持つ方針。

### 3-1. `milestones`（Phase 6: マイルストーン管理）

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `title` | TEXT | NOT NULL | マイルストーン名 |
| `due_date` | TEXT | NOT NULL | 期限（ISO 8601 UTC） |
| `plan_id` | TEXT | NOT NULL | 紐付く Planner の Plan ID |
| `created_at` | TEXT | NOT NULL | 作成日時（ISO 8601 UTC） |

```sql
CREATE TABLE IF NOT EXISTS milestones (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    due_date   TEXT NOT NULL,
    plan_id    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

### 3-2. `task_dependencies`（Phase 6: タスク依存関係）

タスク間の先行後続関係を管理し、ガントチャート上に矢印で可視化する。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `task_id` | TEXT | NOT NULL | 後続タスクの Planner タスクID |
| `depends_on_task_id` | TEXT | NOT NULL | 先行タスクの Planner タスクID |
| `created_at` | TEXT | NOT NULL | 作成日時（ISO 8601 UTC） |

```sql
CREATE TABLE IF NOT EXISTS task_dependencies (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL,
    depends_on_task_id  TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    UNIQUE (task_id, depends_on_task_id)
);
```

### 3-3. `user_profiles`（Phase 7: スキルセット・ロール管理）

最適アサイン提案（Phase 7 FR）のためにユーザーのスキル・担当件数を管理する。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| `user_id` | TEXT | PRIMARY KEY | Graph API の `id`（AAD オブジェクトID） |
| `display_name` | TEXT | NOT NULL | 表示名 |
| `skills` | TEXT | NOT NULL | スキルタグのJSON配列（例: `["Python","Azure"]`） |
| `role` | TEXT | NOT NULL | ロール（`engineer` / `manager` / `designer` 等） |
| `updated_at` | TEXT | NOT NULL | 最終更新日時（ISO 8601 UTC） |

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id      TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    skills       TEXT NOT NULL,
    role         TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
```

---

## 4. マイグレーション方針

- Phase 1 では `aiosqlite` で直接 DDL を実行（`CREATE TABLE IF NOT EXISTS`）。
- Phase 5 以降でテーブルが増えた場合は `alembic` の導入を検討する。
- テーブル定義変更時は `ALTER TABLE` でカラム追加し、削除は行わない（後方互換性を保つ）。

---

## 5. データファイルの管理

```
data/
└── processed.db   # SQLite DBファイル（.gitignore 除外済み）
```

アプリ起動時に `src/services/state.py` の `init_db()` を呼び出し、テーブルが存在しない場合のみ DDL を実行する。本番データはバックアップ対象とし、`data/` ディレクトリごとバックアップする。
