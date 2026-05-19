# Web App Phase 2A — タスク詳細 UI 完成 設計書

**作成日:** 2026-05-19
**ステータス:** 確定
**対象フェーズ:** Web App Phase 2A（Group A）

---

## 1. 概要

### 目的
Phase 1 で構築したバックエンド API（コメント・工数・依存関係・サブタスク）を活用し、フロントエンド UI を完成させる。あわせて、Asana からの既存タスクデータ移行を可能にする。

### スコープ
| 分類 | 内容 |
|------|------|
| DB追加 | `sections` テーブル、`task_assignees` テーブル、`tasks` テーブルに4列追加 |
| バックエンド API | Section CRUD、task_assignees CRUD、Asana インポート、タスク複製、キーワード検索 |
| フロントエンド | タスク詳細タブ拡張、プロジェクト一覧/詳細、サイドバー、Asana インポートウィザード |

### スコープ外（Phase 2B 以降）
- カンバン/ガント/カレンダービュー（F-22, F-23）
- AI 補助機能（F-27〜32）
- D&D による並び替え UI（order_index の DB/API は今回追加）
- Teams 通知連動（F-21）

---

## 2. データモデル

### 2-1. 新規テーブル

#### `sections`
```sql
CREATE TABLE sections (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    order_index INTEGER     NOT NULL DEFAULT 0,
    created_at  TIMESTAMP   NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP   NOT NULL DEFAULT now()
);
```

#### `task_assignees`
```sql
CREATE TABLE task_assignees (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id    UUID        NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id    VARCHAR(255) NOT NULL,   -- Entra ID objectId
    role       VARCHAR(10)  NOT NULL DEFAULT 'sub',  -- 'main' | 'sub'
    created_at TIMESTAMP   NOT NULL DEFAULT now(),
    UNIQUE(task_id, user_id)
);
```

### 2-2. 既存テーブル変更（`tasks`）
| 列 | 型 | デフォルト | 説明 |
|----|----|-----------|------|
| `section_id` | UUID NULL | NULL | FK → sections(id) SET NULL |
| `external_id` | VARCHAR(100) NULL | NULL | Asana Task ID など外部システムID。再インポート重複防止に使用 |
| `completed_at` | TIMESTAMP NULL | NULL | 実際の完了日時（Asana の Completed At をそのまま保持） |
| `order_index` | INTEGER | 0 | セクション内でのタスク並び順 |

---

## 3. Asana データマッピング

| Asana 列 | AutoTicket フィールド | 備考 |
|----------|----------------------|------|
| Task ID | tasks.external_id | 再インポート重複チェックに使用 |
| Name（Parent task 空） | tasks.title | セクション内トップレベルタスク |
| Name（Parent task あり） | tasks.title + parent_task_id | サブタスク |
| Section/Column | sections.name | プロジェクト内セクション |
| Assignee Email | task_assignees (role='main') | 未登録ユーザーは警告してスキップ |
| サブ担当者（カンマ区切りメール） | task_assignees (role='sub') | 複数可 |
| Due Date | tasks.due_date | |
| Start Date | tasks.start_date | |
| Completed At（空でない） | tasks.status='completed' + tasks.completed_at | |
| 優先度（最高/高/中/低/空） | urgent / high / medium / low / medium | |
| Notes | tasks.description | |
| Tags | task_tags | |
| Blocked By | task_dependencies.depends_on_task_id | インポート後に名前→ID 解決 |
| Created At | tasks.created_at | インポート時に上書き |

---

## 4. バックエンド API

### 4-1. Section CRUD

| メソッド | パス | 概要 | 認証 |
|---------|------|------|------|
| GET | `/api/v1/projects/{id}/sections` | セクション一覧（order_index 昇順） | 認証済み全員 |
| POST | `/api/v1/projects/{id}/sections` | セクション作成 | 認証済み全員 |
| PUT | `/api/v1/projects/{id}/sections/{section_id}` | 名前・order_index 変更 | 認証済み全員 |
| DELETE | `/api/v1/projects/{id}/sections/{section_id}` | 削除（タスクの section_id は NULL に） | 認証済み全員 |
| PATCH | `/api/v1/projects/{id}/sections/reorder` | 並び順一括更新 `[{id, order_index}]` | 認証済み全員 |

**SectionCreate:**
```json
{ "name": "残業管理", "order_index": 0 }
```

**SectionResponse:**
```json
{ "id": "uuid", "project_id": "uuid", "name": "残業管理", "order_index": 0, "created_at": "...", "updated_at": "..." }
```

### 4-2. Task Assignees CRUD

| メソッド | パス | 概要 |
|---------|------|------|
| GET | `/api/v1/tasks/{id}/assignees` | 担当者一覧（main + sub） |
| POST | `/api/v1/tasks/{id}/assignees` | サブ担当者追加 `{ user_id, role="sub" }` |
| DELETE | `/api/v1/tasks/{id}/assignees/{user_id}` | サブ担当者削除 |

※ メイン担当者は既存の `PUT /api/v1/tasks/{id}` の `assignee_id` で変更（変更なし）

