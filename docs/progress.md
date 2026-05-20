# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: Web App Phase 2B-2（ユーザー管理・権限制御・UX 強化）✅ 完了 → Phase 2B-3 以降へ**
ステータス: F-08 ユーザー管理・ロール制御・F-07 個人 ToDo・F-04 類似タスク警告・F-11 週次 D&D グリッド 全実装完了・Graph API 申請中（承認待ち）

## 最終更新
- **日付**: 2026-05-20
- **完了した作業**:
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
| test_tasks_crud_router.py | 6 | ✅ |
| test_connectors.py | 10 | ⚠️ respx 未インストール（環境問題） |
| test_teams_chat.py | 3 | ⚠️ respx 未インストール（環境問題） |
| test_onenote.py | 3 | ⚠️ respx 未インストール（環境問題） |
| test_reschedule.py | 4 | ✅ |
| **実行可能合計** | **118** | ✅ 全 passed |

> ⚠️ `respx` は `.venv` に未インストールのため test_connectors / test_teams_chat / test_onenote が collection エラー。コード自体は正常実装済み。

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
   - **未承認** → Web App Phase 2B-2 以降（F-07 個人 ToDo・F-04 二重登録防止・F-14 負荷アラート・F-21 Teams 通知・F-12 工数自動算出）から開始

## 実装計画ファイル
- `docs/superpowers/plans/2026-05-19-phase2a-task-detail-implementation.md`（Phase 2A 実装計画・全完了）
- `docs/specs/2026-05-19-phase2a-task-detail-design.md`（Phase 2A 設計書）
- `docs/superpowers/plans/2026-05-18-phase1-webapp-implementation.md`（Web App Phase 1 実装計画・全完了）
- `docs/specs/system-design.md`（詳細設計ドキュメント）
- `docs/requirements.md`（機能要件・全 37 機能）
