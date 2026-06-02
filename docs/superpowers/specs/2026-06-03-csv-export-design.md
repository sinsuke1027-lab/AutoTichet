# タスク CSV エクスポート機能 設計書

**作成日**: 2026-06-03
**ステータス**: 確定

---

## 目的

タスク一覧ページの現在フィルタ条件を適用した全件を CSV でダウンロードできるようにする。
Excel で開いた際に文字化けしないよう UTF-8 BOM 付きで出力する。

---

## アーキテクチャ方針

- バックエンド主体: `GET /api/v1/tasks/export/csv` で CSV を直接生成して返す
- Python 標準ライブラリ `csv` + `io.StringIO` を使用（依存追加なし）
- ページネーションなし（フィルタに合致する全件を返す）
- `src/api/routers/tasks_crud.py` に追記（新規ファイル不要）

---

## バックエンド設計

### 新規エンドポイント

#### `GET /api/v1/tasks/export/csv`

**クエリパラメータ:** `list_tasks` と同一

| パラメータ | 型 | デフォルト |
|-----------|-----|----------|
| `status` | `str \| None` | `None` |
| `project_id` | `UUID \| None` | `None` |
| `section_id` | `UUID \| None` | `None` |
| `assignee_id` | `str \| None` | `None` |
| `keyword` | `str \| None` | `None` |
| `my_tasks_only` | `bool` | `False` |
| `include_archived_projects` | `bool` | `False` |

**処理フロー:**
1. `list_tasks` と同じクエリロジックでタスクを全件取得（LIMIT/OFFSET なし）
2. `io.StringIO` に BOM (`﻿`) を書き込んでから `csv.writer` で各行を出力
3. `StreamingResponse` で返す

**レスポンス:**
- ステータス: 200
- `Content-Type: text/csv; charset=utf-8`
- `Content-Disposition: attachment; filename=tasks_YYYYMMDD.csv`（ファイル名は実行日付）

### CSV 列定義（20列）

| # | ヘッダー | ソース |
|---|---------|--------|
| 1 | ID | `task.id` |
| 2 | タイトル | `task.title` |
| 3 | ステータス | `task.status` |
| 4 | 優先度 | `task.priority` |
| 5 | 担当者 | `task.assignee_id` |
| 6 | サブ担当者 | `task.sub_assignees`（カンマ区切り） |
| 7 | 開始日 | `task.start_date` |
| 8 | 期限日 | `task.due_date` |
| 9 | 完了日時 | `task.completed_at` |
| 10 | プロジェクト名 | `project.name`（LEFT JOIN） |
| 11 | セクション名 | `section.name`（LEFT JOIN） |
| 12 | タグ | `task.tags`（カンマ区切り） |
| 13 | 説明 | `task.description` |
| 14 | 見積工数(h) | `task_work_hours.estimated_hours`（最初の1件） |
| 15 | 実績工数(h) | `task_work_hours.actual_hours`（最初の1件） |
| 16 | リスクレベル | `_compute_risk_level(task)` を再利用 |
| 17 | 信頼スコア | `task.confidence_score` |
| 18 | ソース種別 | `task.source_type` |
| 19 | 作成日時 | `task.created_at` |
| 20 | 更新日時 | `task.updated_at` |

### クエリ実装方針

`list_tasks` の既存クエリを流用し、以下を変更する:
- `LIMIT` / `OFFSET` を削除（全件取得）
- `selectinload(Task.tags_rel)` / `selectinload(Task.assignees)` / `selectinload(Task.work_hours)` を維持
- LEFT OUTER JOIN で `Project.name`・`Section.name` を取得

---

## フロントエンド設計

### 変更ファイル

`frontend/src/pages/Tasks/index.tsx`

**変更内容:**
1. `DownloadOutlined` を `@ant-design/icons` からインポート追加
2. フィルタ行右端に「CSVエクスポート」ボタン追加
3. クリック時の処理:
   - 現在の `statusFilter`, `projectFilter`, `sectionFilter`, `assigneeFilter`, `keyword`（searchQ）, `myTasksOnly`, `includeArchivedProjects` を URLSearchParams でクエリ文字列化
   - `window.open('/api/v1/tasks/export/csv?' + params, '_blank')` でダウンロードを発火

**注意:** 認証トークンは axios インターセプターが付与しているが `window.open` はそれを通らない。
→ `<a href>` タグを動的生成して `click()` する方式を採用（Cookie ベース認証でない場合はトークンをクエリパラメータに付与する必要がある）。

実際の実装: `api.get('/tasks/export/csv', { params, responseType: 'blob' })` で blob を取得し、`URL.createObjectURL` + 動的 `<a>` でダウンロードを発火する。これにより Authorization ヘッダーが送信される。

---

## 影響範囲

| ファイル | 変更種別 |
|---------|---------|
| `src/api/routers/tasks_crud.py` | `GET /tasks/export/csv` エンドポイント追加 |
| `frontend/src/pages/Tasks/index.tsx` | CSVエクスポートボタン追加 |
| `tests/unit/test_task_csv_export.py` | 新規作成（5件） |

---

## テスト計画（5件）

| # | テストケース | 期待結果 |
|---|-------------|---------|
| 1 | 正常リクエスト | 200, `Content-Type: text/csv` |
| 2 | Content-Disposition ヘッダー | `attachment; filename=tasks_YYYYMMDD.csv` |
| 3 | BOM 付き UTF-8 | レスポンスボディ先頭が `﻿` |
| 4 | `status=completed` フィルタ | completed タスクのみ出力 |
| 5 | アーカイブ済みプロジェクトのタスクをデフォルト除外 | 除外確認 |

テストファイル: `tests/unit/test_task_csv_export.py`

---

## スコープ外

- Excel（.xlsx）形式での出力（標準の CSV で十分）
- 非同期ジョブ化（件数が少ないため不要）
- エクスポート履歴の記録
- プロジェクト単位のエクスポート（タスク一覧のフィルタで代替可能）