**TaskAssigneeResponse:**
```json
{ "id": "uuid", "task_id": "uuid", "user_id": "entra-oid", "role": "sub" }
```

### 4-3. Asana インポート

| メソッド | パス | 概要 |
|---------|------|------|
| POST | `/api/v1/import/asana/preview` | xlsx アップロード → プレビュー返却（DB書き込みなし）。`multipart/form-data` で xlsx を受け取る |
| POST | `/api/v1/import/asana/confirm` | xlsx を再度アップロードしてDB投入。`multipart/form-data` で xlsx を受け取る（サーバーサイドに状態を持たないシンプルな設計） |

**ImportPreviewResponse:**
```json
{
  "file_name": "総務関連.xlsx",
  "projects": [{ "name": "総務関連", "will_create": true }],
  "sections": [{ "project": "総務関連", "name": "よく知るVORN", "task_count": 8 }],
  "tasks": { "total": 45, "completed": 32, "with_subtasks": 12, "with_dependencies": 3 },
  "warnings": ["tomoyo-ishikawa@vorn.co.jp はシステムに未登録のため assignee は空になります"]
}
```

**ImportResult:**
```json
{
  "created_tasks": 45, "created_sections": 3, "skipped_duplicates": 0,
  "errors": []
}
```

重複チェック: `external_id` が一致するタスクは既存タスクを更新せずスキップ。

### 4-4. タスク複製

| メソッド | パス | 概要 |
|---------|------|------|
| POST | `/api/v1/tasks/{id}/duplicate` | タスクを複製して新規タスク返却 |

複製時の動作:
- title に `"（コピー）"` を付与
- status = `not_started` にリセット
- completed_at = NULL にリセット
- created_by = 複製実行ユーザーの sub に設定
- サブタスク・コメント・工数履歴は複製しない
- 以下は引き継ぐ: description, priority, assignee_id, due_date, start_date, visibility, project_id, section_id, tags, sub_assignees（task_assignees）

### 4-5. 既存 API 変更

**`GET /api/v1/tasks`** — クエリパラメータ追加:
- `q: str | None` — title・description に対する ILIKE 検索（PostgreSQL の `ILIKE '%keyword%'`）
- `section_id: UUID | None` — セクションフィルタ

**`POST /api/v1/tasks`・`PUT /api/v1/tasks/{id}`** — フィールド追加:
- `section_id: UUID | None`

**`TaskResponse`** — フィールド追加:
- `section_id: UUID | None`
- `completed_at: datetime | None`
- `order_index: int`
- `sub_assignees: list[str]` — role='sub' のユーザー一覧

**`GET /api/v1/users`** — ロール制限を撤廃し、認証済みユーザー全員がアクセス可能にする

---

## 5. バックエンド ファイル構成

### 新規作成
```
alembic/versions/0002_sections_task_assignees.py
src/api/routers/sections.py        — Section CRUD
src/api/routers/import_router.py   — Asana インポート
src/services/asana_importer.py     — Excel解析・マッピングロジック（openpyxl 使用）
```

**依存パッケージ追加（pyproject.toml）:**
- `openpyxl>=3.1` — Excel (.xlsx) 読み込み用

### 変更
```
src/db/models.py          — Section, TaskAssignee ORM モデル追加・Task 列追加
src/models/task_web.py    — SectionCreate/Response, TaskAssigneeCreate/Response, ImportPreviewResponse, ImportResult 追加
                            TaskCreate/Update に section_id 追加
                            TaskResponse に section_id/completed_at/order_index/sub_assignees 追加
src/api/routers/tasks_crud.py   — q 検索・section_id フィルタ追加・duplicate エンドポイント追加
src/api/routers/task_details.py — task_assignees エンドポイント追加
src/api/routers/users.py        — ロール制限撤廃
src/api/main.py                 — sections_router, import_router 登録
```

---

## 6. フロントエンド

### 6-1. ルーティング・ナビゲーション更新（`App.tsx`）

**新規ルート:**
- `/projects` → プロジェクト一覧
- `/projects/:id` → プロジェクト詳細（セクション管理）
- `/import` → Asana インポートウィザード

**サイドバー（Ant Design `Sider`）追加:**
```
🏠 ダッシュボード     /
✅ タスク一覧         /tasks
📁 プロジェクト       /projects
📅 スケジュール       /schedule
👥 ワークロード       /workload
⬆️ データインポート   /import
```

### 6-2. タスク詳細ページ拡張（`/tasks/:id`）

現行の Descriptions カード 1 枚 → **Ant Design Tabs** に変更:

```
[ 詳細 | コメント (N) | 工数 | サブタスク (N) ]
```

**詳細タブ:**
- 既存の Descriptions（ステータス・優先度・期限・公開範囲・タグ）
- 担当者フィールド: メイン担当者 Select + サブ担当者チップ（追加・削除可）
- section_id: セクション Select
- 「複製」ボタン（タスク詳細右上に追加）

