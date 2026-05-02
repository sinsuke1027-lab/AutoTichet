# AutoTicket — 要件定義書

最終更新: 2026-05-02  
フェーズ: Phase 1 実装中  
ステータス: ドラフト確定版

---

## 1. プロジェクト目的

Outlookメール・Teams会議議事録からAIがタスクを自動抽出し、Microsoft Plannerおよびは Microsoft To Do へ自動起票する。担当者・期限・優先度をAIが判断し、信頼スコアに基づいて自動起票／承認依頼／ログのみの3ルートで処理する。

---

## 2. 機能要件（FR）

### 2-1. 入力・取得

| ID | 要件 | Graph API スコープ | 対象フェーズ |
|----|------|-------------------|------------|
| FR-01 | Outlookメール未読取得 | `Mail.Read` | Phase 1 |
| FR-02 | Teams会議文字起こし取得 | `OnlineMeetings.Read.All` | Phase 1 |
| FR-03-a | Teamsチャットメッセージ取得 | `ChannelMessage.Read.All` | Phase 2 |
| FR-03-b | OneNoteページ取得 | `Notes.Read.All` | Phase 2 |
| FR-03-c | Teamsボット経由スクショ＋コメント受信 | Bot Framework Webhook | Phase 3 |

### 2-2. AI処理

| ID | 要件 | 備考 |
|----|------|------|
| FR-03 | 機密度分類（キーワードベース Pattern A/B） | Pattern B はローカルLLM強制（FR-13参照） |
| FR-04 | タスク自動抽出 | 抽出フィールド：タイトル・担当者・期限・優先度・カテゴリ・visibility |
| FR-05 | 信頼スコアによる承認フロー分岐 | スコア ≥ 0.8 → 自動起票、0.5〜0.8 → 承認依頼、< 0.5 → ログのみ |
| FR-12 | LLMプロバイダー切り替え | Ollama / Claude / Gemini / Azure OpenAI を `.env` で選択 |
| FR-13 | 機密データのローカルLLM強制処理 | Pattern B 分類時は Ollama を強制使用、外部LLMへの送信を禁止 |

### 2-3. 起票・出力

| ID | 要件 | 起票先 | 対象フェーズ |
|----|------|--------|------------|
| FR-06 | Microsoft To Do 起票（private タスク） | To Do（個人） | Phase 1 |
| FR-07 | Microsoft Planner 起票（team / all タスク） | Planner（M365 Group） | Phase 1 |

**visibilityと起票先の対応:**

| visibility | 起票先 |
|-----------|--------|
| `private` | 担当者の Microsoft To Do |
| `team` | 担当者が所属する部署の Planner |
| `all` | 全社共有 Planner |

### 2-4. 状態管理・インフラ

| ID | 要件 | 備考 |
|----|------|------|
| FR-08 | 処理済みメッセージID管理（SQLite 重複防止） | `processed_messages` テーブル（詳細は db-schema.md） |
| FR-09 | ポーリングスケジューラー（5〜10分間隔） | APScheduler で FastAPI 起動時にバックグラウンド実行 |

### 2-5. APIエンドポイント

| ID | 要件 | エンドポイント |
|----|------|--------------|
| FR-10 | 手動タスク起票 | `POST /tasks/extract?text=...&source_type=...` |
| FR-11 | ヘルスチェック | `GET /health` → `{"status": "ok"}` |

---

## 3. 非機能要件（NFR）

| ID | カテゴリ | 要件 |
|----|--------|------|
| NFR-01 | セキュリティ | 機密データ（Pattern B）を外部LLM（OpenAI等）へ一切送信しない。違反時はリクエストをブロックして Langfuse にエラーログを記録する |
| NFR-02 | 型安全 | 全Pythonコードに引数・戻り値の型ヒントを付与し、`mypy --strict` が通ること |
| NFR-03 | データモデル | Pydantic v2 のみ使用。生の `dict` をビジネスロジック間で引き回さない |
| NFR-04 | 非同期処理 | ファイルI/O・ネットワークI/O・DB操作はすべて `async/await` で実装する |
| NFR-05 | 最小権限 | Graph API スコープは必要最小限（Phase 1: 4スコープ `Mail.Read`, `OnlineMeetings.Read.All`, `Tasks.ReadWrite`, `Group.Read.All`） |
| NFR-06 | 監査ログ | Langfuse に全LLM呼び出し・信頼スコア・起票結果を記録する。ログの改ざん・削除を行わない |
| NFR-07 | コード品質 | `ruff check`・`ruff format`（行長100）・`mypy --strict` がすべてパスすること |
| NFR-08 | テスト | `pytest` ユニットテスト必須。LLM・Graph API は必ずモックで代替 |
| NFR-09 | 設定管理 | `.env` をコミットしない。シークレット（クライアントID・シークレット・APIキー）は環境変数のみで管理 |

