# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: 0 → 1 移行中**
ステータス: ✅ ハーネス設定完了 / ⏳ Graph API申請待ち

## 最終更新
- **日付**: 2026-05-02（Task 5完了）
- **完了した作業**:
  - プロジェクト設計ドキュメント作成（docs/superpowers/specs/）
  - CLAUDE.md 作成
  - .claude/settings.json（hooks設定）作成
  - カスタムスキル3本作成（resume-session / extract-task / sensitivity-check）
  - pyproject.toml / .env.example / .gitignore 作成
  - docs/graph-api-setup.md 作成
  - docs/tasks.md 作成
  - **[Task 1完了]** requirements.txt / requirements-dev.txt 作成
  - **[Task 1完了]** src/ & tests/ 全パッケージに __init__.py 作成（src/providers/ ディレクトリも新規作成）
  - **[Task 1完了]** Python 3.13.7 仮想環境（.venv）セットアップ・依存関係インストール完了
  - **[Task 1完了]** pytest 動作確認（0 tests collected、正常終了）
  - **[Task 1完了]** git commit: chore: プロジェクト依存関係とパッケージ構造を初期化
  - **[Task 2完了]** `src/models/task.py` 実装（ExtractedTask・SensitivityResult モデル）
  - **[Task 2完了]** `tests/unit/test_models.py` 実装（4つのユニットテスト、TDD方式）
  - **[Task 2完了]** git commit: feat: ExtractedTask・SensitivityResultモデルを追加
  - **[Task 3完了]** `src/models/config.py` 実装（Settings pydantic-settings）
  - **[Task 3完了]** git commit: feat: pydantic-settingsでSettings設定クラスを追加
  - **[Task 5完了]** `src/providers/base.py` 実装（LLMProvider / VisionLLMProvider Protocol）
  - **[Task 5完了]** `src/providers/ollama.py` 実装（OllamaProvider / OllamaVisionProvider）
  - **[Task 5完了]** `tests/unit/test_providers.py` 実装（2つのプロトコル適合テスト、TDD方式）
  - **[Task 5完了]** ruff --fix 実施（unused imports削除）、mypy チェック完了
  - **[Task 5完了]** git commit: feat: LLMProvider基底Protocol + Ollamaプロバイダーを追加

- **次のアクション**:
  1. Task 4 実装: `src/services/state.py`（SQLite処理済みID管理、aiosqlite）
  2. Task 1-2 実装: `src/connectors/graph_api.py`（Graph API クライアント、MSAL認証）

## 前提条件ステータス
| 項目 | ステータス | 備考 |
|------|----------|------|
| Graph API アプリ登録 | ⏳ 未申請 | graph-api-setup.md をIT管理者に提出要 |
| Docker Desktop | ⏳ 未確認 | Langfuse・n8n実行用 |
| Python 3.11+ | ⏳ 未確認 | 開発環境に必要 |

## ブロッカー
- **Graph API アプリ登録**: IT管理者への申請待ち。承認後に統合テストが実行可能になる

## 次セッションの開始手順
1. このファイルと `docs/tasks.md` を確認する
2. Graph API申請ステータスを更新する
3. Phase 1 の未完了タスクを進める
