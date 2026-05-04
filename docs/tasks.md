# AutoTicket タスク一覧

最終更新: 2026-05-04

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

## Phase 1A: 基盤実装（Graph API 不要）✅ 完了

### ドキュメント
- [x] docs/requirements.md（機能要件・非機能要件）
- [x] docs/db-schema.md（SQLite DDL・将来テーブル設計）
- [x] docs/design.md（システム構成図・LangGraph 状態機械・API 仕様）

### データモデル
- [x] `src/models/task.py` — ExtractedTask・SensitivityResult（Pydantic v2）
- [x] `src/models/config.py` — Settings（pydantic-settings + dept_plan_map）

### サービス
- [x] `src/services/state.py` — SQLite 処理済み ID 管理（aiosqlite）
- [x] `src/services/classifier.py` — 機密度分類器（キーワード31件）
- [x] `src/services/approval.py` — 信頼スコア → 承認アクション分岐
- [x] `src/services/routing.py` — visibility → 起票先ルーティング
- [x] `src/services/langfuse_client.py` — Langfuse v4 SDK トレーシング

### LLMプロバイダー
- [x] `src/providers/base.py` — LLMProvider / VisionLLMProvider Protocol
- [x] `src/providers/ollama.py` — Ollama プロバイダー
- [x] `src/providers/claude.py` — Claude API プロバイダー
- [x] `src/providers/gemini.py` — Gemini API プロバイダー
- [x] `src/providers/azure_openai.py` — Azure OpenAI プロバイダー
- [x] `src/providers/factory.py` — プロバイダーファクトリー

### エージェント
- [x] `src/agents/nodes.py` — classify / extract / route ノード
- [x] `src/agents/graph.py` — LangGraph StateGraph 定義

### コネクター（モックテスト済み・実接続は Phase 1B）
- [x] `src/connectors/graph_api.py` — MSAL + httpx（メール・会議・ユーザー・グループ）
- [x] `src/connectors/planner.py` — Planner タスク起票・更新
- [x] `src/connectors/todo.py` — To Do リスト自動作成 + タスク起票

### API
- [x] `src/api/routers/health.py` — GET /health
- [x] `src/api/routers/tasks.py` — POST /tasks/extract（Langfuse トレース付き）
- [x] `src/api/main.py` — FastAPI + APScheduler + `polling_job()` 完全実装

### インフラ
- [x] `docker/Dockerfile` — python:3.13-slim + 非 root ユーザー
- [x] `docker/docker-compose.yml` — autoticket-app + langfuse-server + langfuse-db
- [x] `.dockerignore`
- [x] Langfuse v2 Docker 起動・APIキー .env 登録済み

### テスト（50/50 パス）
- [x] `tests/unit/test_models.py`（6件）
- [x] `tests/unit/test_state.py`（4件）
- [x] `tests/unit/test_classifier.py`（6件）
- [x] `tests/unit/test_approval.py`（5件）
- [x] `tests/unit/test_routing.py`（3件）
- [x] `tests/unit/test_providers.py`（8件）
- [x] `tests/unit/test_agent.py`（2件）
- [x] `tests/unit/test_langfuse_client.py`（3件）
- [x] `tests/unit/test_connectors.py`（10件）
- [x] `tests/unit/test_polling_job.py`（3件）

---

## Phase 1B: Graph API 統合 🔒 承認待ち

**前提:** Azure AD アプリ登録承認 + `.env` に `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` 設定

### 統合テスト基盤
- [ ] **Task 16**: `tests/integration/conftest.py` — `AZURE_TENANT_ID` 未設定時の自動 skip
- [ ] **Task 16**: `pyproject.toml` — `integration` マーカー追加

### Graph API 疎通確認
- [ ] **Task 17**: `tests/integration/test_graph_api_live.py`
  - [ ] トークン取得テスト
  - [ ] `get_users()` — ユーザー一覧取得
  - [ ] `get_groups()` — M365 グループ一覧取得
  - [ ] `get_unread_emails(user_id)` — 未読メール取得

### コネクター疎通確認
- [ ] **Task 17**: テスト用 Planner タスク起票 → ID 返却確認
- [ ] **Task 17**: テスト用 To Do タスク起票 → ID 返却確認

### E2E テスト
- [ ] **Task 18**: `tests/integration/test_e2e.py`
  - [ ] メールテキスト → LangGraph → アクション決定の一気通貫テスト
  - [ ] Planner 起票 → タスク ID 確認

### 設定値確認
- [ ] `.env` に `COMPANY_WIDE_PLAN_ID` 設定（全社 Planner プラン ID）
- [ ] `.env` に `DEPT_PLAN_MAP` 設定（部署グループID → プランID の JSON マッピング）

---

## Phase 2: Teamsチャット・OneNote 対応

**前提:** Phase 1B 完了 + Graph API スコープ追加申請（`ChannelMessage.Read.All` / `Notes.Read.All`）

### Teamsチャットコネクター
- [ ] **Task 19**: `src/connectors/teams_chat.py`
  - [ ] `get_teams()` — 参加チーム一覧
  - [ ] `get_channels(team_id)` — チャンネル一覧
  - [ ] `get_channel_messages(team_id, channel_id)` — メッセージ取得
- [ ] **Task 19**: `tests/unit/test_teams_chat.py`（respx モック）

### OneNote コネクター
- [ ] **Task 20**: `src/connectors/onenote.py`
  - [ ] `get_notebooks()` — ノートブック一覧
  - [ ] `get_recent_pages(count)` — 最近更新ページ一覧
  - [ ] `get_page_content(page_id)` — HTML コンテンツ取得
