# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: Web App Phase 2B-6（F-30 遅延リスク予測・F-31 自動棚卸し提案）✅ 完了 → F-21 Teams 通知 or F-12 工数自動算出へ**
ステータス: F-30 リスクバッジ・F-31 棚卸しカード実装完了・Graph API 申請中（承認待ち）

## 最終更新
- **日付**: 2026-05-28
- **完了した作業**:
  - **[F-30 遅延リスク AI 予測]** `_compute_risk_level()` 純粋関数・`TaskResponse.risk_level`・タスク一覧バッジ（高リスク/要注意）
  - **[F-31 タスクの自動棚卸し提案]** `StaleTaskItem` モデル・`GET /dashboard/stale-tasks`・Dashboard 棚卸しカード・`useArchiveTask(PUT)` フック
  - テスト 13 件追加（`test_delay_risk.py` 8件・`test_stale_tasks.py` 5件）→ 合計 183 passed

- **完了した作業（前セッション）**:
  - **[F-29 タスク要件の明確化プロンプト — Gemini AI チェック]**
    - `GeminiProvider.clarify_requirements()` 追加（Gemini API でルール＋AI 複合チェック）
    - `POST /tasks/{id}/clarify-requirements` エンドポイント（`ClarifyIssue` Pydantic モデル）
    - タスク詳細「詳細」タブに AI チェックボタン・要件不足 Alert 表示
    - テスト 7 件追加（`tests/unit/test_clarify_requirements.py`）→ 合計 170 passed

  - **[Admin 組織設定・アラート設定タブ]**
    - `GET/PATCH/DELETE /api/v1/admin/tags` — 部門タグ一覧・リネーム・削除 API 追加（`admin.py`）
    - `TagRenameRequest` Pydantic モデル追加（`task_web.py`）
    - Admin ページをタブ構成に刷新: ユーザー管理 / 組織設定 / アラート設定（`frontend/src/pages/Admin/`）
    - `useAdminTags` フック（一覧・リネーム・削除）・`useAdminUsers` フック追加
    - `useSettingsStore` Zustand ストア追加（アラート設定永続化）
    - Dashboard ロールスコープ修正（`_scope_condition()` で member/leader/manager/admin 別絞り込み）

  - **[DevLogin カード選択 UI 刷新]**
    - `GET /api/v1/dev/users` エンドポイント追加（`dev.py`・DEV_MODE=true のみ有効）
    - DevLogin をフォーム手入力 → DB からユーザー取得してカード選択方式に変更
    - ロール・部門タグをカラーバッジで視覚表示

  - **[Gantt 依存関係 UI 改善]**
    - 先行タスク(A)→後続タスク(B) の選択 UI を 2 ドロップダウン方式に統一
    - 依存関係削除（`Popconfirm` + `DeleteOutlined`）追加
    - `DepMapFull` 型で依存 ID を正確に管理

  - **[ruff 自動修正]** 38 件の import 整列・不要 import 除去・`datetime.UTC` 置換

