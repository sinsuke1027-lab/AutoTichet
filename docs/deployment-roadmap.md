# AutoTicket — 社内導入ロードマップ

最終更新: 2026-05-28

---

## 概要

本ドキュメントは、AutoTicket の開発完了後における社内展開の進め方を定める。
ツール開発フェーズ（Phase 1〜3）とは別軸で、**誰に・いつ・どのように展開するか** を管理するためのロードマップ。

---

## 前提：データセキュリティ方針

AutoTicket は処理対象テキストを **Pattern A / Pattern B** に自動分類する。

| 分類 | 判定条件 | LLM の扱い |
|------|---------|-----------|
| **Pattern A** | 機密キーワードなし | 外部 LLM（Gemini / Azure OpenAI）へ送信可 |
| **Pattern B** | 給与・人事・顧客名・契約金額 等を含む | 外部送信をブロック（現状）→ 順次対応（後述） |

**Pattern B の対応方針（段階的）:**

```
導入初期   → 完全ブロック（ユーザーにテキスト変更を促す）
全社展開時 → Azure OpenAI（M365 テナント内で処理）へ移行
高機密部署 → Ollama on-prem（社内サーバーで完結）を検討
```

---

## フェーズ構成

### Deployment Phase 0：環境整備（開発完了後 即時）

**目的:** 本番環境の構築・IT 部門承認取得

| タスク | 担当 | 備考 |
|-------|------|------|
| Entra ID アプリ登録（Graph API 権限申請） | IT 管理者 | `docs/graph-api-setup.md` を参照 |
| 本番 DB（PostgreSQL）サーバー準備 | IT インフラ | Docker Compose で起動可能 |
| 本番サーバー（FastAPI + React）デプロイ | 開発担当 | オンプレ or Azure App Service |
| Langfuse（監査ログ）Docker 起動 | 開発担当 | LLM 呼び出しの全量ロギング |
| セキュリティレビュー資料の提出 | 開発担当 | データフロー図 + Pattern A/B 分類説明 |
| IT 部門・法務部門への承認取得 | PJ 担当 | Pattern A のみ利用の段階で申請しやすい |

**承認に使うデータフロー説明:**

```
[Outlook / Teams] → [AutoTicket（社内サーバー）]
                          ↓ テキスト分類
                   ┌── Pattern A → [Gemini API（外部）]
                   └── Pattern B → [ブロック・処理しない]
```

---

### Deployment Phase 1：パイロット展開（〜開発完了後 1〜2ヶ月）

**目的:** 限定部署での実績作り・フィードバック収集

**対象部署の選定基準:**
- Pattern B キーワード（給与・人事・契約）が少ない業務が主体
- 推奨: 総務・広報・社内イベント企画・IT 部門

| チェック項目 | 内容 |
|------------|------|
| 対象ユーザー数 | 5〜20 名（チャンピオンユーザーを選出） |
| 利用開始前研修 | Pattern A/B の概念・「外部送信されないデータ」の説明 |
| フィードバック収集 | 2 週間ごとにヒアリング or アンケート |
| モニタリング | Langfuse で LLM 呼び出しログ・エラー率を確認 |
| 除外事項 | 人事・財務・法務部門はこの段階では対象外 |

**利用可能機能（Pattern A のみ）:**
- F-18/19 テキスト抽出（メール・議事録・チャット）→ タスク候補表示・起票
- F-29 AI チェック（タスク要件の明確化）
- F-32 サブタスク自動生成
- ダッシュボード・タスク一覧・ワークロード可視化

---

### Deployment Phase 2：LLM バックエンドの切り替え（〜開発完了後 3〜6ヶ月）

**目的:** Pattern B 対応の解禁・全社展開の準備

**推奨: Azure OpenAI への移行**

M365 テナントを既に保有している場合、Azure OpenAI は最もスムーズに承認を得やすい選択肢。

