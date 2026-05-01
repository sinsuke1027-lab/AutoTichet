# AutoTicket タスク一覧

最終更新: 2026-05-01

---

## Phase 0: ハーネス設定
- [x] プロジェクトフォルダ・ディレクトリ構造作成
- [x] CLAUDE.md 作成
- [x] .claude/settings.json 作成（hooks・権限設定）
- [x] カスタムスキル作成（resume-session / extract-task / sensitivity-check）
- [x] pyproject.toml 作成
- [x] .env.example 作成
- [x] .gitignore 作成
- [x] 設計ドキュメント作成（docs/superpowers/specs/）
- [x] docs/progress.md 作成
- [x] docs/graph-api-setup.md 作成

---

## Phase 1: Graph API申請 + Pattern A実装

### 前提条件
- [ ] docs/graph-api-setup.md をIT管理者に提出
- [ ] アプリ登録完了・クレデンシャル受け取り（テナントID / クライアントID / シークレット）
- [ ] .env に認証情報を設定して接続確認
- [ ] Docker Desktop インストール確認

### 1-1. データモデル定義
- [ ] `src/models/task.py` — ExtractedTask・SensitivityResult モデル
- [ ] `src/models/config.py` — Settings（pydantic-settings）

### 1-2. Graph API クライアント
- [ ] `src/connectors/graph_api.py` — MSAL認証・未読メール取得・Teams文字起こし取得
- [ ] `src/services/state.py` — SQLite処理済みID管理（aiosqlite）

### 1-3. LangGraph エージェント
- [ ] `src/services/classifier.py` — 機密度分類ロジック
- [ ] `src/agents/task_extractor.py` — タスク抽出ノード実装
- [ ] `src/agents/graph.py` — LangGraph グラフ定義・状態マシン

### 1-4. 起票・承認フロー
- [ ] `src/connectors/planner.py` — Microsoft Planner タスク起票（Graph API）
- [ ] `src/services/approval.py` — 信頼スコア→承認フロー分岐
- [ ] Teams承認通知（Adaptive Card）実装

### 1-5. FastAPI エントリーポイント
- [ ] `src/api/main.py` — FastAPI アプリ・ポーリングスケジューラー起動
- [ ] `src/api/routers/tasks.py` — タスク手動起票エンドポイント
- [ ] `src/api/routers/health.py` — ヘルスチェックエンドポイント

### 1-6. テスト
- [ ] `tests/unit/test_task_extractor.py` — タスク抽出ユニットテスト（モックLLM）
- [ ] `tests/unit/test_classifier.py` — 機密度分類ユニットテスト
- [ ] `tests/integration/test_graph_api.py` — Graph API統合テスト（申請後）

### 1-7. インフラ
- [ ] `docker/docker-compose.yml` — Langfuse・n8n設定
- [ ] `docker/Dockerfile` — FastAPIアプリコンテナ
- [ ] Langfuse 動作確認

---

## Phase 2: Teamsチャット・OneNote対応
- [ ] （Phase 1完了後に詳細化）
- [ ] Graph API スコープ追加申請（ChannelMessage.Read.All / Notes.Read.All）

## Phase 3: ローカルLLM基盤（Pattern B）
- [ ] （Phase 1完了後に詳細化）
- [ ] Ollama + qwen2.5:14b セットアップ
- [ ] 機密度振り分けロジック実装

## Phase 4: 通話録音（Whisper）
- [ ] （Phase 3完了後に詳細化）
