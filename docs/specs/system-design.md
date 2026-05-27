# AutoTicket 設計ドキュメント

**作成日**: 2026-05-01  
**最終更新**: 2026-05-15  
**フェーズ**: Phase 0〜9（全フェーズ設計）  
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

## 5. フェーズロードマップ（全体）

### 起票パイプライン（Phase 0〜4）

| フェーズ | 内容 | 前提条件 |
|---------|------|---------|
| Phase 0 | ハーネス設定 | ✅ 完了 |
| Phase 1 | Outlook・Teams議事録 → Planner起票 | Graph API申請承認 |
| Phase 2 | Teamsチャット・OneNote対応 | Phase 1完了 |
| Phase 3 | ローカルLLM基盤 + 機密度振り分け + Teamsボット（スクショ＋コメント） | Docker・Ollama vision |
| Phase 4 | 通話録音対応（Whisper） | Phase 3完了 |

### ポスト起票機能（Phase 5〜9）

| フェーズ | 内容 | 前提条件 |
|---------|------|---------|
| Phase 5 | コア管理機能（通知・重複検知・リスケ・サブタスク・要件明確化） | Phase 1完了・カスタムUI基盤 |
| Phase 6 | ビジュアライゼーション（カンバン/ガント/カレンダー・マイルストーン・依存関係・ダッシュボード） | Phase 5完了 |
| Phase 7 | AI高度化（最適アサイン・遅延リスク予測・棚卸し提案・引き継ぎドキュメント） | Phase 3完了（LLM基盤） |
| Phase 8 | リアルタイム機能（会議音声リアルタイム起票・チャットボット対話・右クリック起票） | Phase 4完了 |
| Phase 9 | モバイルアプリ | Phase 6完了 |

---

## 6. ポスト起票機能 詳細仕様

起票パイプライン（Phase 1〜4）完了後に実装する機能群。Phase番号は実装優先順序を示す。

---

### Phase 5：コア管理機能

#### 5-1. Teams通知（#14）
タスク割り当て・期限変更・承認依頼などのイベント発生時にTeamsで自動通知。
- 実装：Graph API `chatMessage` または Adaptive Card via Bot Framework
- 通知先：担当者・作成者・マネージャー（ロール別設定可）

#### 5-2. 二重登録防止（#18）
新規タスク起票時に類似タスクをベクトル検索で検出し、重複を警告。
- 実装：タスクタイトル・説明をEmbedding化（Ollama embedding or 外部API）→ cosine類似度で閾値判定
- 閾値：類似度 0.85以上で「類似タスクが存在します」と警告・確認を促す

#### 5-3. リスケジュール機能（#19）
期限・担当者の変更を最小操作で完結。
- 実装：Planner/To Do の `PATCH /planner/tasks/{id}` または `/todo/lists/{listId}/tasks/{taskId}`
- UI：カスタムUI（Phase 3以降）でカレンダーピッカーによる日付変更

#### 5-4. サブタスク自動作成（#20）
メインタスクをLLMで分解し、サブタスクとして自動生成。
- 実装：LangGraphエージェントにサブタスク分解ノードを追加
- 出力：Plannerのチェックリスト（`checklist`フィールド）または独立タスクとして子起票
- プロンプト：「このタスクを完了するために必要なステップを3〜7個に分解してください」

#### 5-5. タスク要件明確化プロンプト（#7）
起票時に目的・完了条件・粒度が不明確なタスクをAIが検知し、補足情報を促す。
- 判定条件：タイトルが10文字以下 / 完了条件のキーワードなし / 担当者・期限が共になし
- 動作：Teamsボット or 承認フローで「以下の情報を追記してください」とメッセージ送信

---

### Phase 6：ビジュアライゼーション（カスタムUI必須）

#### 6-1. カンバン/ガント/カレンダー相互切替（#9）
同一タスクデータを3ビューで瞬時に切り替え。
- カンバン：状態（未着手/進行中/完了）×担当者のボード表示
- ガント：開始日・期限をタイムライン表示、依存関係の矢印表示
- カレンダー：期限日ベースの月次/週次表示
- データソース：Graph API（Planner + To Do）から取得、フロントエンドでレンダリング

#### 6-2. マイルストーン設定（#10）
プロジェクト上の節目を設定し、残日数・達成度（完了タスク数/全タスク数）を表示。
- 実装：カスタムDBにmilestoneテーブルを追加。Planner BucketをマイルストーングループとしてマッピングをCaption可能。

