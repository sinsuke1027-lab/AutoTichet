# AutoTicket Web アプリ 設計仕様書

**作成日**: 2026-05-18
**最終更新**: 2026-05-18
**ステータス**: 承認済み（アーキテクチャ・データモデル確定）
**対象読者**: フロントエンド／バックエンドエンジニア

---

## 1. 背景・目的

### 設計変更の経緯

当初 AutoTicket は Microsoft Planner / To Do を起票先・UI として想定していたが、社内メンバーからの機能要望（37機能）を統合した結果、以下の理由でカスタム Web アプリへの移行を決定した。

| 制約 | 内容 |
|------|------|
| 工数管理（F-12） | Planner / To Do API に工数フィールドが存在しない |
| カスタム列・タグ（F-03） | Planner はラベル7色のみ、列追加不可 |
| ワークロード集計（F-13） | API で集計クエリが出せない |
| タスク依存関係（F-23） | Planner に依存関係の概念がない |
| コメント＋メンション（F-05） | To Do のコメント API は読み取り専用に近い |

### システムの目的（Word 要件定義書より）

「入力負荷を最小化し、チームと個人の仕事を可視化する」

- 入力しなくてもタスクが生まれる環境（メール・会議・チャット等からの自動起票）
- 今日やるべきこと・誰が忙しいかの即時把握（ダッシュボード・ワークロード）
- 柔軟なビュー切り替え（ガント/カンバン/カレンダー）

---

## 2. アーキテクチャ（確定）

### 全体構成

```
[React + TypeScript SPA]
        ↕ REST API（JSON）
[FastAPI バックエンド（既存を拡張）]
        ↕
[PostgreSQL（タスク・工数・コメント・依存関係等）]
[SQLite（処理済みID管理 ※既存のまま）]
[Langfuse（監査ログ ※既存のまま）]

[FastAPI] ←→ [Microsoft Graph API（メール・Teams・Forms/SharePoint）]
[FastAPI] ←→ [Entra ID（MSAL 認証）]
[LangGraph エージェント（既存・変更なし）]
```

### 既存からの主な変更点

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| タスク保存先 | Microsoft Planner / To Do | PostgreSQL |
| タスク閲覧UI | Planner / To Do の画面 | カスタム React SPA |
| 認証 | なし（サーバー間のみ） | Entra ID（MSAL）|
| DB | SQLite のみ | PostgreSQL（タスク本体）+ SQLite（処理済みID）|
| LangGraph パイプライン | — | **変更なし** |
| Graph API 連携 | — | **変更なし** |
| Langfuse 監査ログ | — | **変更なし** |

---

## 3. 技術スタック

### フロントエンド（新規）

| 種別 | ライブラリ | バージョン目安 | 用途 |
|------|-----------|-------------|------|
| フレームワーク | React + TypeScript | 18.x | SPA 基盤 |
| ビルドツール | Vite | 5.x | 高速ビルド |
| UI コンポーネント | Ant Design | 5.x | フォーム・テーブル・モーダル等 |
| データフェッチ | TanStack Query | 5.x | REST API キャッシュ・同期 |
| 状態管理 | Zustand | 4.x | グローバル状態（軽量） |
| グラフ・チャート | Recharts | 2.x | ダッシュボード・ワークロード |
| ドラッグ&ドロップ | dnd-kit | 6.x | カンバン・日程D&D |
| カレンダー | FullCalendar | 6.x | カレンダービュー |
| ガントチャート | gantt-task-react | 最新安定版 | ガントビュー・依存関係矢印 |
| 認証 | @azure/msal-react | 2.x | Entra ID ログイン |
| ルーティング | React Router | 6.x | SPA ルーティング |

### バックエンド（既存を拡張）

| 種別 | ツール | 変更 |
|------|--------|------|
| API フレームワーク | FastAPI + uvicorn | 既存 |
| LLM オーケストレーション | LangGraph | 既存 |
| データモデル | Pydantic v2 | 既存 |
| DB クライアント | asyncpg + SQLAlchemy 2.x | 新規追加（PostgreSQL 用）|
| 既存 DB | aiosqlite（SQLite） | 処理済みID管理のみ継続 |
| マイグレーション | Alembic | 新規追加 |
| 認証 | python-jose + MSAL | 新規追加 |
| M365 連携 | MSAL Python + httpx | 既存 |
| 監査ログ | Langfuse | 既存 |

