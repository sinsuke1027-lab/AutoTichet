# AutoTicket タスク一覧

最終更新: 2026-05-01（Teamsボット入力ルート追加）

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

### 1-3. LLMプロバイダー抽象化
- [ ] `src/providers/base.py` — LLMProvider / VisionLLMProvider Protocol定義
- [ ] `src/providers/ollama.py` — Ollamaプロバイダー実装
- [ ] `src/providers/claude.py` — Claude APIプロバイダー実装
- [ ] `src/providers/gemini.py` — Gemini APIプロバイダー実装
- [ ] `src/providers/azure_openai.py` — Azure OpenAIプロバイダー実装
- [ ] `src/providers/factory.py` — 設定値からプロバイダーを生成するファクトリー
- [ ] プロバイダー切り替えテスト（各プロバイダーのモック）

### 1-4. LangGraph エージェント
- [ ] `src/services/classifier.py` — 機密度分類ロジック（機密時はollama強制）
- [ ] `src/agents/task_extractor.py` — タスク抽出ノード実装
- [ ] `src/agents/graph.py` — LangGraph グラフ定義・状態マシン

### 1-5. 起票・承認フロー
- [ ] `src/connectors/planner.py` — Microsoft Planner タスク起票（Graph API）
- [ ] `src/services/approval.py` — 信頼スコア→承認フロー分岐
- [ ] Teams承認通知（Adaptive Card）実装

### 1-6. FastAPI エントリーポイント
- [ ] `src/api/main.py` — FastAPI アプリ・ポーリングスケジューラー起動
- [ ] `src/api/routers/tasks.py` — タスク手動起票エンドポイント
- [ ] `src/api/routers/health.py` — ヘルスチェックエンドポイント

### 1-7. テスト
- [ ] `tests/unit/test_task_extractor.py` — タスク抽出ユニットテスト（モックLLM）
- [ ] `tests/unit/test_classifier.py` — 機密度分類ユニットテスト
- [ ] `tests/integration/test_graph_api.py` — Graph API統合テスト（申請後）

### 1-8. インフラ
- [ ] `docker/docker-compose.yml` — Langfuse・n8n設定
- [ ] `docker/Dockerfile` — FastAPIアプリコンテナ
- [ ] Langfuse 動作確認

---

## Phase 2: Teamsチャット・OneNote対応
- [ ] （Phase 1完了後に詳細化）
- [ ] Graph API スコープ追加申請（ChannelMessage.Read.All / Notes.Read.All）

## Phase 3: ローカルLLM基盤（Pattern B）+ Teamsボット
- [ ] （Phase 1完了後に詳細化）
- [ ] Ollama + qwen2.5:14b セットアップ
- [ ] Ollama + llama3.2-vision セットアップ（スクショ処理用）
- [ ] 機密度振り分けロジック実装
### Teamsボット（スクショ＋コメント起票）
- [ ] Bot Framework 登録（Teams Developer Portal）
- [ ] FastAPI `/bot` エンドポイント実装（Bot Framework Webhook受信）
- [ ] 画像バイナリ抽出 + Ollama vision 呼び出し実装
- [ ] 画像説明 + コメント統合 → LangGraph エージェントへ渡す実装
- [ ] ボット返信メッセージ実装（起票成功・承認依頼・低信頼スコア）
- [ ] チャンネル投稿・DM 両対応テスト

## Phase 4: 通話録音（Whisper）
- [ ] （Phase 3完了後に詳細化）
