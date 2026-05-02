# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: 1 Part A 完了**
ステータス: ✅ Part A（Graph API非依存）実装完了 / ⏳ Graph API申請待ち（Part B待機中）

## 最終更新
- **日付**: 2026-05-02（Part A 全タスク完了）
- **完了した作業**:
  - Phase 0 ハーネス設定（前セッション）
  - **[ドキュメント]** docs/requirements.md（要件定義書）作成
  - **[ドキュメント]** docs/db-schema.md（DB定義書）作成
  - **[ドキュメント]** docs/design.md（基本設計書）作成
  - **[Task 1]** requirements.txt / requirements-dev.txt / 全 __init__.py 作成、.venv セットアップ
  - **[Task 2]** src/models/task.py（ExtractedTask・SensitivityResult）+ テスト4件
  - **[Task 3]** src/models/config.py（Settings pydantic-settings）
  - **[Task 4]** src/services/state.py（SQLite処理済みID管理）+ テスト4件
  - **[Task 5]** src/providers/base.py（LLMProvider Protocol）+ src/providers/ollama.py
  - **[Task 6]** src/providers/claude.py / gemini.py / azure_openai.py（外部LLMプロバイダー）
  - **[Task 7]** src/providers/factory.py（LLMプロバイダーファクトリー）
  - **[Task 8]** src/services/classifier.py（機密度分類器）+ テスト6件
  - **[Task 9]** src/services/approval.py（承認フロー分岐）+ テスト5件
  - **[Task 10]** src/services/routing.py（visibility→起票先ルーティング）+ テスト3件
  - **[Task 11]** src/agents/nodes.py + src/agents/graph.py（LangGraphエージェント）+ テスト2件
  - **[Task 12]** src/api/main.py + src/api/routers/health.py + tasks.py（FastAPI + APScheduler）
  - **[Task 13]** Part A 全テスト 32/32 パス・ruff・mypy 全クリーン

- **次のアクション（Part B: Graph API申請後）**:
  1. `docs/graph-api-setup.md` をIT管理者に提出してGraph API申請を開始する
  2. 申請承認後: `src/connectors/graph_api.py`（MSAL認証・メール・会議取得）
  3. 申請承認後: `src/connectors/planner.py`（Planner起票）
  4. 申請承認後: `src/connectors/todo.py`（To Do起票）
  5. 申請承認後: `src/api/main.py` の `polling_job()` を完全実装
  6. 申請承認後: `docker/docker-compose.yml`（Langfuse）
  7. 申請承認後: E2E動作確認（Outlook→Planner全フロー）

## 前提条件ステータス
| 項目 | ステータス | 備考 |
|------|----------|------|
| Graph API アプリ登録 | ⏳ 未申請 | graph-api-setup.md をIT管理者に提出要 |
| Docker Desktop | ⏳ 未確認 | Langfuse実行用 |
| Python 3.13.7 | ✅ 確認済み | .venv で動作 |

## ブロッカー
- **Graph API アプリ登録**: IT管理者への申請が前提。承認後に Part B（統合テスト含む）を実装可能

## 次セッションの開始手順
1. このファイルと `docs/tasks.md` を確認する
2. Graph API申請ステータスを更新する
3. 承認済みなら Part B（Task 14〜19）を進める
4. 未承認なら Part B を待機しつつ、docker-compose.yml の準備を先行できる