---

## 4. データモデル（PostgreSQL）

### 4-1. テーブル一覧

```sql
-- ① プロジェクト
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active',  -- active | archived | completed
    created_by  TEXT NOT NULL,                   -- Entra ID オブジェクトID
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ② タスク
CREATE TABLE tasks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID REFERENCES projects(id) ON DELETE SET NULL,
    parent_task_id   UUID REFERENCES tasks(id) ON DELETE SET NULL,  -- サブタスク
    title            TEXT NOT NULL,
    description      TEXT,
    status           TEXT NOT NULL DEFAULT 'not_started',
        -- not_started | in_progress | completed | cancelled
    priority         TEXT NOT NULL DEFAULT 'medium',
        -- low | medium | high | urgent
    assignee_id      TEXT,                        -- Entra ID オブジェクトID
    due_date         DATE,
    start_date       DATE,
    visibility       TEXT NOT NULL DEFAULT 'team',-- private | team | all
    source_type      TEXT,
        -- email | meeting | chat | onenote | teams_bot | manual | form | template
    source_id        TEXT,                        -- 元メッセージ/フォームID
    confidence_score FLOAT,                       -- AI 抽出の信頼スコア
    route            TEXT,
        -- auto_create | request_approval | log_only
    created_by       TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ③ 工数管理
CREATE TABLE task_work_hours (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id          UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id          TEXT NOT NULL,               -- Entra ID オブジェクトID
    estimated_hours  FLOAT,                       -- 予定工数
    actual_hours     FLOAT,                       -- 実績工数
    notes            TEXT,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ④ コメント
CREATE TABLE task_comments (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id          UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id        TEXT NOT NULL,               -- Entra ID オブジェクトID
    content          TEXT NOT NULL,
    mentions         TEXT[] DEFAULT '{}',          -- メンション対象 Entra ID リスト
    sharepoint_links TEXT[] DEFAULT '{}',          -- 添付 SharePoint URL
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ⑤ タスク依存関係
CREATE TABLE task_dependencies (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id              UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id   UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (task_id, depends_on_task_id)
);

-- ⑥ タグ
CREATE TABLE task_tags (
    task_id  UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    PRIMARY KEY (task_id, tag)
);

-- ⑦ マイルストーン
CREATE TABLE milestones (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    due_date   DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ⑧ テンプレート
CREATE TABLE task_templates (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    description   TEXT,
    template_data JSONB NOT NULL,  -- タスクフィールド＋サブタスク構造
    created_by    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ⑨ ユーザープロファイル（Entra ID キャッシュ）
CREATE TABLE user_profiles (
    user_id               TEXT PRIMARY KEY,  -- Entra ID オブジェクトID
    display_name          TEXT NOT NULL,
    email                 TEXT,
    role                  TEXT DEFAULT 'member',
        -- member | leader | manager | admin
    skills                JSONB DEFAULT '[]',
    capacity_hours_per_day FLOAT DEFAULT 8.0,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4-2. 工数 AI 最適化の仕組み

- `task_work_hours` に蓄積された `(source_type, estimated_hours, actual_hours)` のペアを学習データとして使用
- タスク登録時に同種タスクの過去実績中央値を `estimated_hours` の初期値として自動セット（F-28）
- 定期バッチで実績データを集計し、カテゴリ別標準工数モデルを更新

---

## 5. 機能一覧（フェーズ別）

### Phase 1（Must）— 基盤構築と可視化の解消

| F-ID | 機能名 | 実装ポイント |
|------|--------|------------|
| F-01 | タスク手動登録・編集・削除・複製 | React フォーム ＋ `POST/PUT/DELETE /api/v1/tasks` |
| F-02 | タスク一覧表示（検索・絞り込み・並び替え） | TanStack Query ＋ クエリパラメータ |
| F-03 | タスク詳細管理（工数・進捗・ステータス・タグ・列追加） | Ant Design Table カスタム列 ＋ `task_tags` |
| F-04 | 二重登録防止（類似タスク検出・警告） | タイトル類似度チェック（Levenshtein or Embedding） |
| F-05 | コメント機能（リンク・メンション → Teams 通知） | `task_comments` テーブル ＋ Graph API 通知 |
| F-06 | プロジェクト管理（グルーピング・連携） | `projects` テーブル ＋ プロジェクト別タスク一覧 |
| F-08 | 権限管理（一般・リーダー・管理者ロール） | `user_profiles.role` ＋ FastAPI 依存注入でロール検証 |
| F-09 | 1日スケジュール表示（今日やること・期限超過） | `GET /api/v1/dashboard/today` ＋ `dashboard/overdue` |
| F-10 | ダッシュボード（未完了タスク・各種指標） | Recharts ＋ `GET /api/v1/dashboard/summary` |
| F-11 | ドラッグ&ドロップ（日内スケジュール配置） | dnd-kit ＋ `start_date` / `due_date` 更新 |
| F-12 | 予定/実績管理（工数入力・比較） | `task_work_hours` テーブル ＋ 入力フォーム |
| F-13 | ワークロード画面（負荷・余力・超過可視化） | `GET /api/v1/dashboard/workload` ＋ Recharts |
| F-16 | Microsoft Forms 連携（SharePoint → 自動起票） | Graph API `GET /sites/{id}/lists/{id}/items` ポーリング |
| F-17 | Outlook / Teams 右クリック即タスク化 | Outlook アドイン（Office.js）または Teams メッセージ拡張 |
| F-18 | トランスクリプト自動作成 | **既存実装済み**（LangGraph パイプライン） |
| F-19 | 議事録自動作成 | **既存実装済み**（LangGraph パイプライン） |
| F-21 | Teams 通知（アサイン・期限切れ・メンション） | Graph API `POST /chats/{id}/messages` |

### Phase 2（Should）— UI 高度化と起票の完全自動化

| F-ID | 機能名 | 実装ポイント |
|------|--------|------------|
| F-07 | 個人 ToDo 管理（非公開） | `visibility = 'private'` でフィルタリング |
| F-14 | 負荷アラート（工数超過・期限超過警告） | ワークロード閾値チェック ＋ バナー通知 |
| F-15 | テンプレート機能（定型業務雛形・一括作成） | `task_templates` テーブル ＋ `POST /api/v1/templates/{id}/apply` |
| F-22 | ガント/カンバン/カレンダービュー切替 | gantt-task-react / dnd-kit カンバン / FullCalendar |
| F-23 | ガントチャートでの依存関係可視化 | `task_dependencies` ＋ gantt-task-react 依存矢印 |
| F-24 | チャットボット対話起票（Teams Bot） | **既存 Phase 3 実装に統合**（変更なし） |
| F-25 | スクショからタスク化 | **既存 Phase 3 実装に統合**（変更なし） |
| F-26 | マニュアルから自動生成 | PDF / Word 解析 → LangGraph でタスク群生成 |
| F-27 | 過去実績参照（同種作業の参考情報表示） | `task_work_hours` 集計 ＋ タスク詳細 UI に表示 |
| F-28 | 工数自動初期値設定（カテゴリ別標準工数） | 蓄積実績から中央値を計算 ＋ タスク作成時に自動入力 |
| F-29 | タスク要件明確化プロンプト | **既存 Phase 5 実装に統合**（変更なし） |
| F-30 | 遅延リスク AI 予測 | **既存 Phase 7 実装に統合**（変更なし） |
| F-31 | 自動棚卸し提案 | **既存 Phase 7 実装に統合**（変更なし） |
| F-32 | サブタスク自動作成 | **既存 Phase 5 実装に統合**（変更なし） |
| F-36 | リスケジュール（期間再入力なし） | `due_date` オフセット計算 ＋ 一括更新 API |

### Phase 3（Could）— 自律的タスク管理

| F-ID | 機能名 | 実装ポイント |
|------|--------|------------|
| F-20 | 会議音声リアルタイム起票 | **既存 Phase 8 実装に統合**（変更なし） |
| F-33 | 引き継ぎドキュメント自動生成 | **既存 Phase 7 実装に統合**（変更なし） |
| F-34 | 最適アサイン提案 | **既存 Phase 7 実装に統合**（変更なし） |
| F-35 | マイルストーン高度管理 | `milestones` テーブル ＋ ガント統合表示 |
| F-37 | ペアワークモード（リアルタイム共同編集） | WebSocket（FastAPI） ＋ フロント同期（要検討） |

> **対象外**: モバイル専用アプリ、タスク内チャット機能、基幹システム連携

---

## 6. API 設計

### 認証

```
POST /api/v1/auth/token      -- MSAL トークン検証・セッション発行
GET  /api/v1/auth/me         -- ログインユーザー情報取得
```

### プロジェクト

```
GET    /api/v1/projects                     -- 一覧
POST   /api/v1/projects                     -- 作成
GET    /api/v1/projects/{id}                -- 詳細
PUT    /api/v1/projects/{id}                -- 更新
DELETE /api/v1/projects/{id}                -- 削除
GET    /api/v1/projects/{id}/tasks          -- プロジェクト内タスク一覧
GET    /api/v1/projects/{id}/milestones     -- マイルストーン一覧
```

### タスク

```
GET    /api/v1/tasks                        -- 一覧（クエリ: status, assignee, project, due_before, tag 等）
POST   /api/v1/tasks                        -- 手動作成
GET    /api/v1/tasks/{id}                   -- 詳細
PUT    /api/v1/tasks/{id}                   -- 更新
DELETE /api/v1/tasks/{id}                   -- 削除（論理削除）
GET    /api/v1/tasks/{id}/subtasks          -- サブタスク一覧
POST   /api/v1/tasks/{id}/subtasks          -- サブタスク作成
GET    /api/v1/tasks/{id}/comments          -- コメント一覧
POST   /api/v1/tasks/{id}/comments          -- コメント投稿
GET    /api/v1/tasks/{id}/dependencies      -- 依存関係一覧
POST   /api/v1/tasks/{id}/dependencies      -- 依存関係追加
DELETE /api/v1/tasks/{id}/dependencies/{dep_id}
GET    /api/v1/tasks/{id}/work-hours        -- 工数一覧
POST   /api/v1/tasks/{id}/work-hours        -- 工数記録
PUT    /api/v1/tasks/{id}/work-hours/{wh_id}
```

### ダッシュボード

```
GET /api/v1/dashboard/summary               -- 全体指標（未完了数・完了率・期限超過数）
GET /api/v1/dashboard/workload              -- ワークロード（ユーザー別 予定工数 vs キャパシティ）
GET /api/v1/dashboard/today                 -- 今日やること（due_date = today）
GET /api/v1/dashboard/overdue               -- 期限超過タスク一覧
GET /api/v1/dashboard/completion-trend      -- 完了推移（週次/月次）
```

### テンプレート・ユーザー・エクスポート

```
GET    /api/v1/templates
POST   /api/v1/templates
PUT    /api/v1/templates/{id}
DELETE /api/v1/templates/{id}
POST   /api/v1/templates/{id}/apply         -- テンプレートから一括タスク生成

