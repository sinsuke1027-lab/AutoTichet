# AutoTicket タスク一覧

最終更新: 2026-05-27

凡例: `[x]` 完了 / `[ ]` 未着手 / `[-]` 承認待ちでブロック中

---

## Phase 0: ハーネス設定 ✅ 完了

- [x] プロジェクトフォルダ・ディレクトリ構造作成
- [x] CLAUDE.md 作成
- [x] .claude/settings.json 作成（hooks・権限設定）
- [x] カスタムスキル作成（resume-session / extract-task / sensitivity-check）
- [x] pyproject.toml 作成（ruff / mypy / pytest 設定）
- [x] .env.example 作成
- [x] .gitignore 作成
- [x] docs/progress.md 作成
- [x] docs/graph-api-setup.md 作成（IT管理者向け申請手順書）

---

## Phase 1A: LangGraph パイプライン基盤 ✅ 完了

### ドキュメント
- [x] docs/requirements.md（機能要件・非機能要件）
- [x] docs/design.md（システム構成図・LangGraph 状態機械・API 仕様）

### データモデル
- [x] `src/models/task.py` — ExtractedTask・SensitivityResult（Pydantic v2）
- [x] `src/models/config.py` — Settings（pydantic-settings + dept_plan_map + DATABASE_URL + FRONTEND_URL）

### サービス
- [x] `src/services/state.py` — SQLite 処理済み ID 管理（aiosqlite）
- [x] `src/services/classifier.py` — 機密度分類器（キーワード 31 件）
- [x] `src/services/approval.py` — 信頼スコア → 承認アクション分岐
- [x] `src/services/routing.py` — visibility → PostgreSQL 保存（_save_tasks_to_postgres）
- [x] `src/services/langfuse_client.py` — Langfuse v4 SDK トレーシング

### LLM プロバイダー
- [x] `src/providers/base.py` — LLMProvider / VisionLLMProvider Protocol
- [x] `src/providers/ollama.py` / `claude.py` / `gemini.py` / `azure_openai.py`
- [x] `src/providers/factory.py` — プロバイダーファクトリー

### エージェント
- [x] `src/agents/nodes.py` — classify / extract / route ノード（起票先は PostgreSQL）
- [x] `src/agents/graph.py` — LangGraph StateGraph 定義

### コネクター
- [x] `src/connectors/graph_api.py` — MSAL + httpx（メール・会議・ユーザー・グループ）
- [x] `src/connectors/teams_chat.py` — Teams チャットコネクター
- [x] `src/connectors/onenote.py` — OneNote コネクター
- [x] `src/connectors/forms.py` — Microsoft Forms / SharePoint ポーリング（F-16）

### API
- [x] `src/api/routers/health.py` — GET /health
- [x] `src/api/routers/tasks.py` — POST /tasks/extract（Langfuse トレース付き）
- [x] `src/api/main.py` — FastAPI + APScheduler + `polling_job()` 完全実装（メール・Teams・OneNote・Forms）

### インフラ
- [x] `docker/Dockerfile` / `docker/docker-compose.yml`（PostgreSQL 追加済み）
- [x] Langfuse v2 Docker 起動・APIキー .env 登録済み

---

## Web App Phase 1: Must 機能 ✅ 完了（2026-05-19）

### バックエンド API
- [x] `src/db/engine.py` — asyncpg セッション管理・AsyncSessionLocal
- [x] `src/db/models.py` — SQLAlchemy ORM 9 テーブル（Mapped 型）
- [x] `alembic/` — 非同期マイグレーション設定・初回スキーマ
- [x] `src/models/task_web.py` — Web API 用 Pydantic v2 モデル全種
- [x] `src/api/auth.py` — Entra ID JWT 検証（JWKS TTL キャッシュ）・ロール制御
- [x] `src/api/routers/projects.py` — プロジェクト CRUD
- [x] `src/api/routers/tasks_crud.py` — タスク CRUD + サブタスク一覧
- [x] `src/api/routers/task_details.py` — コメント・工数・依存関係 API
- [x] `src/api/routers/dashboard.py` — ダッシュボード集計 API（N+1 解消）
- [x] `src/api/routers/users.py` — ユーザープロファイル（/me・一覧）