#### 6-3. 依存関係管理（#12）
タスク間の前後関係（Aが完了しないとBを開始できない）を設定・可視化。
- 実装：カスタムDB `task_dependencies（task_id, depends_on_task_id）`
- 可視化：ガントチャートで依存矢印を描画、未完了の前提タスクがある場合はロック表示

#### 6-4. ダッシュボード・レポーティング（#11）
- メトリクス：チーム別完了率、平均リードタイム、期限超過件数、担当者別負荷
- 実装：Langfuseの集計データ + Graph APIデータをFastAPIで集約 → フロントでcharts描画
- エクスポート：CSV / PDF

---

### Phase 7：AI高度化機能

#### 7-1. 最適アサイン提案（#3）
タスク内容・スキルセット・現在の担当件数からLLMが最適担当者を推薦。
- 実装：ユーザープロファイル（スキルタグ・役割）をDB管理 → タスク説明とのセマンティックマッチング
- 出力：「推奨：田中さん（適合度87%）」のような提案をTeamsボットまたは承認フローで表示

#### 7-2. 遅延リスクAI予測（#4）
過去の類似タスクの完了傾向から、期限超過確率（%）を予測して事前警告。
- 実装：完了済みタスクの履歴をLangfuseから収集 → カテゴリ・担当者・タスク規模で類似タスクを検索 → 完了率から確率算出
- 警告タイミング：期限の3日前に確率 60%以上で「遅延リスクあり」とTeams通知

#### 7-3. 自動棚卸し提案（#6）
1ヶ月以上更新のないタスクを定期スキャンし、アーカイブ・削除・再設定を提案。
- 実装：週次スケジューラー（APScheduler）で `updatedAt` が30日以上経過したタスクを検出
- 提案：担当者にTeams通知「このタスクは放置されています。どうしますか？ [完了] [削除] [延長]」

#### 7-4. 引き継ぎドキュメント自動生成（#2）
休暇・担当変更時に未完了タスクの状況をまとめた引き継ぎメモをAIが作成。
- 実装：対象ユーザーの未完了タスク一覧をGraph APIで取得 → LLMが「現状・残作業・注意点」を整理
- 出力：Teamsチャット送信 または OneNote ページとして保存

---

### Phase 8：リアルタイム・インプット拡張

#### 8-1. 会議音声リアルタイム起票（#5）
Web会議の音声をリアルタイム解析し、アクションアイテムをその場でタスク化。
- 実装：WebSocket + faster-whisper ストリーミング → LangGraph即時抽出 → Planner起票
- 前提：Teams会議の音声ストリームまたは参加者側の音声キャプチャ（技術的制約要確認）

#### 8-2. チャットボット対話登録（#1）
「明日までに〇〇の資料を作る」とTeamsボットに話しかけるだけで起票。
- 実装：Phase 3のTeamsボットを拡張。自然文から1クリック起票。
- 確認なし自動起票（信頼スコアが常に高いため）

#### 8-3. 右クリック即タスク化（#17）
メール・チャットのテキストを選択→右クリックでワンアクション起票。
- 実装：Outlookアドイン（Office.js）またはTeamsメッセージ拡張（Message Extension）
- 選択テキスト + コンテキスト（送信者・日時）をFastAPIに送信してタスク化

---

### Phase 9：モバイルアプリ

#### 9-1. スマートフォン対応（#15）
カスタムWebアプリのPWA（Progressive Web App）化、または React Native アプリ。
- Phase 6のカスタムUIをPWAとして公開することで、追加開発コスト最小化
- 閲覧・ステータス更新・簡易コメント機能を優先実装

---

### 要検討機能

| # | 機能 | 検討事項 |
|---|------|---------|
| #8 | ペアワークモード | WebSocket + リアルタイム同期基盤が必要。コスト対効果を要検討 |
| #13 | タスク内でコミュニケーション機能 | TeamsチャットやPlanner内コメントで代替可能か要検討。重複開発リスクあり |

---

## 7. LLMプロバイダー抽象化レイヤー

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

## 7. マルチユーザー・部署別アクセス制御設計

### 基本方針
**Phase 1-2はM365のグループ権限モデルをそのまま活用する。** アクセス制御をゼロから実装せず、M365 Groupのメンバーシップ＝部署の権限として扱う。Phase 3以降でカスタムWeb UIを作る際に FastAPI 側でロール制御を追加する。

---

### ロールモデル