GET    /api/v1/users                        -- Entra ID からキャッシュ済みユーザー一覧
GET    /api/v1/users/{id}/tasks
GET    /api/v1/users/{id}/workload

GET    /api/v1/export/tasks?format=csv
GET    /api/v1/export/dashboard?format=pdf
```

---

## 7. フロントエンド画面構成

### ルーティング

```
/                       → ダッシュボード（今日のタスク・各種指標）
/tasks                  → タスク一覧（検索・絞り込み）
/tasks/:id              → タスク詳細
/projects               → プロジェクト一覧
/projects/:id           → プロジェクト詳細（タスク一覧・マイルストーン）
/projects/:id/gantt     → ガントビュー
/projects/:id/kanban    → カンバンビュー
/schedule               → 1日スケジュール（カレンダービュー）
/workload               → ワークロード画面
/templates              → テンプレート管理
/settings               → ユーザー設定（権限・キャパシティ）
```

### 主要コンポーネント

```
src/
├── pages/
│   ├── Dashboard/        -- ダッシュボード
│   ├── Tasks/            -- タスク一覧・詳細
│   ├── Projects/         -- プロジェクト管理
│   ├── GanttView/        -- ガントチャート
│   ├── KanbanView/       -- カンバンボード
│   ├── Schedule/         -- 1日スケジュール
│   ├── Workload/         -- ワークロード
│   └── Templates/        -- テンプレート
├── components/
│   ├── TaskCard/         -- タスクカード（共通）
│   ├── TaskForm/         -- タスク作成・編集フォーム
│   ├── CommentThread/    -- コメントスレッド
│   ├── WorkHoursForm/    -- 工数入力フォーム
│   └── charts/           -- Recharts ラッパー群
├── hooks/
│   ├── useTasks.ts       -- TanStack Query タスク操作
│   ├── useProjects.ts
│   └── useDashboard.ts
├── store/
│   └── useAuthStore.ts   -- Zustand 認証状態
└── lib/
    ├── api.ts            -- axios インスタンス・インターセプター
    └── msal.ts           -- MSAL 設定