- **完了した作業**:
  - **[F-32 サブタスク自動生成 — Gemini API 連携]**
    - `GeminiProvider.generate_subtasks()` 追加（`src/providers/gemini.py`）
    - `POST /tasks/{id}/generate-subtasks` エンドポイント（503 エラーハンドリング・logger.exception 付き）
    - `GenerateSubtasksResponse` Pydantic モデル追加
    - `useGenerateSubtasks()` フック追加（`frontend/src/hooks/useTaskDetails.ts`）
    - `SubtasksPanel.tsx` を AI 提案 UI に刷新（チェックボックス選択→一括追加）
    - テスト 6 件追加（`tests/unit/test_generate_subtasks.py`）→ 合計 128 passed

  - **[F-15 テンプレート機能 — 定型業務の雛形登録・一括作成]**
    - **Alembic 0005**: `task_templates.updated_at` カラム追加（`sa.text("now()")` 準拠）
    - **Pydantic モデル 7 種**: `TemplateSubtask` / `TemplateData` / `TemplateCreate` / `TemplateUpdate` / `TemplateResponse` / `TemplateApplyRequest` / `TemplateApplyResponse`（`src/models/task_web.py`）
    - **テンプレート CRUD ルーター**: `src/api/routers/templates.py`（GET/POST/PUT/DELETE・作成者 or admin 認可・`POST /{id}/apply` でメインタスク＋サブタスク一括作成）
    - **テスト 13 件**: `tests/unit/test_templates_router.py`（CRUD・403 認可・apply 3 件）→ 合計 141 passed
    - **フロントエンド**: `useTemplates.ts`（5 フック）・`/templates` 管理ページ（カード一覧・Drawer 作成/編集・Form.List サブタスク）・App.tsx ナビ追加
    - **タスク作成モーダル統合**: テンプレート選択 Select + DatePicker + 「このテンプレートで作成」ボタン・Divider で手動作成と区別
    - TypeScript チェック通過・全コミット origin/master にプッシュ済み

  - **[バグ修正セッション — SQLAlchemy MissingGreenlet 根本修正]**
    - **ガントチャート reschedule エラー修正**（`src/api/routers/tasks_crud.py` `reschedule_task`）
      - 原因: `_cascade_reschedule()` が `await db.execute(SELECT)` → autoflush → UPDATE → `updated_at` expire → `db.refresh(task, ["tags","sub_assignees","subtasks"])` が列属性を再ロードせず → `_task_to_response()` で `MissingGreenlet` → HTTP 500
      - 修正: `commit()` 後に部分 `db.refresh()` を廃止し、フル `SELECT` + `selectinload` で再クエリ
    - **`update_task` 同種バグ修正**（`tasks_crud.py` L275）
      - タグ更新時 `db.flush()` → UPDATE → `updated_at` expire → 部分 `db.refresh()` → `MissingGreenlet` → HTTP 500
      - 修正: `commit()` 後に同パターンで再クエリ
    - **ガントチャート React StrictMode 二重発火修正**（`frontend/src/pages/Gantt/index.tsx`）
      - `isReschedulingRef` + `useCallback` で同時実行を防御
      - `toLocalDate()` をコンポーネント外の純粋関数に移動（タイムゾーン問題修正）
    - **全 router の `db.refresh()` 安全性確認**: `tasks_crud.py` `update_task` のみが問題、他は全安全
    - **セキュリティレビュー実施**: `DEV_MODE` バイパス機能の脆弱性候補を分析→信頼度閾値(8)未満のため有意な脆弱性なし
    - **テスト**: `tests/unit/test_auth.py` 7 件 ✅ passed

  - **[Web App Phase 2B-3 — F-14 全タスク完了]** 負荷アラート（ワークロードバッジ）実装
    - `DailyWorkloadItem` Pydantic モデル追加（`src/models/task_web.py`）
    - `GET /dashboard/daily-workload` エンドポイント（due_date 日別集計・ロール別スコープ・1.0h デフォルト）
    - `tests/unit/test_daily_workload.py`（7 件追加 → 合計 122 passed）
    - `frontend/src/hooks/useDailyWorkload.ts`（5 分キャッシュ）
    - `frontend/src/components/WorkloadAlertBadge.tsx`（Badge + Popover + recharts BarChart + Cell 着色 + ReferenceLine）
    - `frontend/src/App.tsx` ヘッダー右端に WorkloadAlertBadge 統合
    - TypeScript チェック通過・フロントエンドビルド（Windows 環境の pre-existing クラッシュは無関係）

  - **[Web App Phase 2B-2 — 全 14 タスク完了]** ユーザー管理・権限制御・UX 強化
    - Alembic 0003（start_date 補完）・0004（department_tags JSONB）
    - ハイブリッド認証: JWT-first / DB-fallback・ROLE_HIERARCHY 公開
    - Admin API: GET/POST/PATCH/DELETE /api/v1/admin/users（admin 権限ガード）
    - ロールベース閲覧制御: member=own+public, leader=dept+public, manager/admin=全件
    - /tasks/similar の認可フィルタ（private タスク漏洩防止）・my_tasks_only + ロールフィルタ競合修正
    - F-07: my_tasks_only フィルタ・タスク作成時 visibility 選択（private/team/all）
    - F-04: /tasks/similar エンドポイント（トークン分割 ILIKE・スコア 0.5 以上・最大 5 件）
    - F-11: Schedule ページ週次 D&D グリッド（前後 3 日 + 今日 + 3 日・start_date 更新）
    - Admin Users ページ（/admin/users・admin ロール限定表示）・部門タグ Select mode=tags
    - テスト: 115 passed（新規 13 件: test_admin_router・test_visibility・test_similar_tasks）
    - バグ修正: visibility "public" → "all"・similar 認可バイパス・my_tasks_only ロール競合
    - git push: `6638870` → origin/master にプッシュ済み

  - **[Web App Phase 2B-1 — 全 6 タスク完了]** マルチビュー + F-36 自動リスケジュール実装
    - バックエンド: `due_date_gte`/`lte`/`assignee_ids` フィルタ追加、`POST /tasks/{id}/reschedule` エンドポイント新設（BFS 依存グラフ走査）
    - フロントエンド: `@dnd-kit`, `react-big-calendar`, `gantt-task-react` ライブラリ導入
    - カンバンビュー (`/board`): ステータス 4 列・dnd-kit D&D・CSS.Transform.toString()・drag/click 競合防止
    - カレンダービュー (`/calendar`): 月次・担当者 Multi-Select フィルタ・タスク密度ヒートマップ・`allDay` 期間バー対応
    - ガントチャート (`/gantt`): gantt-task-react・バー D&D で reschedule・依存関係矢印・`enabled` ガード・onError フィードバック
    - フック: `useTasksForView`・`useReschedule`・`useUsers` 新規作成
    - テスト: 118 passed（新規 4 件: test_reschedule.py）
    - バグ修正: BFS キュー条件・start_date 上書き・`allDay` フラグ・due_date なしタスクのクラッシュ防止
    - git push: `71eb868` (最終コミット) → origin/master にプッシュ済み

  - **[Web App Phase 2A — 全 12 タスク完了]** タスク詳細 UI 完成・Asana インポート機能実装
    - Alembic 0002: sections・task_assignees テーブル追加・Task 列追加（section_id, external_id, completed_at, order_index）
    - Section CRUD API（`/api/v1/projects/{id}/sections`）・Task Assignees API・タスク複製 API
    - キーワード検索（ILIKE）・section_id フィルタを `GET /tasks` に追加
    - ユーザー一覧 API のリーダーロール制限撤廃
    - Asana xlsx インポート: openpyxl 解析・preview/confirm 2 段階 API
    - App.tsx を Ant Design Sider レイアウトに刷新・/projects と /import ルート追加
    - プロジェクト一覧ページ（List.tsx）・プロジェクト詳細ページ（Section 別タスク管理）
    - タスク詳細を 4 タブ拡張（詳細・コメント・工数・サブタスク）・複製ボタン
    - タスク一覧検索 UI（キーワード・ステータス・プロジェクト・セクションフィルタ）
    - Asana インポートウィザード（3 ステップ: Upload → Preview → Complete）
    - バグ修正: `await db.delete()` の await 漏れを sections/task_details の 3 箇所で修正
  - **テスト**: バックエンド 114 passed（.venv Python 3.11）
  - **git コミット**: `31fc4e0`

