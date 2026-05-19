# Web App Phase 2B-2 — ユーザー管理・権限制御・UX 強化 設計書

最終更新: 2026-05-20
ステータス: 承認済み

---

## 1. 概要

**Goal:** 部門タグ方式のユーザー管理・ロールベース閲覧制御・JWT-first/DB-fallback ハイブリッド認証を実装し、開発中は DB で直接ユーザーを管理しながら本番移行後は Entra ID App Roles に自動的に切り替わる基盤を作る。あわせて F-07 個人 ToDo・F-04 二重登録防止・F-11 スケジュール D&D の 3 機能を追加する。

**対象機能:** F-08（権限管理）、F-07（個人 ToDo）、F-04（二重登録防止）、F-11（スケジュール D&D）

**前提:** Web App Phase 2B-1 完了 ✅

---

## 2. アーキテクチャ方針

既存の `list_tasks` に可視性フィルタをインラインで追加するアプローチ（Approach A）を採用する。新規 Dependency や中間テーブルは設けず、`UserProfile.department_tags`（JSON カラム）と `auth.py` の拡張で完結させる。

---

## 3. DB スキーマ変更

### Alembic 0004

`user_profiles` テーブルに `department_tags` カラムを追加。

```sql
ALTER TABLE user_profiles
  ADD COLUMN department_tags JSON NOT NULL DEFAULT '[]';
```

downgrade: `ALTER TABLE user_profiles DROP COLUMN department_tags`

**`department_tags` の値例:**
```json
["営業部", "第一チーム", "関東エリア"]
```

タグは自由文字列のリスト。複数軸（部門・チーム・エリア等）を 1 カラムで表現する。

---

## 4. バックエンド

### 4-1. ハイブリッド認証拡張（`src/api/auth.py`）

#### 変更方針

`TokenPayload` に `department_tags: list[str]` フィールドを追加する。`get_current_user` 内で以下の順序でロールと部門タグを解決する：

```
1. JWT の roles クレームが 1 件以上ある
   → roles = JWT roles（Entra ID App Roles が設定済みの本番環境）
   → department_tags = DB の UserProfile.department_tags

2. JWT の roles クレームが空
   → roles = DB の UserProfile.role を list にラップ（開発環境）
   → department_tags = DB の UserProfile.department_tags
```

DB を参照する場合は `UserProfile` を `user_id（= JWT sub）` で SELECT し、存在しなければ roles=["member"]・department_tags=[] をデフォルトとして使う。

#### `TokenPayload` 変更

```python
class TokenPayload(BaseModel):
    sub: str
    name: str = ""
    email: str = ""
    roles: list[str] = []
    tid: str = ""
    department_tags: list[str] = []  # 追加
```

### 4-2. ロールベース閲覧制御（`src/api/routers/tasks_crud.py`）

`list_tasks` 関数の既存フィルタ群の末尾（`if assignee_ids:` の後）に追加：

```python
# ロールベース閲覧制御
user_role = max(
    (_ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
    default=0,
)
if user_role < _ROLE_HIERARCHY["manager"]:
    if user_role >= _ROLE_HIERARCHY["leader"]:
        # leader: 同じ department_tags を 1 つ以上持つユーザーのタスク + public
        if current_user.department_tags:
            assignee_sub_result = await db.execute(
                select(UserProfile.user_id).where(
                    UserProfile.department_tags.op("?|")(current_user.department_tags)
                )
            )
            dept_user_ids = [r for r in assignee_sub_result.scalars().all()]
            query = query.where(
                or_(
                    Task.assignee_id.in_(dept_user_ids),
                    Task.visibility == "public",
                )
            )
        else:
            query = query.where(Task.visibility == "public")
    else:
        # member: 自分のタスク + public
        query = query.where(
            or_(
                Task.assignee_id == current_user.sub,
                Task.visibility == "public",
            )
        )
# manager / admin はフィルタなし（全件）
```

**JSON の `?|` 演算子はPostgreSQL 固有。** SQLAlchemy の `func.jsonb_exists_any` を使う実装でも同等。