```

---

## 8. 非機能要件

| ID | カテゴリ | 要件 |
|----|--------|------|
| NFR-01 | セキュリティ | 機密データ（Pattern B）を外部 LLM へ送信しない（既存要件を継承） |
| NFR-02 | 認証 | Entra ID（MSAL）でログインし、ロール（member/leader/manager/admin）に基づくアクセス制御 |
| NFR-03 | 操作性 | 初見で直感的に操作でき、D&D やビュー切り替えがシームレスであること |
| NFR-04 | 性能 | ダッシュボード・カンバン・一覧のレンダリングが 3 秒以内に完了すること |
| NFR-05 | 型安全 | フロント：TypeScript strict モード。バック：mypy --strict |
| NFR-06 | 監査ログ | LLM 呼び出し・信頼スコア・起票結果を Langfuse に記録（既存要件を継承） |
| NFR-07 | コード品質 | バック：ruff + mypy。フロント：ESLint + Prettier |
| NFR-08 | テスト | バック：pytest（既存）。フロント：Vitest + Testing Library |
| NFR-09 | DB マイグレーション | Alembic で管理し、ダウンタイムなしのスキーマ変更を基本とする |
| NFR-10 | レスポンシブ | PC ブラウザ（1280px 以上）を主対象。スマートフォン専用アプリは対象外 |

---

## 9. 環境変数追加分（`.env.example` への追記）

```env
# PostgreSQL（新規）
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/autoticket

