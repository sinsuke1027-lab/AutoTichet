# AutoTicket — 自動タスク起票システム

## プロジェクト概要
Outlookメール・Teams会議議事録からAIがタスクを自動抽出し、Microsoft Plannerへ自動起票するシステム。
TaskFlowとは独立した別プロジェクト。

## セッション開始時の必須手順
新しいセッションを開始したら、必ず以下を実行する：
1. `docs/progress.md` を読んで現在の進捗・ブロッカーを確認する
2. `docs/tasks.md` を読んで次の未完了タスクを確認する
3. ユーザーに「前回の続き：〇〇まで完了、次は××です」と報告してから作業開始

## 重要ルール
1. **データセキュリティ**: 機密データを外部LLM（OpenAI等）に絶対に送信しない
2. **型ヒント**: 全Pythonコードに型ヒント必須（引数・戻り値の両方）
3. **Pydantic v2**: データモデルはPydantic v2のみ使用（dict生の引き回し禁止）
4. **非同期**: I/O処理はasync/await必須
5. **最小権限**: Graph APIスコープは必要最小限のみ
6. **.envはコミットしない**: シークレットは環境変数のみで管理
7. **機密度分類**: テキスト処理前に必ずsensitivity-checkスキルを参照

## 技術スタック
| レイヤー | ツール |
|---------|--------|
| APIフレームワーク | FastAPI + uvicorn |
| AIオーケストレーション | LangGraph |
| データモデル | Pydantic v2 |
| ローカルDB | SQLite（aiosqlite） |
| M365連携 | Microsoft Graph API（MSAL Python） |
| 監査ログ | Langfuse（Docker） |
| ローカルLLM（Phase 3〜） | Ollama（qwen2.5:14b） |
| コンテナ | Docker（Langfuse・n8n・Ollama） |

## 開発コマンド
```bash
# 開発サーバー起動
uvicorn src.api.main:app --reload --port 8000

# テスト実行
pytest tests/ -v

# リント・フォーマット
ruff check src/ tests/
ruff format src/ tests/

# 型チェック
mypy src/
```

## アーキテクチャ概要（Phase 1）
```
Graph API（Outlookメール・Teams文字起こし）
    ↓ ポーリング（5〜10分間隔）
FastAPI + LangGraph エージェント
    ├→ 処理済みID → SQLite（data/processed.db）
    ├→ タスク起票 → Microsoft Planner（Graph API）
    └→ 監査ログ → Langfuse（Docker）
```

## LangGraph エージェント状態フロー
```
classify_sensitivity
    → extract_tasks
        → match_assignee
            → score_confidence
                → route_approval
                    ├→ auto_create（スコア≥0.8）
                    ├→ request_approval（スコア0.5〜0.8）
                    └→ log_only（スコア<0.5）
```

## フェーズ構成
| フェーズ | 内容 | ステータス |
|---------|------|----------|
| Phase 0 | ハーネス設定 | ✅ 完了 |
| Phase 1 | Outlook・Teams → Planner自動起票（Pattern A） | ⏳ 進行中 |
| Phase 2 | Teamsチャット・OneNote対応 | 未着手 |
| Phase 3 | ローカルLLM基盤（Pattern B）+ 機密度振り分け | 未着手 |
| Phase 4 | 通話録音対応（Whisper） | 未着手 |

## フォルダ構造
```
AutoTicket/
├── CLAUDE.md
├── .claude/
│   ├── settings.json          # hooks・権限設定
│   └── skills/
│       ├── resume-session.md  # セッション再開スキル
│       ├── extract-task.md    # タスク抽出指示スキル
│       └── sensitivity-check.md  # 機密度分類スキル
├── docs/
│   ├── specs/                 # 設計ドキュメント（チーム共有用）
│   │   └── system-design.md  # 詳細設計書（Phase 0〜9 全体）
│   ├── superpowers/plans/     # エージェント実装計画（内部用）
│   ├── progress.md            # 進捗ログ（毎セッション末に更新）
│   ├── tasks.md               # タスク一覧・チェックリスト
│   └── graph-api-setup.md    # IT管理者向け申請手順書
├── src/
│   ├── api/                   # FastAPI エントリーポイント
│   ├── agents/                # LangGraph エージェント
│   ├── connectors/            # Graph API・Planner連携
│   ├── models/                # Pydantic モデル
│   └── services/              # ビジネスロジック
├── tests/unit/
├── tests/integration/
├── docker/
├── data/                      # SQLite DB（.gitignore除外）
├── .env.example
├── pyproject.toml
└── .gitignore
```

## コーディング規約
| 項目 | 規約 |
|------|------|
| フォーマッター | ruff format（Black互換） |
| リンター | ruff check |
| 型チェック | mypy --strict |
| ファイル名 | snake_case.py |
| クラス名 | PascalCase |
| 定数 | UPPER_SNAKE_CASE |
| 関数・変数 | snake_case |
| 最大行長 | 100文字 |
| テスト | pytest + pytest-asyncio |

## 前提条件（未解決）
- [ ] Graph API アプリ登録 → `docs/graph-api-setup.md` をIT管理者に提出
- [ ] Docker Desktop インストール確認（Langfuse・n8n実行用）