### フロントエンド（React SPA）
- [x] `frontend/` — React 18 + TypeScript strict + Vite + Ant Design 5.x
- [x] `frontend/src/lib/msal.ts` — MSAL PublicClientApplication 設定
- [x] `frontend/src/store/useAuthStore.ts` — Zustand 認証状態管理
- [x] `frontend/src/main.tsx` — MsalProvider + QueryClientProvider + BrowserRouter
- [x] `frontend/src/App.tsx` — MSAL 認証ガード + React Router ルーティング
- [x] `frontend/src/lib/api.ts` — axios API クライアント（MSAL トークンインターセプター）
- [x] `frontend/src/hooks/useTasks.ts` — useTasks / useTask / useCreateTask / useUpdateTask / useDeleteTask
- [x] `frontend/src/hooks/useDashboard.ts` — useDashboardSummary / useTodayTasks / useOverdueTasks / useWorkload
- [x] `frontend/src/hooks/useProjects.ts` — useProjects / useCreateProject
- [x] `frontend/src/pages/Tasks/index.tsx` — タスク一覧（ステータスフィルタ・新規作成モーダル）
- [x] `frontend/src/pages/Tasks/TaskDetail.tsx` — タスク詳細（インライン編集・Descriptions レイアウト）
- [x] `frontend/src/pages/Dashboard/index.tsx` — KPI カード・PieChart・今日のタスク・期限超過リスト
- [x] `frontend/src/pages/Schedule/index.tsx` — 1日スケジュール（今日・期限超過）
- [x] `frontend/src/pages/Workload/index.tsx` — ワークロード（BarChart・Progress・超過 Alert）

### テスト
- [x] `tests/unit/test_task_web_models.py`（12 件）
- [x] `tests/unit/test_tasks_crud_router.py`（6 件）
- [x] バックエンド合計 79 passed / フロントエンドビルド成功

---

## Phase 1B: Graph API 統合 🔒 承認待ち

**前提:** Azure AD アプリ登録承認 + `.env` に `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` 設定

- [x] **Task 16**: `tests/integration/conftest.py` — `AZURE_TENANT_ID` 未設定時の自動 skip
- [ ] **Task 17**: `tests/integration/test_graph_api_live.py` — トークン取得・ユーザー一覧・メール取得
- [ ] **Task 17**: Planner / To Do コネクター疎通確認
- [ ] **Task 18**: `tests/integration/test_e2e.py` — E2E テスト（メール → LangGraph → PostgreSQL 起票）
- [ ] `.env` に `COMPANY_WIDE_PLAN_ID` / `DEPT_PLAN_MAP` 設定

---

## Web App Phase 2A: タスク詳細 UI 完成・Asana インポート ✅ 完了（2026-05-19）

**前提:** Web App Phase 1 完了 ✅

### DB・バックエンド
- [x] **Alembic 0002**: sections・task_assignees テーブル追加・Task 列追加（section_id, external_id, completed_at, order_index）
- [x] **Pydantic モデル更新**: Section*/TaskAssignee*/Import* モデル追加・TaskResponse 拡張
- [x] **Section CRUD API**: `/api/v1/projects/{id}/sections`（一覧・作成・更新・削除・並び替え）
- [x] **Task Assignees API**: `/api/v1/tasks/{id}/assignees`（一覧・追加・削除）
- [x] **タスク複製 API**: `POST /tasks/{id}/duplicate`
- [x] **キーワード検索・section_id フィルタ**: `GET /tasks?q=...&section_id=...`
- [x] **ユーザー一覧ロール制限撤廃**: list_users を全認証済みユーザーに開放
- [x] **Asana インポートバックエンド**: openpyxl xlsx 解析・preview/confirm 2 段階 API

### フロントエンド
- [x] **App.tsx サイドバー**: Sider + Menu（ダッシュボード・タスク・プロジェクト・スケジュール・ワークロード・インポート）
- [x] **プロジェクト一覧ページ**: `/projects`（カードグリッド・作成モーダル）
- [x] **プロジェクト詳細ページ**: `/projects/:id`（Section 別タスク一覧・セクション追加・タスク追加）
- [x] **タスク詳細タブ拡張**: 詳細・コメント・工数・サブタスク の 4 タブ・複製ボタン
- [x] **タスク一覧検索・フィルタ**: キーワード検索・ステータス・プロジェクト・セクションフィルタ・ページネーション
- [x] **Asana インポートウィザード**: 3 ステップ（Upload → Preview → Complete）