# フロントエンド認証（MSAL）
AZURE_CLIENT_ID_FRONTEND=your-spa-client-id  # SPA 用の別アプリ登録
FRONTEND_URL=http://localhost:5173

# Microsoft Forms / SharePoint 連携
SHAREPOINT_SITE_ID=your-sharepoint-site-id
FORMS_LIST_ID=your-forms-response-list-id
```

---

## 10. 未解決事項・TODO

| # | 項目 | 優先度 | 備考 |
|---|------|-------|------|
| T-01 | F-17 右クリック起票の実装方式確定 | Should | Outlook アドイン vs Teams メッセージ拡張 |
| T-02 | F-26 マニュアル自動生成の対象ファイル形式 | Should | PDF / Word / SharePoint ページ |
| T-03 | F-37 ペアワークモードの実現可否 | Could | WebSocket コストとの兼ね合い |
| T-04 | PostgreSQL ホスティング先 | Must | Docker Compose 追加（ローカル）/ Azure Database for PostgreSQL |
| T-05 | フロントエンドのホスティング先 | Must | Docker Compose の nginx / Azure Static Web Apps |
| T-06 | Entra ID の SPA アプリ登録 | Must | IT 管理者対応（既存アプリとは別登録） |
| T-07 | Microsoft Forms → SharePoint 自動連携設定 | Must | Forms の回答先 SharePoint リストを IT 管理者が設定 |
