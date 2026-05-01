# AutoTicket 設計ドキュメント

**作成日**: 2026-05-01  
**フェーズ**: Phase 0〜1（ハーネス設定 + Pattern A基盤）  
**ステータス**: 承認済み

---

## 1. プロジェクト概要

### 目的
社内で発生するタスクをOutlookメール・Teams会議議事録からAIが自動抽出し、Microsoft Plannerへ自動起票することで、起票漏れ・手作業負担を解消する。

### 制約条件
| 項目 | 内容 |
|------|------|
| OS | Windows 11 Pro（会社支給PC） |
| M365ライセンス | Power Automate Standard（HTTPコネクタ不可） |
| Azureサブスク | なし（M365テナントのAzure ADのみ） |
| セキュリティ | データはM365テナント内またはローカルのみで処理 |
| 開発言語 | Python 3.11+（FastAPI + LangGraph） |

### TaskFlowとの関係
完全に独立したシステム。TaskFlowとは別フォルダ・別プロジェクトとして管理する。

---

## 2. ハーネス設計

### フォルダ構造
```
AutoTicket/
├── CLAUDE.md                        # Claude への指示書（必読）
├── .claude/
│   ├── settings.json                # hooks・権限設定
│   └── skills/
│       ├── resume-session.md        # セッション再開スキル
│       ├── extract-task.md          # タスク抽出指示スキル
│       └── sensitivity-check.md    # 機密度分類スキル
├── docs/
│   ├── superpowers/specs/           # 設計ドキュメント（本ファイル）
│   ├── progress.md                  # 進捗ログ（毎セッション末に更新）
│   ├── tasks.md                     # タスク一覧・チェックリスト
│   └── graph-api-setup.md          # IT管理者向け申請手順書
├── src/
│   ├── api/main.py                  # FastAPI エントリーポイント
│   ├── api/routers/                 # エンドポイント定義
│   ├── agents/                      # LangGraph エージェント
│   ├── connectors/                  # Graph API・Planner連携
│   ├── models/                      # Pydantic モデル
│   └── services/                   # ビジネスロジック
├── tests/unit/
├── tests/integration/               # Graph API申請後に有効化
├── docker/docker-compose.yml        # Langfuse・n8n
├── data/                            # SQLite DB（.gitignore除外）
├── .env.example
├── pyproject.toml
└── .gitignore
```

### コーディング規約
| 項目 | 規約 |
|------|------|
| フォーマッター | ruff format（Black互換、行長100） |
| リンター | ruff check（E / F / I / UP / B / SIM） |
| 型チェック | mypy --strict |
| ファイル名 | snake_case.py |
| クラス名 | PascalCase |
| 定数 | UPPER_SNAKE_CASE |
| データモデル | Pydantic v2のみ |
| I/O処理 | async/await必須 |

### Hooks（.claude/settings.json）
| フック | タイミング | 動作 |
|--------|-----------|------|
| PostToolUse(Write\|Edit) | Pythonファイル保存後 | ruff check + ruff format を自動実行 |
| Stop | Claude応答終了時 | 進捗更新リマインダーを表示 |

---

## 3. Graph API申請手順

### 必要スコープ（Phase 1）
- `Mail.Read` — Outlookメール読み取り（Application権限）
- `OnlineMeetings.Read.All` — Teams会議文字起こし取得（Application権限）
- `Tasks.ReadWrite.All` — Microsoft Plannerタスク起票（Application権限）
- `User.Read.All` — ユーザー情報・担当者照合（Application権限）

### 認証方式
Client Credentials Flow（バックグラウンドサービスのため委任権限ではなくアプリ権限を使用）

### 申請手順書
詳細は `docs/graph-api-setup.md` を参照。IT管理者に提出する。

---

## 4. Phase 1 アーキテクチャ

### 全体データフロー
```
Graph API（Outlookメール・Teams文字起こし）
    ↓ ポーリング（5〜10分間隔）
FastAPI + LangGraph エージェント
    ├→ 処理済みID → SQLite（data/processed.db）
    ├→ タスク起票 → Microsoft Planner（Graph API）
    └→ 監査ログ → Langfuse（Docker）
```

**Power Automateを使わない理由**: Graph APIを直接ポーリングする方が、Power Automate→SharePointキューの2層構造より単純で保守しやすい。

### LangGraph エージェント状態マシン
```
START
  └→ classify_sensitivity（機密度判定）
       └→ extract_tasks（タスク候補抽出）
            └→ match_assignee（担当者照合）
                 └→ score_confidence（信頼スコア算出）
                      └→ route_approval（スコア分岐）
                           ├→ auto_create（スコア≥0.8: Planner直接起票）
                           ├→ request_approval（スコア0.5〜0.8: Teams通知→承認）
                           └→ log_only（スコア<0.5: ログのみ）
                                └→ END
```

### タスク抽出データモデル
```python
class ExtractedTask(BaseModel):
    is_task: bool
    title: str                              # 20〜60文字
    assignee: str | None
    deadline: date | None
    priority: Literal["high", "medium", "low"]
    category: Literal["HR", "IT", "総務", "その他"]
    confidence_score: float                 # 0.0〜1.0
    source_type: Literal["email", "meeting"]
    source_id: str                          # Graph API メッセージID
```

### 書き込み先
| 書き込み先 | 何を書くか | 理由 |
|-----------|-----------|------|
| SQLite | 処理済みメッセージID・タイムスタンプ | 重複処理防止。軽量でDocker不要 |
| Microsoft Planner | 抽出タスク本体 | 最終起票先。M365テナント内に収まる |
| Langfuse | 信頼スコア・抽出ログ・エラー | AI精度モニタリング。社内Dockerで完結 |

### エラーハンドリング
| シナリオ | 対処 |
|---------|------|
| Graph API認証エラー | Langfuseにログ記録、リトライ後にアラート |
| LLM応答タイムアウト | 3回リトライ後スキップ・ログ記録 |
| Planner起票失敗 | 処理済みIDをロールバック・次回リトライ |
| 担当者名照合不能 | assignee=Noneで起票・Teamsで手動確認依頼 |

### テスト方針
| テスト種別 | 対象 | ツール |
|-----------|------|--------|
| ユニット | タスク抽出ロジック・機密度分類 | pytest + モックLLM |
| 統合 | Graph API連携 | pytest-asyncio（申請後に有効化） |
| E2E | Outlook→Planner全フロー | 手動（初回のみ） |

---

## 5. フェーズロードマップ

| フェーズ | 内容 | 前提条件 |
|---------|------|---------|
| Phase 0 | ハーネス設定 | ✅ 完了 |
| Phase 1 | Outlook・Teams → Planner起票 | Graph API申請承認 |
| Phase 2 | Teamsチャット・OneNote対応 | Phase 1完了 |
| Phase 3 | ローカルLLM基盤（Pattern B）+ 機密度振り分け | Docker環境 |
| Phase 4 | 通話録音対応（Whisper） | Phase 3完了 |

---

## 6. 未解決事項
- [ ] Graph APIアプリ登録（IT管理者申請待ち）
- [ ] Docker Desktopインストール可否（社内PC）
- [ ] Microsoft Plannerのグループ・プランID確認
- [ ] 担当者名マッピングリストの管理方法（Graph APIのユーザーリストと照合）