### 4-3. 管理 API（`src/api/routers/admin.py`）（新規）

```
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
AdminDep = Depends(require_role("admin"))
```

| メソッド | パス | 処理 |
|---------|------|------|
| `GET` | `/api/v1/admin/users` | ユーザー一覧（department_tags 含む） |
| `POST` | `/api/v1/admin/users` | ユーザー登録 |
| `PATCH` | `/api/v1/admin/users/{user_id}` | ロール・部門タグ更新 |
| `DELETE` | `/api/v1/admin/users/{user_id}` | ユーザー削除（論理削除なし、物理削除） |

#### Pydantic モデル（`src/models/task_web.py` に追加）

```python
class AdminUserCreate(BaseModel):
    user_id: str
    display_name: str
    email: str | None = None
    role: str = "member"
    department_tags: list[str] = []
    capacity_hours_per_day: float = 8.0

class AdminUserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    department_tags: list[str] | None = None
    capacity_hours_per_day: float | None = None

class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    display_name: str
    email: str | None
    role: str
    department_tags: list[str]
    capacity_hours_per_day: float
```

### 4-4. F-07 個人 ToDo フィルタ（`src/api/routers/tasks_crud.py`）

`list_tasks` に `my_tasks_only: bool = Query(default=False)` を追加：

```python
if my_tasks_only:
    query = query.where(
        Task.assignee_id == current_user.sub,
        Task.visibility == "private",
    )
```

### 4-5. F-04 二重登録防止（`src/api/routers/tasks_crud.py`）

新規エンドポイント：

```
GET /api/v1/tasks/similar?q={title}
```

処理：
1. `q` をスペース・句読点（`[　 、。，．・]` 等）で分割してトークンリストを作成
2. 各トークンに対して `Task.title.ilike(f'%{token}%')` を OR で結合して検索（最大 100 件）
3. タスクごとに一致トークン数 / 総トークン数でスコアを計算
4. スコア 0.5 以上のタスクを最大 5 件、スコア降順で返す

レスポンス：
```python
class SimilarTaskResponse(BaseModel):
    id: str
    title: str
    status: str
    score: float
```

---

## 5. フロントエンド

### 5-1. 新規ページ・ルート

| ルート | ファイル | 説明 |
|-------|--------|------|
| `/admin/users` | `frontend/src/pages/Admin/Users.tsx` | ユーザー管理（admin のみ） |

`App.tsx` のサイドバーに「ユーザー管理」項目を追加。admin ロールのユーザーにのみ表示する。

### 5-2. Admin Users ページ（`/admin/users`）

- **アクセス制御**: ログインユーザーが admin でなければ `/` へリダイレクト
- **テーブル列**: 氏名・メール・ロール・部門タグ・稼働時間/日・操作
- **編集モーダル**: ロール Select（member / leader / manager / admin）+ 部門タグ（`Select mode="tags"` で既存タグをサジェスト）
- **新規登録**: 同モーダルを使い回す（user_id・display_name・email は必須）
- **削除**: 確認 Popconfirm 後に DELETE

### 5-3. F-07 個人 ToDo UI（`/tasks` 既存ページ改修）

フィルタバーに `Switch`「自分の ToDo のみ」を追加。ON 時は `my_tasks_only=true` で再取得。OFF 時は通常フィルタに戻る。

### 5-4. F-04 二重登録防止 UI（タスク作成モーダル改修）

- タイトル `Input` の `onChange` に 500ms デバウンスを設定
- 3 文字以上で `GET /tasks/similar?q={title}` を呼ぶ
- 類似タスクが 1 件以上あれば入力欄の下に `Alert` を表示：
  ```
  ⚠️ 類似タスクが見つかりました（2件）
  ・[タスクタイトル A] (in_progress)
  ・[タスクタイトル B] (not_started)
  ```
- 警告は無視して作成ボタンを押すことも可能

### 5-5. F-11 スケジュール D&D（`/schedule` 既存ページ改修）