**コメントタブ（`CommentsPanel.tsx`）:**
- コメント一覧（投稿者アバター・本文・日時・時系列順）
- テキストエリア投稿フォーム + 送信ボタン

**工数タブ（`WorkHoursPanel.tsx`）:**
- 予定工数・実績工数の入力フォーム（Number Input）
- 登録履歴一覧（記録日時・予定・実績・メモ）

**サブタスクタブ（`SubtasksPanel.tsx`）:**
- サブタスク一覧（完了チェックボックス + タイトル + ステータス Tag）
- インライン新規作成（タイトル入力 + Enter で作成）

### 6-3. プロジェクト一覧ページ（`/projects`）

```
[+ プロジェクト作成]

┌─────────────────────────────┐
│ 総務関連           進行中    │
│ タスク 45件                 │
└─────────────────────────────┘
┌─────────────────────────────┐
│ 人事関連           進行中    │
│ タスク 12件                 │
└─────────────────────────────┘
```

### 6-4. プロジェクト詳細ページ（`/projects/:id`）

```
[プロジェクト名]  [+ セクション追加]

▼ よく知るVORN  [編集] [削除]
  ☐ タスクA   石川   2026/01/31   高
  ☐ タスクB   —      —            中
  [+ タスクを追加]

▼ まぜ飯  [編集] [削除]
  ...

▽ セクションなし
  ...
```

- セクション: Ant Design `Collapse`
- タスク行クリック → `/tasks/:id` 遷移
- 「+ タスクを追加」→ section_id 付きでタスク作成モーダル

### 6-5. タスク一覧ページ拡張（`/tasks`）

- 検索ボックス追加（Input with Search アイコン、Enter で `q=keyword` 検索）
- section_id フィルタ Select を追加（プロジェクト選択時に対応セクション動的表示）

### 6-6. Asana インポートウィザード（`/import`）

**Step 1: アップロード**
```
.xlsx ファイルをドロップするかクリックして選択
（Ant Design Upload / Dragger コンポーネント）
[プレビューを取得]
```

**Step 2: プレビュー**
```
インポート内容
  プロジェクト: 総務関連（新規作成）
  セクション: よく知るVORN (8タスク), まぜ飯 (5タスク), プロジェクト (32タスク)
  タスク合計: 45件（完了済み: 32件）
  サブタスク: 12件

⚠️ 警告:
  - tomoyo-ishikawa@vorn.co.jp は未登録のため担当者は空になります

[インポート実行]  [キャンセル]
```

**Step 3: 完了**
```
✅ インポート完了
  タスク 45件・セクション 3件 を作成しました
[プロジェクトを見る]  [別のファイルをインポート]
```

### 6-7. 新規フロントエンドファイル構成

```
frontend/src/
├── App.tsx                         変更: Sider追加・ルート追加
├── pages/
│   ├── Projects/
│   │   ├── List.tsx                新規: プロジェクト一覧
│   │   └── index.tsx               新規: プロジェクト詳細（セクション管理）
│   ├── Tasks/
│   │   ├── index.tsx               変更: 検索ボックス・section_idフィルタ追加
│   │   ├── TaskDetail.tsx          変更: Tabs構成に拡張・複製ボタン
│   │   └── components/
│   │       ├── CommentsPanel.tsx   新規
│   │       ├── WorkHoursPanel.tsx  新規
│   │       └── SubtasksPanel.tsx   新規
│   └── Import/
│       └── index.tsx               新規: Asana インポートウィザード
└── hooks/
    ├── useSections.ts              新規
    ├── useTaskAssignees.ts         新規
    └── useTaskDetails.ts           新規: コメント・工数・サブタスク
```

---

## 7. テスト方針

### バックエンド（pytest）
- `tests/unit/test_sections_router.py` — Section CRUD の 404・作成・削除
- `tests/unit/test_import.py` — Asana Excel解析ロジック（実ファイル不要、テスト用 xlsx を生成）
- `tests/unit/test_tasks_crud_router.py` — q 検索・section_id フィルタ・duplicate エンドポイント

### フロントエンド（Vitest + Testing Library）
- CommentsPanel: コメント一覧表示・投稿フォーム送信
- SubtasksPanel: サブタスク一覧・チェックボックス状態変更

---

## 8. 実装順序

```
Task 1: DBスキーマ追加（Alembic 0002）
Task 2: Pydantic モデル更新（task_web.py）
Task 3: Section CRUD バックエンド
Task 4: Task Assignees バックエンド + TaskResponse 拡張
Task 5: タスク複製・キーワード検索・section_id フィルタ
Task 6: ユーザー一覧 API ロール制限撤廃
Task 7: Asana インポートバックエンド（asana_importer.py + import_router.py）
Task 8: App.tsx サイドバー・ルーティング更新
Task 9: プロジェクト一覧・詳細ページ（Section UI）
Task 10: タスク詳細タブ拡張（コメント・工数・サブタスク・担当者）
Task 11: タスク一覧ページ拡張（検索・セクションフィルタ）
Task 12: Asana インポートウィザード（フロントエンド）
```