- [ ] **Task 20**: `tests/unit/test_onenote.py`（respx モック）

### ポーリングジョブ更新
- [ ] **Task 21**: `src/api/main.py` — `polling_job()` に Teams チャンネルメッセージ処理を追加
- [ ] **Task 21**: `src/api/main.py` — `polling_job()` に OneNote 最近ページ処理を追加
- [ ] **Task 21**: `tests/unit/test_polling_job.py` — Teams・OneNote 分岐テスト追加

---

## Phase 3: ローカルLLM + Teamsボット

**前提:** Phase 2 完了 + Ollama インストール + Bot Framework 登録

### 前提作業
- [ ] Ollama インストール（または docker-compose 経由）
- [ ] `ollama pull qwen2.5:14b` — テキスト処理モデル
- [ ] `ollama pull llama3.2-vision` — 画像処理モデル
- [ ] Teams Developer Portal でボット登録（Bot ID + Secret 取得）

### Pattern B → Ollama 強制ルーティング
- [ ] **Task 22**: `src/providers/factory.py` — `create_llm_provider_for_sensitivity(settings, is_confidential)` 追加
- [ ] **Task 22**: `src/agents/nodes.py` — `node_extract` を機密度判定 + プロバイダー選択に更新
- [ ] **Task 22**: `tests/unit/test_providers.py` — 機密フラグ時 Ollama 強制のテスト

### Ollama Docker 対応
- [ ] **Task 23**: `docker/docker-compose.yml` — `ollama` サービス追加（GPU 対応・モデルボリューム）
- [ ] **Task 23**: `.env.example` 更新（Docker 内 OLLAMA_HOST）

### Teams Bot エンドポイント
- [ ] **Task 24**: `src/api/routers/bot.py` — POST `/bot` Webhook
  - [ ] テキストメッセージ → `process_bot_message()` → LangGraph
  - [ ] 画像添付 → バイナリ取得 → `describe_image()` → テキスト統合
- [ ] **Task 24**: `tests/unit/test_bot.py`
- [ ] **Task 24**: `src/api/main.py` — `/bot` router を登録

### Ollama Vision 画像処理
- [ ] **Task 25**: `src/services/image_processor.py` — `describe_image(image_bytes, comment, settings) -> str`
  - [ ] Vision LLM プロバイダー呼び出し
  - [ ] エラー時はコメントをフォールバック返却
- [ ] **Task 25**: `tests/unit/test_image_processor.py`

---

## Phase 4: 通話録音（Whisper）

**前提:** Phase 3 完了 + Whisper モデル or OpenAI Whisper API キー

### 前提作業
- [ ] Whisper 方式の選定（ローカル `openai-whisper` / OpenAI API / Azure Speech）
- [ ] `requirements.txt` に `openai-whisper` or `openai>=1.40.0`（音声エンドポイント）を確認

### 文字起こしサービス
- [ ] **Task 26**: `src/services/transcription.py` — `transcribe_audio(audio_bytes, language) -> str`
  - [ ] ローカル Whisper モデル対応
  - [ ] OpenAI Whisper API 対応（フォールバック）
  - [ ] エラー時の空文字列 + ログ記録
- [ ] **Task 26**: `tests/unit/test_transcription.py`（モック）

### 音声受信エンドポイント
- [ ] **Task 27**: `src/api/routers/audio.py` — POST `/audio/transcribe`
  - [ ] multipart/form-data で音声ファイル受信
  - [ ] `transcribe_audio()` → テキスト化 → LangGraph エージェントへ渡す
  - [ ] 対応フォーマット: wav / mp3 / m4a / ogg
- [ ] **Task 27**: `tests/unit/test_audio.py`
- [ ] **Task 27**: `src/api/main.py` — `/audio` router 登録

### LangGraph 統合
- [ ] **Task 28**: `src/api/main.py` — `polling_job()` に Teams 会議録音ファイル処理を追加
  - [ ] `graph_api.get_meeting_transcripts(meeting_id)` で文字起こし URL 取得
  - [ ] 音声ファイルダウンロード → `transcribe_audio()` → `source_type="meeting"` で LangGraph 投入
- [ ] **Task 28**: `tests/unit/test_polling_job.py` — 会議録音分岐テスト追加

### E2E テスト
- [ ] **Task 29**: `tests/integration/test_audio_e2e.py`
  - [ ] テスト音声ファイル → `POST /audio/transcribe` → タスク抽出確認

### Docker 対応
- [ ] **Task 29**: `docker/docker-compose.yml` — Whisper モデルボリューム追加（ローカル使用時）
- [ ] **Task 29**: `docker/Dockerfile` — `openai-whisper` インストール（ffmpeg 依存含む）

---

## 全体進捗サマリー

| フェーズ | 完了 | 残り | ブロッカー |
|---------|------|------|----------|
| Phase 0 | ✅ 全完了 | — | — |
| Phase 1A | ✅ 全完了 | — | — |
| Phase 1B | 0 / 7 | 7 タスク | 🔒 Graph API 承認待ち |
| Phase 2 | 0 / 9 | 9 タスク | Phase 1B 完了待ち |
| Phase 3 | 0 / 13 | 13 タスク | Phase 2 完了 + Ollama + Bot 登録 |
| Phase 4 | 0 / 12 | 12 タスク | Phase 3 完了 + Whisper 方式決定 |
