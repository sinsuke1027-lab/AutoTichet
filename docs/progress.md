# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: 1B 準備中**
ステータス: ✅ Phase 1A 完了・Langfuse/Docker 設定済み / ⏳ Graph API 申請中（承認待ち）

## 最終更新
- **日付**: 2026-05-03
- **完了した作業**:
  - Phase 0 ハーネス設定
  - **[ドキュメント]** docs/requirements.md / db-schema.md / design.md 作成
  - **[Task 1]** requirements.txt / requirements-dev.txt / 全 __init__.py / .venv セットアップ
  - **[Task 2]** src/models/task.py（ExtractedTask・SensitivityResult）
  - **[Task 3]** src/models/config.py（Settings pydantic-settings）
  - **[Task 4]** src/services/state.py（SQLite 処理済み ID 管理）
  - **[Task 5]** src/providers/base.py + src/providers/ollama.py
  - **[Task 6]** src/providers/claude.py / gemini.py / azure_openai.py
  - **[Task 7]** src/providers/factory.py
  - **[Task 8]** src/services/classifier.py（機密度分類器）
  - **[Task 9]** src/services/approval.py（承認フロー分岐）
  - **[Task 10]** src/services/routing.py（visibility→起票先ルーティング）
  - **[Task 11]** src/agents/nodes.py + graph.py（LangGraph エージェント）
  - **[Task 12]** src/api/main.py + routers/health.py + tasks.py（FastAPI）
  - **[Task 13]** 全テスト 45/45 パス・ruff・mypy 全クリーン
  - **[Langfuse]** src/services/langfuse_client.py + /extract エンドポイントにトレーシング追加
  - **[Connectors]** src/connectors/graph_api.py / planner.py / todo.py（モックテスト済み）
  - **[Docker]** docker/Dockerfile + docker-compose.yml（autoticket-app サービス追加）
  - **[計画]** docs/superpowers/plans/2026-05-03-autoticket-phase1b-onwards.md 作成
  - **[Task 14]** src/models/config.py に dept_plan_map（JSON環境変数）追加
  - **[Task 15]** src/api/main.py polling_job() 完全実装（TDD・3テスト追加）— メールポーリング→LangGraph→起票ルーティング

## テスト状況
| テストファイル | 件数 |
|-------------|------|
| test_models.py | 6 |
| test_state.py | 4 |
| test_classifier.py | 6 |
| test_approval.py | 5 |
| test_routing.py | 3 |
| test_providers.py | 8 |
| test_agent.py | 2 |
| test_langfuse_client.py | 3 |
| test_connectors.py | 10 |
| test_polling_job.py | 3 |
| **合計** | **50** |

## 前提条件ステータス
| 項目 | ステータス | 備考 |
|------|----------|------|
| Graph API アプリ登録 | ⏳ 申請中 | IT管理者承認待ち |
| Docker Desktop | ✅ 確認済み v28.5.1 | Langfuse コンテナ起動済み |
| Langfuse | ✅ 設定済み | http://localhost:3000、APIキー .env 登録済み |
| Python 3.13.7 | ✅ 確認済み | .venv で動作 |

## ブロッカー
- **Graph API アプリ登録**: IT管理者への申請中。承認後に Task 16〜18（統合・E2E テスト）を実施可能

## 次セッションの開始手順
1. `docs/progress.md`（このファイル）と `docs/superpowers/plans/2026-05-03-autoticket-phase1b-onwards.md` を確認
2. Graph API 承認状況を確認
3. 承認済み → Task 16（統合テスト基盤）から開始
4. 未承認 → Task 16（統合テスト基盤スキャフォルド）または Phase 2 Task 19（Teamsチャットコネクター）から開始

## 実装計画ファイル
- `docs/superpowers/plans/2026-05-03-autoticket-phase1b-onwards.md`
  - Task 14: dept_plan_map を Settings に追加（credentials 不要）
  - Task 15: polling_job() 完全実装（credentials 不要）
  - Task 16: 統合テスト基盤（credentials 必要）
  - Task 17: Graph API 疎通確認テスト（credentials 必要）
  - Task 18: E2E テスト（credentials 必要）
  - Task 19: Teams チャットコネクター（Phase 2）
  - Task 20: OneNote コネクター（Phase 2）
  - Task 21: polling_job() Teams/OneNote 追加（Phase 2）
  - Task 22: Pattern B → Ollama 強制（Phase 3）
  - Task 23: Ollama docker-compose 追加（Phase 3）
  - Task 24: Teams Bot エンドポイント（Phase 3）
  - Task 25: Ollama vision 画像処理（Phase 3）
