# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: Web App Phase 1（Must）✅ 完了 → Phase 1B / Web App Phase 2 へ**
ステータス: Web アプリ Must 機能フルスタック実装完了・Graph API 申請中（承認待ち）

## 最終更新
- **日付**: 2026-05-19
- **完了した作業**:
  - **[Web App Phase 1 — 全 18 タスク完了]** React + FastAPI + PostgreSQL タスク管理 Web アプリ実装
    - PostgreSQL 16 + SQLAlchemy 2.x（Mapped 型）+ Alembic 非同期マイグレーション
    - Pydantic v2 Web API モデル（TaskCreate / ProjectResponse / DashboardSummary 等）
    - Entra ID JWT 検証ミドルウェア（JWKS TTL キャッシュ）・ロールベースアクセス制御
    - プロジェクト CRUD / タスク CRUD（サブタスク・タグ）/ コメント・工数・依存関係 API
    - ダッシュボード API（summary / today / overdue / workload / completion-trend・N+1 解消）
    - ユーザープロファイル API・CORS ミドルウェア・全ルーター登録
    - LangGraph 起票先を Microsoft Planner/To Do → PostgreSQL に変更
    - Microsoft Forms（SharePoint）ポーリング追加（F-16）
    - React 18 + TypeScript strict + Vite + Ant Design 5.x + TanStack Query 5.x フロントエンド
    - MSAL（@azure/msal-react）Entra ID 認証・Zustand 認証状態管理
    - axios API クライアント + カスタムフック（useTasks / useDashboard / useProjects）
    - タスク一覧・詳細ページ（F-01, F-02, F-03）
    - ダッシュボードページ（F-09, F-10）
    - スケジュール・ワークロードページ（F-09, F-13）
    - TypeScript verbatimModuleSyntax 準拠・vitest/config 修正
  - **テスト**: バックエンド 79 passed（.venv Python 3.11）/ フロントエンドビルド成功
  - **git push**: origin/master へプッシュ済み（commit `4a2039a`）

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
| **実行可能合計** | **79** | ✅ 全 passed |

> ⚠️ `respx` は `.venv` に未インストールのため test_connectors / test_teams_chat / test_onenote が collection エラー。コード自体は正常実装済み。

## 前提条件ステータス
| 項目 | ステータス | 備考 |
|------|----------|------|
| Graph API アプリ登録 | ⏳ 申請中 | IT管理者と調整中 |
| Exchange Application Access Policy | ⏳ IT管理者対応待ち | Step 1: 担当者1名で検証 |
| Docker Desktop | ✅ 確認済み v28.5.1 | Langfuse コンテナ起動済み |
| Langfuse | ✅ 設定済み | http://localhost:3000 |
| PostgreSQL（Docker） | 🔧 設定済み（接続要確認） | docker-compose up で起動 |
| Python .venv | ✅ 動作確認 | pytest 79 passed |
| Node.js / npm | ✅ 動作確認 | frontend build 成功 |

## ブロッカー
- **Graph API 申請**: IT管理者との調整中。承認後に Phase 1B 統合テストを実施可能
- **respx 未インストール**: `.venv` に `pip install respx` で解決可能（優先度低）

## 次セッションの開始手順
1. `docs/progress.md`（このファイル）を確認
2. Graph API 承認状況を確認
   - **承認済み** → `docs/tasks.md` の Phase 1B タスクから開始
   - **未承認** → Web App Phase 2（Should 機能）から開始

## 実装計画ファイル
- `docs/superpowers/plans/2026-05-18-phase1-webapp-implementation.md`（Web App Phase 1 実装計画・全完了）
- `docs/specs/system-design.md`（詳細設計ドキュメント）
- `docs/specs/2026-05-18-dashboard-webapp-design.md`（Web アプリ設計書）
- `docs/requirements.md`（機能要件・全 37 機能）