---

## 4. 制約条件

| 項目 | 制約 |
|------|------|
| OS | Windows 11 Pro |
| Python | 3.11 以上 |
| M365ライセンス | Power Automate Standard（HTTP コネクタ使用不可） |
| Azure サブスクリプション | なし（M365テナントの Azure AD のみ利用可） |
| データ保管場所 | M365テナント内またはローカルのみ（外部クラウドストレージ禁止） |
| LLM外部送信 | Pattern B（機密）データの外部送信禁止 |
| Graph API 認証 | Client Credentials フロー（アプリ権限）のみ。ユーザー委任権限は Phase 1 では使用しない |

---

## 5. フェーズ構成

| フェーズ | 内容 | ステータス |
|---------|------|----------|
| Phase 0 | ハーネス設定（CLAUDE.md・スキル・pyproject.toml） | 完了 |
| Phase 1 | Outlook・Teams → Planner / To Do 自動起票（Pattern A） | 進行中 |
| Phase 2 | Teamsチャット・OneNote 対応 | 未着手 |
| Phase 3 | ローカルLLM基盤（Ollama qwen2.5:14b）+ Teamsボット（スクショ起票） | 未着手 |
| Phase 4 | 通話録音対応（Whisper） | 未着手 |
| Phase 5 | コア管理機能（Teams通知・二重登録防止・リスケジュール・サブタスク） | 未着手 |
| Phase 6 | ビジュアライゼーション（カンバン・ガント・マイルストーン・依存関係） | 未着手 |
| Phase 7 | AI高度化（最適アサイン・遅延リスク予測・自動棚卸し） | 未着手 |
| Phase 8 | リアルタイム・インプット拡張（音声ストリーミング・右クリック起票） | 未着手 |
| Phase 9 | モバイル対応（PWA化） | 未着手 |

---

## 6. ユースケース概要（Phase 1）

```
UC-01: メール自動起票
  Actor: システム（スケジューラー）
  前提: Graph API 認証済み
  手順:
    1. スケジューラーが5〜10分間隔で未読メールを取得
    2. 処理済みIDをチェックし、未処理のみ対象にする
    3. 機密度を分類し、LLMプロバイダーを選択
    4. LLM でタスク抽出（タイトル・担当者・期限・優先度・visibility）
    5. 信頼スコアで分岐：自動起票 / 承認依頼 / ログのみ
    6. 処理済みIDをSQLiteに記録

UC-02: 手動タスク起票
  Actor: エンジニア / 運用者
  手順:
    1. POST /tasks/extract にテキストと source_type を渡す
    2. UC-01 の手順 3〜5 と同じ処理を実行
    3. 抽出タスクのリストをレスポンスとして返す
```

---

## 7. データフロー概要（Phase 1）

```
[Outlook メール / Teams 文字起こし]
        |
        | Graph API (MSAL Client Credentials)
        v
[FastAPI + APScheduler]
        |
        v
[LangGraph エージェント]
    classify_sensitivity
        → extract_tasks (LLM)
            → match_assignee
                → score_confidence
                    → route_approval
                        ├─ auto_create     (score ≥ 0.8) → Planner / To Do
                        ├─ request_approval (0.5〜0.8)  → Teams 承認通知
                        └─ log_only        (score < 0.5) → Langfuse ログのみ
        |
[SQLite: processed_messages]  — 処理済みID記録
[Langfuse: 監査ログ]          — 全LLM呼び出し・信頼スコア記録
```
