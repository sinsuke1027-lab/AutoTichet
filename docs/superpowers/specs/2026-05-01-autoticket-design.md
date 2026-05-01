# AutoTicket 設計ドキュメント

**作成日**: 2026-05-01  
**最終更新**: 2026-05-01（LLMプロバイダー抽象化レイヤー追加）  
**フェーズ**: Phase 0〜1（ハーネス設定 + Pattern A基盤）  
**ステータス**: 承認済み

---

## 1. プロジェクト概要

### 目的
社内で発生するタスクを各種情報ソースからAIが自動抽出し、Microsoft Plannerへ自動起票することで、起票漏れ・手作業負担を解消する。

### インプットソース一覧

| # | インプット | 取得方法 | フェーズ |
|---|-----------|---------|---------|
| 1 | Outlookメール | Graph API ポーリング | Phase 1 |
| 2 | Teams会議 議事録 | Graph API ポーリング | Phase 1 |
| 3 | Teamsチャット | Graph API ポーリング | Phase 2 |
| 4 | OneNote メモ | Graph API ポーリング | Phase 2 |
| 5 | **Teamsボット（スクショ＋コメント）** | **Bot Framework Webhook** | **Phase 3** |
| 6 | 通話録音（電話等） | 音声ファイル → Whisper | Phase 4 |

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
│   ├── providers/                   # LLMプロバイダー抽象化レイヤー
│   │   ├── base.py                  # LLMProvider Protocol（インターフェース定義）
│   │   ├── ollama.py                # Ollama（ローカル・デフォルト）
│   │   ├── claude.py                # Anthropic Claude API
│   │   ├── gemini.py                # Google Gemini API
│   │   ├── azure_openai.py          # Azure OpenAI
│   │   └── factory.py               # 設定値からプロバイダーを生成
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
    source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot"]
    source_id: str                          # Graph API メッセージID or Bot activity ID
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

## 5. フェーズロードマップ（更新済み）

| フェーズ | 内容 | 前提条件 |
|---------|------|---------|
| Phase 0 | ハーネス設定 | ✅ 完了 |
| Phase 1 | Outlook・Teams議事録 → Planner起票 | Graph API申請承認 |
| Phase 2 | Teamsチャット・OneNote対応 | Phase 1完了 |
| Phase 3 | ローカルLLM基盤（Pattern B）+ 機密度振り分け + **Teamsボット（スクショ＋コメント）** | Docker環境・Ollama vision |
| Phase 4 | 通話録音対応（Whisper） | Phase 3完了 |

---

## 6. LLMプロバイダー抽象化レイヤー

### 設計方針
LLM処理をプロバイダー抽象化することで、`.env` の設定変更だけでバックエンドを切り替え可能にする。コードの変更は不要。

### プロバイダー一覧

| プロバイダー | テキスト処理 | 画像処理（Vision） | データ所在 | 推奨用途 |
|------------|------------|-----------------|----------|---------|
| `ollama` | ✅ qwen2.5:14b | ✅ llama3.2-vision | ローカル | 機密データ・コスト重視 |
| `claude` | ✅ claude-sonnet-4-6 | ✅ claude-sonnet-4-6 | Anthropicクラウド | 高精度・非機密データ |
| `gemini` | ✅ gemini-1.5-pro | ✅ gemini-1.5-pro | Googleクラウド | 高精度・非機密データ |
| `azure_openai` | ✅ GPT-4o | ✅ GPT-4o | Azureクラウド | 社内Azure環境がある場合 |

### セキュリティルール（機密度と連動）
```
classify_sensitivity の結果
    ├→ CONFIDENTIAL → 強制的に ollama（外部送信禁止）
    └→ NON_CONFIDENTIAL → .env の LLM_PROVIDER 設定に従う
```

外部APIを使う場合でも、機密データは必ずローカルOllamaで処理される。

### プロバイダー インターフェース（`src/providers/base.py`）
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    async def extract_tasks(self, text: str) -> list[ExtractedTask]: ...

@runtime_checkable
class VisionLLMProvider(Protocol):
    async def analyze_image(self, image: bytes, comment: str) -> str: ...
```

### 設定（`.env`）
```bash
# テキスト処理プロバイダー（ollama | claude | gemini | azure_openai）
LLM_PROVIDER=ollama

# 画像処理プロバイダー（ollama | claude | gemini | azure_openai）
LLM_VISION_PROVIDER=ollama
```

### ファクトリー（`src/providers/factory.py`）
設定値を読んで適切なプロバイダーインスタンスを返す。LangGraphエージェントはプロバイダーの実装を知らず、インターフェースだけに依存する。

---

## 7. Phase 3: Teamsボット（スクショ＋コメント）アーキテクチャ

### データフロー
```
[Teams チャンネル (#タスク起票) または Bot へのDM]
  ユーザー：スクショ画像 + コメント（例：「田中さんに来週までお願い」）
      ↓ Bot Framework Webhook（HTTPS POST）
[FastAPI /bot エンドポイント]
      ↓ 画像バイナリ + コメントテキストを抽出
[Ollama Vision LLM（llama3.2-vision）]  ← ローカル処理、外部送信なし
      ↓ 画像内容の説明文を生成
[LangGraph タスク抽出エージェント]
      ↓ 画像説明 + コメントを統合してタスク抽出
      ↓ 通常の承認フローへ（信頼スコア分岐）
[Microsoft Planner 起票]
      ↓ Teamsボットが起票結果をユーザーへ返信
```

### ボットの動作仕様
| 入力パターン | 処理 |
|------------|------|
| 画像 + コメントあり | 画像解析 + コメントを統合してタスク抽出（最高精度） |
| 画像のみ | 画像解析のみでタスク抽出（コメントなし） |
| テキストのみ | 通常テキスト処理（スクショなし） |

### ボット返信例
- 自動起票成功：「✅ タスク『田中さんへのA社資料作成依頼』を起票しました（期限：来週金曜）」
- 承認依頼：「📋 確認が必要です。以下のタスクを起票してよいですか？[承認] [却下]」
- 低信頼スコア：「⚠️ タスクを特定できませんでした。コメントで詳細を追加してください」

### 技術要件（Phase 3追加分）
- **Bot Framework 登録**: Teams Developer Portal（Azure ADアプリ登録）
- **Vision LLM**: Ollama + `llama3.2-vision`（ローカル処理）
- **公開エンドポイント**: 社内サーバーのHTTPS + Bot Framework向けFWルール
- **追加Graph APIスコープ**: 不要（Bot Framework経由で受信するため）

---

## 7. 未解決事項
- [ ] Graph APIアプリ登録（IT管理者申請待ち）
- [ ] Docker Desktopインストール可否（社内PC）
- [ ] Microsoft Plannerのグループ・プランID確認
- [ ] 担当者名マッピングリストの管理方法（Graph APIのユーザーリストと照合）
- [ ] Teamsボット用の公開HTTPSエンドポイント確保（Phase 3）
- [ ] Bot Framework登録の社内ポリシー確認（Phase 3）
- [ ] Ollama vision対応GPU/CPUスペック確認（llama3.2-vision動作要件）
