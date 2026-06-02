# プロジェクトアーカイブ機能 設計書

**作成日**: 2026-06-02
**ステータス**: 確定

---

## 目的

完了・凍結したプロジェクトをアーカイブし、一覧・タスク一覧から非表示にする。
長期運用で増えるプロジェクト・タスクの視認性を保つ。

---

## アーキテクチャ方針

- **DB スキーマ変更なし** — 既存の `Project.status: String(20)` 列を利用
  - `"active"` = 通常（デフォルト）
  - `"archived"` = アーカイブ済み
- Alembic マイグレーション不要

---

## バックエンド設計

### 新規エンドポイント

#### `PATCH /api/v1/projects/{project_id}/archive`
- 対象プロジェクトの `status` を `"archived"` に変更
- **権限**: `project.created_by == current_user.sub` または `user_role >= ROLE_HIERARCHY["leader"]`
- 権限なし → 403
- プロジェクト不存在 → 404
- レスポンス: `ProjectResponse`（200）

#### `PATCH /api/v1/projects/{project_id}/unarchive`
- 対象プロジェクトの `status` を `"active"` に変更
- 権限・エラー処理は archive と同一
- レスポンス: `ProjectResponse`（200）

### 既存エンドポイント変更

#### `GET /api/v1/projects`
- クエリパラメータ `include_archived: bool = False` を追加
- デフォルト（`false`）: `WHERE status != 'archived'` を適用
- `?include_archived=true`: 全件返す

#### `GET /api/v1/tasks`
- アーカイブ済みプロジェクトのタスクをデフォルトで除外
- 実装: `Task.project_id` が NULL でない場合のみ `JOIN projects WHERE projects.status != 'archived'` を適用
  - `project_id IS NULL`（個人 ToDo 等）は影響なし
- クエリパラメータ `include_archived_projects: bool = False` を追加
  - `true` の場合は JOIN を省略して全件返す

---

## フロントエンド設計

### プロジェクト一覧ページ（`frontend/src/pages/Projects/List.tsx`）

**変更点:**
1. カード右上に Ant Design `Dropdown`（`...` アイコン）を追加
   - メニュー項目: 「アーカイブ」 / 「アーカイブ解除」（status により切り替え） / 「削除」
2. アーカイブ済みカードの表示
   - `opacity: 0.5` でグレーアウト
   - カードタイトルに `<Tag color="default">アーカイブ済み</Tag>` バッジ表示
3. ページ上部フィルター行に `<Switch>` 「アーカイブ済みを表示」追加（デフォルト OFF）

### タスク一覧ページ（`frontend/src/pages/Tasks/index.tsx`）

**変更点:**
1. フィルター行に `<Switch>` 「アーカイブ済みプロジェクトを含む」追加（デフォルト OFF）
2. `useTasks` フックに `include_archived_projects` パラメータを渡す

### フック（`frontend/src/hooks/useProjects.ts`）

追加フック:
- `useArchiveProject()` — `PATCH /projects/{id}/archive` の mutation
- `useUnarchiveProject()` — `PATCH /projects/{id}/unarchive` の mutation
- `useProjects(includeArchived?: boolean)` — 既存フックに `include_archived` クエリパラメータ追加

---

## 権限マトリクス

| 操作 | member（非作成者） | member（作成者） | leader 以上 |
|------|:-----------------:|:---------------:|:-----------:|
| アーカイブ | ❌ 403 | ✅ | ✅ |
| アーカイブ解除 | ❌ 403 | ✅ | ✅ |

---

## テスト計画（6 件）

| # | テストケース | 期待結果 |
|---|-------------|---------|
| 1 | 作成者が archive → status = "archived" | 200 |
| 2 | 作成者が unarchive → status = "active" | 200 |
| 3 | 非作成者の member が archive → | 403 |
| 4 | leader が他人のプロジェクトを archive → | 200 |
| 5 | `GET /projects`（デフォルト）→ アーカイブ済みプロジェクトが含まれない | 200 |
| 6 | `GET /projects?include_archived=true` → アーカイブ済みも含まれる | 200 |

テストファイル: `tests/unit/test_project_archive.py`

---

## 影響範囲

| ファイル | 変更種別 |
|---------|---------|
| `src/api/routers/projects.py` | PATCH /archive・/unarchive 追加、GET に include_archived 追加 |
| `src/api/routers/tasks_crud.py` | GET /tasks に include_archived_projects フィルタ追加 |
| `frontend/src/hooks/useProjects.ts` | useArchiveProject / useUnarchiveProject フック追加 |
| `frontend/src/hooks/useTasks.ts` | include_archived_projects パラメータ追加 |
| `frontend/src/lib/api.ts` | archiveProject / unarchiveProject 関数追加 |
| `frontend/src/pages/Projects/List.tsx` | Dropdown メニュー・Switch・グレーアウト表示追加 |
| `frontend/src/pages/Tasks/index.tsx` | include_archived_projects Switch 追加 |
| `tests/unit/test_project_archive.py` | 新規作成（6 件） |

---

## スコープ外

- タスクの自動完了（要件定義で除外済み）
- アーカイブ日時の記録（status フィールド利用のため不要）
- アーカイブ済みプロジェクトの完全削除（既存 DELETE エンドポイントで対応可能）