| ロール | 対象 | 見えるタスク |
|--------|------|------------|
| `admin` | システム管理者 | 全部署・全メンバーの全タスク |
| `manager` | 部署責任者 | 自部署のチームタスク全件 + 自分のプライベートタスク |
| `member` | 一般メンバー | 自分のプライベートタスク + 所属部署のチームタスク |

---

### タスク可視性（visibility）と起票先

```
ExtractedTask.visibility
    ├→ "private"  → Microsoft To Do（本人の個人リスト）
    ├→ "team"     → 部署別 Planner プラン（M365 Group に紐づく）
    └→ "all"      → 全社共通 Planner プラン
```

#### M365テナント構造

```
M365テナント
  ├── M365 Group: 営業部  → Planner Plan: 営業部タスク  （営業部メンバーのみ閲覧可）
  ├── M365 Group: IT部   → Planner Plan: IT部タスク    （IT部メンバーのみ閲覧可）
  ├── M365 Group: 総務部  → Planner Plan: 総務部タスク  （総務部メンバーのみ閲覧可）
  └── M365 Group: 全社共通 → Planner Plan: 全社タスク   （全員閲覧可）

各ユーザーの Microsoft To Do → private タスク（本人のみ）
```

PlannerはM365 Groupのメンバーシップを自動的に引き継ぐため、部署の追加・メンバー変更はM365管理者側で完結する。

---

### 可視性の自動判定ロジック

LangGraphエージェントがテキストから可視性を推定する：

| 判定条件 | visibility |
|---------|-----------|
| 特定の個人宛（「〇〇さんお願いします」） | `private` |
| 部署・チーム宛（「営業チームで対応」「皆さんへ」） | `team` |
| 全社・会社全体（「全部署共有」「社内周知」） | `all` |
| 判定不能 | `team`（保守的デフォルト） |

---

### 拡張データモデル

```python
class ExtractedTask(BaseModel):
    is_task: bool
    title: str
    assignee_user_id: str | None      # Azure AD Object ID
    assignee_name: str | None         # 表示名（照合失敗時のフォールバック）
    department_id: str | None         # M365 Group ID（部署）
    deadline: date | None
    priority: Literal["high", "medium", "low"]
    category: Literal["HR", "IT", "総務", "その他"]
    visibility: Literal["private", "team", "all"]  # 追加
    confidence_score: float
    source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot"]
    source_id: str
```

---

### 起票先ルーティング（`src/services/routing.py`）

```
visibility = "private"
    → Graph API: POST /users/{assignee_id}/todo/lists/{listId}/tasks
    → 本人のTo Doに作成（Tasks.ReadWrite.All 権限が必要）

visibility = "team"
    → Graph API: POST /planner/tasks
    → planId = departments[department_id].planner_plan_id
    → 部署のPlannerプランに作成

visibility = "all"
    → Graph API: POST /planner/tasks
    → planId = COMPANY_WIDE_PLAN_ID（全社共通プラン）
```

---

### 追加Graph API スコープ（Phase 1に追加申請）

| スコープ | 用途 |
|---------|------|
| `Tasks.ReadWrite.All` | To Doプライベートタスク作成（全ユーザー分） |
| `Group.Read.All` | 部署一覧（M365 Group）の取得 |

---

### Phase 3以降：カスタムWeb UI 対応時の追加設計

FastAPI に以下を追加する：

```
GET /api/tasks
  → 呼び出しユーザーのAzure ADトークンを検証
  → ロールに応じてフィルタリング:
     admin   → Planner全プラン + 全To Doをaggregateして返す
     manager → 自部署Planner + 自分のTo Do
     member  → 自部署Planner（自分担当分） + 自分のTo Do

認証: Azure AD MSAL (Authorization Code Flow)
```

---

## 8. 未解決事項
- [ ] Graph APIアプリ登録（IT管理者申請待ち）→ `docs/graph-api-setup.md` 提出
- [ ] Docker Desktopインストール可否（社内PC）
- [ ] 部署ごとのM365 Group・Planner プランID確認（IT管理者に確認）
- [ ] 全社共通Plannerプランの作成・プランID確認
- [ ] 担当者名マッピング：Graph API `User.Read.All` で自動取得
- [ ] To Doのデフォルトリスト取得方法確認（`GET /users/{id}/todo/lists`）
- [ ] Teamsボット用の公開HTTPSエンドポイント確保（Phase 3）
- [ ] Bot Framework登録の社内ポリシー確認（Phase 3）
- [ ] Ollama vision対応GPU/CPUスペック確認（llama3.2-vision動作要件）