## 実装計画ファイル（Phase 2B-1）
- `docs/superpowers/plans/2026-05-19-phase2b1-multiview-implementation.md`（Phase 2B-1 実装計画・全完了）
- `docs/specs/2026-05-19-phase2b1-multiview-design.md`（Phase 2B-1 設計書）

  - **[Web App Phase 1 — 全 18 タスク完了]** React + FastAPI + PostgreSQL タスク管理 Web アプリ実装（2026-05-19）
    - PostgreSQL 16 + SQLAlchemy 2.x（Mapped 型）+ Alembic 非同期マイグレーション
    - タスク一覧・詳細・ダッシュボード・スケジュール・ワークロードページ
    - MSAL Entra ID 認証・Zustand 状態管理・TanStack Query 5.x
    - **テスト**: バックエンド 79 passed / フロントエンドビルド成功

## テスト状況
| テストファイル | 件数 | 状態 |
|-------------|------|------|
| test_models.py | 9 | ✅ |
| test_state.py | 4 | ✅ |
| test_classifier.py | 6 | ✅ |
| test_approval.py | 5 | ✅ |
| test_routing.py | 3 | ✅ |
| test_providers.py | 11 | ✅ |
| test_agent.py | 2 | ✅ |
| test_langfuse_client.py | 3 | ✅ |
| test_polling_job.py | 6 | ✅ |
| test_task_web_models.py | 12 | ✅ |
| test_tasks_crud_router.py | 8 | ✅ |
| test_connectors.py | 10 | ✅ |
| test_teams_chat.py | 3 | ✅ |
| test_onenote.py | 3 | ✅ |
| test_reschedule.py | 4 | ✅ |
| test_daily_workload.py | 7 | ✅ |
| test_generate_subtasks.py | 6 | ✅ |
| test_templates_router.py | 13 | ✅ |
| test_clarify_requirements.py | 7 | ✅ |
| test_admin_router.py | 5 | ✅ |
| test_auth.py | 7 | ✅ |
| test_import.py | 5 | ✅ |
| test_past_performance.py | 6 | ✅ |
| test_projects_router.py | 4 | ✅ |
| test_sections_router.py | 4 | ✅ |
| test_similar_tasks.py | 4 | ✅ |
| test_visibility.py | 4 | ✅ |
| **合計** | **170** | ✅ 全 passed |