| 項目 | 内容 |
|------|------|
| 根拠 | Microsoft エンタープライズ契約でデータが AI 学習に使われない保証あり |
| 親和性 | Copilot for M365 と同じセキュリティ境界 |
| コスト | 従量課金（GPU サーバー不要） |
| 設定変更 | `.env` の `LLM_PROVIDER=azure_openai` に切り替えるだけ（コード変更不要）|

```env
# 切り替え例（コード変更なし）
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

**この段階で Pattern B 解禁のフロー:**

```
Pattern B テキスト → Azure OpenAI（M365 テナント内）→ タスク抽出
```

人事・財務・法務部門へのパイロット展開も開始可能になる。

---

### Deployment Phase 3：全社展開（〜開発完了後 6〜12ヶ月）

**目的:** 全部署への水平展開・運用定着

| タスク | 内容 |
|-------|------|
| 全社ロールアウト | 部署ごとに順次追加（IT → 総務 → 営業 → 人事・財務）|
| ヘルプデスク整備 | 社内 FAQ・チュートリアル動画・問い合わせ窓口 |
| 管理者研修 | IT 管理者・部門責任者向けの操作・設定研修 |
| KPI モニタリング | 起票数・AI 精度・ユーザー継続率を定期レポート |
| Entra ID グループ連携 | 部署グループとロール（一般/リーダー/管理者）の自動同期 |

---

### Deployment Phase 4：高機密部署対応（必要に応じて）

**目的:** Azure OpenAI でも不安な部署向けの完全社内処理

**Ollama on-prem 構成:**

```
Pattern B テキスト → Ollama（社内 GPU サーバー）→ 完全社内完結
```

| 項目 | 内容 |
|------|------|
| 必要インフラ | GPU サーバー（VRAM 8GB 以上推奨、qwen2.5:14b 使用）|
| コード変更 | `LLM_PROVIDER=ollama` + `OLLAMA_HOST=http://社内サーバー:11434` |
| 対象部署 | 法務・役員室・M&A 担当等、データ機密性が極めて高い部署 |
| 判断基準 | Azure OpenAI の Microsoft 契約条件で法務が承認できない場合のみ検討 |

---

## タイムライン概要

```
開発完了
    │
    ├── [D-Ph0] 環境整備・IT 承認      ── 1〜2週間
    │
    ├── [D-Ph1] パイロット展開          ── 1〜2ヶ月
    │         （Pattern A のみ、非機密部署）
    │
    ├── [D-Ph2] Azure OpenAI 移行      ── 3〜6ヶ月
    │         （Pattern B 解禁、人事・財務へ拡大）
    │
    ├── [D-Ph3] 全社展開               ── 6〜12ヶ月
    │         （全部署・Entra ID グループ連携）
    │
    └── [D-Ph4] Ollama on-prem          ── 必要に応じて
              （法務等の最高機密部署）
```

---

## 判断フロー：どの LLM を使うか

```
自社の状況は？
    │
    ├── M365（Azure）テナントあり
    │       └── → Azure OpenAI を採用（推奨）
    │             ・IT 承認取りやすい
    │             ・GPU サーバー不要
    │
    ├── M365 なし / Azure 契約なし
    │       └── → Gemini（Pattern A のみ）でパイロット開始
    │             ・Pattern B は引き続きブロック
    │             ・Ollama の導入を並行検討
    │
    └── 機密性が極めて高い（法務・役員）
            └── → Ollama on-prem を検討
                  ・GPU サーバー調達が必要
                  ・導入コスト高め
```

---

## 関連ドキュメント

| ドキュメント | 内容 |
|------------|------|
| [docs/requirements.md](requirements.md) | 機能要件・フェーズ構成（開発フェーズ）|
| [docs/graph-api-setup.md](graph-api-setup.md) | IT 管理者向け Graph API 申請手順 |
| [docs/startup-guide.md](startup-guide.md) | 開発環境・本番起動手順・**社内メンバーへの共有手順（社内 LAN 共有 / Docker 本番デプロイ）**|
