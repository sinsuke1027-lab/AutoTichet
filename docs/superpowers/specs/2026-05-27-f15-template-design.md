# F-15 テンプレート機能 設計書

**最終更新:** 2026-05-27  
**ステータス:** 承認済み  
**対応要件:** F-15「定型業務を雛形として登録し、一括作成」（Should / Phase 2）

---

## 1. 概要

定型業務（月次報告・週次レビューなど）をテンプレートとして登録し、適用時にメインタスク＋サブタスク群を一括作成する機能。

**ユースケース例:**
- 「月次報告テンプレート」を適用 → 基準日から相対日数で期限が設定されたタスクとサブタスクが即作成される

---

## 2. データモデル

### 2-1. `task_templates` テーブル（既存 + `updated_at` 追加）

```
id              UUID PK
name            Text     テンプレート名
description     Text?    説明
template_data   JSON     テンプレート本体（後述）
created_by      Text     作成者 user_id
created_at      DateTime
updated_at      DateTime  ← Alembic 0005 で追加
```

### 2-2. `template_data` JSON スキーマ

```json
{
  "title": "月次報告書作成",
  "description": "毎月末に提出する報告書",
  "priority": "medium",
  "visibility": "team",
  "tags": ["報告書", "月次"],
  "estimated_hours": 2.0,
  "due_date_offset_days": 3,
  "subtasks": [
    { "title": "データ収集",      "priority": "medium", "due_date_offset_days": 1 },
    { "title": "資料作成",        "priority": "medium", "due_date_offset_days": 2 },
    { "title": "上長レビュー依頼", "priority": "high",   "due_date_offset_days": 3 }
  ]
}
```

- `due_date_offset_days`: 適用時の基準日（`base_date`）からの加算日数
- `subtasks[].due_date_offset_days`: サブタスクの期限オフセット（メインタスクと独立）
- `base_date` 未指定時は今日の日付を使用

### 2-3. Pydantic モデル（`src/models/task_web.py` に追加）

```python
class TemplateSubtask(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    due_date_offset_days: int = 0

class TemplateData(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    visibility: str = "team"
    tags: list[str] = []
    estimated_hours: float | None = None
    due_date_offset_days: int = 0
    subtasks: list[TemplateSubtask] = []

class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    template_data: TemplateData

class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    template_data: TemplateData | None = None

class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    template_data: TemplateData
    created_by: str
    created_at: datetime
    updated_at: datetime

class TemplateApplyRequest(BaseModel):
    base_date: date | None = None   # None の場合は today
    project_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    assignee_id: str | None = None

class TemplateApplyResponse(BaseModel):
    task_id: uuid.UUID
    subtask_ids: list[uuid.UUID]
```

---

## 3. バックエンド API

新規ルーター: `src/api/routers/templates.py`

| メソッド | パス | 概要 | 認可 |
|---------|------|------|------|
| GET | `/api/v1/templates` | 一覧取得 | 全認証済みユーザー |
| POST | `/api/v1/templates` | 新規作成 | 全認証済みユーザー |
| GET | `/api/v1/templates/{id}` | 詳細取得 | 全認証済みユーザー |
| PUT | `/api/v1/templates/{id}` | 更新 | 作成者 or admin |
| DELETE | `/api/v1/templates/{id}` | 削除 | 作成者 or admin |
| POST | `/api/v1/templates/{id}/apply` | テンプレート適用（タスク一括作成） | 全認証済みユーザー |

### `/apply` の動作詳細

1. `base_date` が未指定なら `date.today()` を使用
2. メインタスクを作成:
   - `title`, `description`, `priority`, `visibility` を `template_data` から取得
   - `due_date = base_date + timedelta(days=due_date_offset_days)`
   - `assignee_id`, `project_id`, `section_id` はリクエストから上書き
   - `tags` は `TaskTag` レコードとして作成
3. 各サブタスクを作成:
   - `parent_task_id = メインタスクの id`
   - `due_date = base_date + timedelta(days=subtask.due_date_offset_days)`
4. レスポンス: `{ task_id, subtask_ids }`

### 認可ロジック

- PUT / DELETE: `template.created_by == current_user.sub` または `"admin" in current_user.roles`
- 違反時: HTTP 403

---

## 4. Alembic マイグレーション

`alembic/versions/0005_add_template_updated_at.py`

```python
op.add_column(
    "task_templates",
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
)
```

---

## 5. フロントエンド

### 5-1. 新規ページ `/templates`

**ファイル:** `frontend/src/pages/Templates/index.tsx`

- テンプレート一覧をカード形式で表示（名前・サブタスク数・作成者）
- 「新規作成」ボタン → 右側ドロワーでフォームを開く
- 各カードに「編集」「削除」ボタン（`created_by === userId` or `admin` のみ有効）
- フォーム内ではサブタスクを動的追加・削除できるリスト

**フォームフィールド:**
- テンプレート名（必須）
- 説明（任意）
- タスク本体: タイトル・説明・優先度・公開範囲・タグ・予定工数・期限オフセット日数
- サブタスクリスト: 各行にタイトル・優先度・期限オフセット日数

### 5-2. タスク作成画面への統合

**ファイル:** 既存の `frontend/src/pages/Tasks/index.tsx` または TaskCreate コンポーネント

タスク一覧ページ（`frontend/src/pages/Tasks/index.tsx`）の「新規タスク作成」フォームを開くドロワー/モーダルに「テンプレートから作成」タブまたはセクションを追加する。既存のタスク作成フォームの構造を読んで、最も自然に統合できる位置に配置すること:

1. テンプレート選択 `<Select>` （`useTemplates()` で取得）
2. 基準日 `<DatePicker>`（デフォルト: 今日）
3. 「このテンプレートで作成」ボタン → `POST /templates/{id}/apply`
4. 成功後: 作成されたメインタスク詳細ページ（`/tasks/{task_id}`）へ遷移

### 5-3. フック (`frontend/src/hooks/useTemplates.ts` 新規)

```typescript
useTemplates()           // GET /templates 一覧
useCreateTemplate()      // POST /templates
useUpdateTemplate()      // PUT /templates/{id}
useDeleteTemplate()      // DELETE /templates/{id}
useApplyTemplate()       // POST /templates/{id}/apply
```

### 5-4. サイドバーへの追加

`frontend/src/App.tsx` の `NAV_ITEMS` に追加:
```typescript
{ key: '/templates', label: 'テンプレート', icon: <FileTextOutlined /> }
```

---

## 6. テスト方針

**バックエンド** (`tests/unit/test_templates.py`):
- `GET /templates` — 一覧取得（認証必須）
- `POST /templates` — 作成成功
- `PUT /templates/{id}` — 作成者は更新可・他ユーザーは 403
- `DELETE /templates/{id}` — 作成者は削除可・他ユーザーは 403
- `POST /templates/{id}/apply` — メインタスク + サブタスクが作成される
- `POST /templates/{id}/apply`（base_date 未指定）— today が使われる

**フロントエンド:** TypeScript 型チェック（`npx tsc --noEmit`）のみ。

---

## 7. 実装スコープ外

- テンプレートのカテゴリ分類・検索
- テンプレートの公開範囲制御（全員共有のみ）
- テンプレートからのインポート/エクスポート