## 前提条件ステータス
| 項目 | ステータス | 備考 |
|------|----------|------|
| Graph API アプリ登録 | ⏳ 申請中 | IT管理者と調整中 |
| Exchange Application Access Policy | ⏳ IT管理者対応待ち | Step 1: 担当者1名で検証 |
| Docker Desktop | ✅ 確認済み v28.5.1 | Langfuse コンテナ起動済み |
| Langfuse | ✅ 設定済み | http://localhost:3000 |
| PostgreSQL（Docker） | 🔧 設定済み（接続要確認） | docker-compose up で起動 |
| Python .venv | ✅ 動作確認 | pytest 114 passed |
| Node.js / npm | ✅ 動作確認 | TypeScript チェック通過 |

## ブロッカー
- **Graph API 申請**: IT管理者との調整中。承認後に Phase 1B 統合テストを実施可能
- **respx 未インストール**: `.venv` に `pip install respx` で解決可能（優先度低）

## 次セッションの開始手順
1. `docs/progress.md`（このファイル）を確認
2. Graph API 承認状況を確認
   - **承認済み** → `docs/tasks.md` の Phase 1B タスクから開始
   - **未承認** → Web App Phase 2B 残タスク（F-21 Teams 通知・F-12 工数自動算出）から開始
3. 残タスク候補:
   - **F-21 Teams 通知**: コメント投稿時に担当者へ Teams メッセージ送信
   - **F-12 工数自動算出**: 蓄積データから目標工数を自動算出・提案

## 実装計画ファイル
- `docs/superpowers/plans/2026-05-27-f15-template.md`（F-15 テンプレート機能 実装計画・全完了）
- `docs/superpowers/specs/2026-05-27-f15-template-design.md`（F-15 テンプレート機能 設計書）
- `docs/superpowers/plans/2026-05-27-f32-generate-subtasks.md`（F-32 サブタスク自動生成 実装計画・全完了）
- `docs/superpowers/plans/2026-05-19-phase2a-task-detail-implementation.md`（Phase 2A 実装計画・全完了）
- `docs/specs/2026-05-19-phase2a-task-detail-design.md`（Phase 2A 設計書）
- `docs/superpowers/plans/2026-05-18-phase1-webapp-implementation.md`（Web App Phase 1 実装計画・全完了）
- `docs/specs/system-design.md`（詳細設計ドキュメント）
- `docs/requirements.md`（機能要件・全 37 機能）