## Web App Phase 2B-1: マルチビュー ✅ 完了（2026-05-20）

- [x] **バックエンド API 拡張**: due_date_gte/lte・assignee_ids フィルタ・reschedule エンドポイント
- [x] **カンバンビュー** (`/board`): ステータス 4 列・dnd-kit D&D
- [x] **カレンダービュー** (`/calendar`): 月次・担当者フィルタ・密度ヒートマップ
- [x] **ガントチャート** (`/gantt`): gantt-task-react・バー D&D・依存関係矢印・F-36 自動リスケジュール

## Web App Phase 2B: Should 機能（残タスク）

**前提:** Web App Phase 2A 完了 ✅

### タスク操作 UX 強化
- [x] **F-11 D&D**: タスクをスケジュール画面でドラッグ＆ドロップ配置（`dnd-kit` 使用）
- [x] **F-07 個人 ToDo**: `visibility=private` タスクの個人専用ビュー・フィルタ
- [x] **F-04 二重登録防止**: タスク作成時の類似タスク検索・警告表示 UI
- [x] **F-15 テンプレート機能**: 定型業務を雛形として登録し、基準日オフセットで一括作成（2026-05-27）
  - Alembic 0005・Pydantic 7 モデル・CRUD ルーター + apply・フック・管理ページ・タスク作成モーダル統合

### 通知・アラート
- [x] **F-14 負荷アラート**: ワークロード超過・期限超過のブラウザ通知 or バッジ
- [ ] **F-21 Teams 通知**: コメント投稿時に担当者へ Teams メッセージ送信

### AI 支援
- [x] **F-32 サブタスク自動生成**: Gemini API によるサブタスク 3〜6 件提案・チェックボックス選択一括追加（2026-05-27）
- [x] **F-29 タスク要件の明確化プロンプト**: Gemini AI チェックボタン・要件不足 Alert（2026-05-28）
- [ ] **F-12 工数自動算出**: 蓄積データから 🤖 目標工数を自動算出・提案

---

## Phase 3: ローカル LLM + Teams ボット

**前提:** Web App Phase 2 完了 + Ollama インストール + Bot Framework 登録

- [ ] **Task 22**: Pattern B → Ollama 強制ルーティング（機密テキストを外部 LLM に送信しない）
- [ ] **Task 23**: docker-compose に `ollama` サービス追加（GPU 対応）
- [ ] **Task 24**: `src/api/routers/bot.py` — Teams Bot Webhook エンドポイント
- [ ] **Task 25**: `src/services/image_processor.py` — Vision LLM 画像処理

---

## Phase 4: 通話録音（Whisper）

**前提:** Phase 3 完了 + Whisper 方式決定

- [ ] **Task 26**: `src/services/transcription.py` — Whisper 文字起こしサービス
- [ ] **Task 27**: `src/api/routers/audio.py` — POST `/audio/transcribe`
- [ ] **Task 28**: `polling_job()` に Teams 会議録音ファイル処理を追加

---

## 全体進捗サマリー

| フェーズ | 完了 | 残り | ブロッカー |
|---------|------|------|----------|
| Phase 0 | ✅ 全完了 | — | — |
| Phase 1A（LangGraph パイプライン） | ✅ 全完了 | — | — |
| Phase 1B（Graph API 統合テスト） | 1 / 5 | 4 タスク | 🔒 Graph API 承認待ち |
| Web App Phase 1（Must 機能） | ✅ 全完了（2026-05-19） | — | — |
| Web App Phase 2A（タスク詳細・Asana インポート） | ✅ 全完了（2026-05-19） | — | — |
| Web App Phase 2B-1（マルチビュー） | ✅ 全完了（2026-05-20） | — | — |
| Web App Phase 2B-2（ユーザー管理・権限制御・UX 強化） | ✅ 全完了（2026-05-20） | — | — |
| Web App Phase 2B（Should 機能 残タスク） | 7 / 8 | 2 タスク（F-21・F-12 残） | Phase 2B-5 完了 ✅ → 着手可能 |
| Phase 3（ローカル LLM + Bot） | 0 / 4 | 4 タスク | Phase 2 完了 + Ollama + Bot 登録 |
| Phase 4（音声） | 0 / 3 | 3 タスク | Phase 3 完了 + Whisper 方式決定 |