- 既存の `Schedule/index.tsx` に `@dnd-kit/core` の `DndContext` を追加
- タスクカードに `useDraggable`（ドラッグハンドルアイコン付き）
- 日付セルに `useDroppable`
- ドロップ時: `PATCH /tasks/{id}` で `start_date` のみ更新（`due_date` は変更しない）
- ドロップ先の日付セルはドラッグ中にハイライト（`isOver` 判定）

### 5-6. 新規フック

| フック | ファイル | 役割 |
|-------|--------|-----|
| `useAdminUsers()` | `frontend/src/hooks/useAdminUsers.ts` | ユーザー一覧取得 |
| `useCreateAdminUser()` | 同上 | ユーザー登録 |
| `useUpdateAdminUser()` | 同上 | ロール・部門タグ更新 |
| `useDeleteAdminUser()` | 同上 | ユーザー削除 |
| `useSimilarTasks(title)` | `frontend/src/hooks/useSimilarTasks.ts` | 類似タスク検索（デバウンス付き） |

---

## 6. テスト方針

### バックエンド（pytest）

| テストファイル | 内容 |
|-------------|------|
| `tests/unit/test_admin_router.py` | ユーザー CRUD・admin 権限チェック（非 admin は 403） |
| `tests/unit/test_visibility.py` | member/leader/manager 別の list_tasks 結果フィルタ |
| `tests/unit/test_similar_tasks.py` | スコア計算・0.5 未満は除外・最大 5 件 |

### フロントエンド

`npx tsc -b --noEmit` でエラー 0 を確認。

---

## 7. ファイル構成まとめ

### 新規作成

```
alembic/versions/0004_add_department_tags.py
src/api/routers/admin.py
tests/unit/test_admin_router.py
tests/unit/test_visibility.py
tests/unit/test_similar_tasks.py
frontend/src/pages/Admin/Users.tsx
frontend/src/hooks/useAdminUsers.ts
frontend/src/hooks/useSimilarTasks.ts
```

### 変更

```
src/db/models.py              ← UserProfile に department_tags 追加
src/api/auth.py               ← TokenPayload に department_tags 追加・DB fallback 実装
src/models/task_web.py        ← AdminUserCreate/Update/Response・SimilarTaskResponse 追加
src/api/routers/tasks_crud.py ← 閲覧制御・my_tasks_only・/similar エンドポイント追加
src/api/main.py               ← admin ルーター登録
frontend/src/lib/api.ts       ← AdminUser・SimilarTask 型追加
frontend/src/App.tsx          ← /admin/users ルート・サイドバー（admin のみ表示）追加
frontend/src/pages/Tasks/index.tsx  ← 個人 ToDo スイッチ追加
frontend/src/pages/Schedule/index.tsx ← D&D 実装
```

---

## 8. 非機能要件への対応

| NFR | 対応 |
|----|------|
| NFR-03 操作性 | D&D は dnd-kit（既導入）でアクセシブルに実装。類似タスク警告はノンブロッキング（無視して作成可能） |
| NFR-04 性能 | similar タスク検索は最大 100 件取得後にサーバー側でスコアリング。フロント側デバウンス 500ms で API 呼び出しを抑制 |
| NFR-05 型安全 | TypeScript strict + verbatimModuleSyntax。Python mypy --strict |
| NFR-07 非同期 | 全 DB 操作は async/await |

---

## 9. 移行戦略（開発 → 本番）

| ステップ | 作業 | 担当 |
|---------|------|------|
| 開発中 | DB の `UserProfile.role` / `department_tags` で動作確認 | 開発者 |
| 本番移行前 | Azure AD で App Roles（member/leader/manager/admin）を定義・割り当て | IT 管理者 |
| 本番移行後 | JWT に `roles` クレームが付くため自動的に JWT 優先に切り替わる | 自動 |
| 切り替え確認 | `GET /api/v1/users/me` の `roles` フィールドが JWT 由来になっていることを確認 | 開発者 |
