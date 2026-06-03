# AutoTicket 進捗ログ

## 現在のフェーズ
**Phase: Web App Phase 2B（Should 機能）✅ ほぼ完了（F-21 Teams 通知のみ残・Graph API 承認待ち）**
ステータス: タスク一括操作完了・F-21 は Graph API 承認待ちのためブロック中

## 最終更新
- **日付**: 2026-06-03
- **完了した作業**:
  - **[タスク一括操作]**（2026-06-03）
    - **バックエンド**:
      - `TaskBulkUpdate` / `BulkUpdateResponse` Pydantic v2 モデル追加（`src/models/task_web.py`）
      - `PATCH /api/v1/tasks/bulk` エンドポイント追加（`src/api/routers/tasks_crud.py`）
        - `task_ids` 1〜100件バリデーション（422）
        - `status`/`assignee_id` 両方 None → 422
        - 存在しない task_id → 404
        - 非オーナー + member ロール → 403
        - 1トランザクション一括更新・`_spawn_next_recurrence` 呼び出し（completed/cancelled 時）
        - `PATCH /bulk` を `GET /{task_id}` の前に配置（パスパラメータ競合回避）
      - テスト 4 件追加（`tests/unit/test_bulk_update.py`）→ 合計 240 passed
    - **フロントエンド**:
      - `api.ts`: `TaskBulkUpdate` インターフェース・`bulkUpdateTasks` 関数追加
      - `useTasks.ts`: `useBulkUpdateTasks` フック追加（`tasks` + `tasks-view` 両方 invalidate）
      - `pages/Tasks/index.tsx`: Ant Design `rowSelection` チェックボックス追加・画面下部固定の一括操作バー（ステータス Select・担当者 Select・適用ボタン・選択解除ボタン）追加
      - D&D 並び替えと rowSelection は独立して共存
    - コミット: `64ce3d2`・`4978c06`・`dc95510`・`633e20c`・`bea32c3`・`9e94796` → origin/master にプッシュ済み

  - **[マイページ `/mypage`]**（2026-06-03）
    - **バックエンド**:
      - `UserProfileUpdate` / `WeeklyWorkSummary` Pydantic モデル追加（`src/models/task_web.py`）
      - `GET /api/v1/users/me/profile` — DB から自分のプロフィールを取得（`AdminUserResponse` 返却）
      - `PATCH /api/v1/users/me` — 表示名・稼働時間・部門タグを部分更新
      - `GET /api/v1/dashboard/my-weekly-summary` — 過去4週分の工数・タスク・完了数・期限超過集計
      - テスト 8 件追加（`test_update_me.py` 4件・`test_my_weekly_summary.py` 4件）→ 合計 236 passed
    - **フロントエンド**:
      - `api.ts`: `UserProfileUpdate`・`WeeklyWorkSummary` 型定義・`updateMyProfile`・`getMyWeeklySummary` 関数追加
      - `useTasks.ts`: `TaskFilters` に `due_date_gte`/`due_date_lte` 追加
      - `useMyPage.ts`: 5 フック新規作成（useMyProfile / useUpdateMyProfile / useMyWeeklySummary / useMyWeeklyTasks / useMyOverdueTasks）
      - `pages/MyPage/ProfileCard.tsx`: プロフィール表示 + 編集 Modal（表示名・稼働時間・部門タグ）
      - `pages/MyPage/WeeklySummary.tsx`: KPI カード4枚 + recharts 工数 BarChart（過去4週）
      - `pages/MyPage/index.tsx`: 今週タスク一覧 + 期限超過タスク一覧
      - `App.tsx`: `/mypage` ルート・ナビ（`UserOutlined`）追加
    - コミット: `6a18f65`・`15e544f`・`2ea3f1b`・`f25f665`・`e877b99`・`be25217`・`033e2da` → origin/master にプッシュ済み

  - **[繰り返しタスク]**
    - **Alembic 0007**: `tasks` テーブルに `recurrence_rule`（daily/weekly/monthly）・`recurrence_end_date`・`recurrence_origin_id`（自己参照 FK）を追加
    - **SQLAlchemy モデル修正**: `Task` に 3 列追加・`subtasks`/`parent_task` リレーションに `foreign_keys` 明示（FK 曖昧性解消）
    - **Pydantic モデル拡張**: `TaskCreate` に `recurrence_rule`/`recurrence_end_date` 追加・`TaskResponse` に 3 フィールド追加
    - **`_spawn_next_recurrence` ヘルパー**: 完了/キャンセル時に次回インスタンスを生成（endDate 超過チェック・重複チェック・タグ引き継ぎ）
    - **`create_task` 修正**: 初回作成時に `recurrence_origin_id = task.id`（自己参照）をセット
    - **`update_task` 修正**: ステータスが completed/cancelled になったとき `_spawn_next_recurrence` を呼び出し
    - **`DELETE /{task_id}/recurrence` エンドポイント**: 繰り返しルールを単体タスクに解除
    - **`recurrence_backfill_job` APScheduler**: 毎日 02:00 JST に完了済み繰り返しタスクの後継未生成分を補完
    - **ユニットテスト 7 件**: `test_task_recurrence.py`（daily/weekly/monthly/endDate/重複防止/ルールなし/start_date オフセット保持）→ 合計 228 passed
    - **フロントエンド**:
      - `api.ts`: `Task` インターフェースに 3 フィールド追加・`deleteRecurrence()` 関数追加
      - `useTasks.ts`: `useDeleteRecurrence` フック追加
      - `Tasks/index.tsx`: タイトル横に `RedoOutlined` アイコン（繰り返し表示）・作成フォームに繰り返し Select + 終了日 DatePicker 追加
      - `TaskDetail.tsx`: 詳細タブに繰り返し情報行（ルール・終了日・「解除」Popconfirm ボタン）追加
    - コミット: `20e610c`・`d131f6c`・`aeac735`・`1442ca0`・`f9f07c4`

  - **[CSV エクスポート]**
    - `GET /api/v1/tasks/export/csv` エンドポイント追加（フィルタ結果を UTF-8 BOM CSV でストリーム）
    - タスク一覧ページに「CSV エクスポート」ボタン追加（loading 状態・blob ダウンロード処理）
    - コミット: `c886368`, `eb00411`

  - **[手動並び替え（Fractional Indexing）]**
    - `Task.order_index` を Integer → Float に変更（Alembic 0006 マイグレーション）
    - `TaskReorderRequest` Pydantic モデル追加
    - `PATCH /api/v1/tasks/{task_id}/order` エンドポイント追加（中点計算・gap < 0.001 で再採番）
    - `list_tasks` の ORDER BY を `order_index ASC` に変更・`create_task` で末尾追加
    - ユニットテスト 5 件追加（合計 221 passed）
    - `useReorderTask` フック追加（`frontend/src/hooks/useTasks.ts`）
    - タスク一覧（`Tasks/index.tsx`）: `DraggableRow` + `DndContext` + 楽観的更新
    - ボード（`Board/index.tsx`）: `SortableContext` + カラム内並び替え/カラム間ステータス変更の二重モード
    - コミット: `cba60b7`, `bae026e`, `8f76487`, `ce09c98`, `76dc423`

- **完了した作業（前セッション: 2026-05-28 セッション 2）**:
- **完了した作業**:
  - **[バグ修正: gemini_api_key リネーム]** `google_api_key` → `gemini_api_key` に統一
    - 原因: OS 環境変数 `GOOGLE_API_KEY`（Google Cloud SA キー）が pydantic-settings に優先されて Gemini 400 エラーが発生
    - 修正ファイル: `src/models/config.py`・`src/providers/factory.py`・`src/api/routers/tasks_crud.py`・`tests/unit/test_clarify_requirements.py`・`tests/unit/test_generate_subtasks.py`・`.env`
    - コミット: `d1102a3`

  - **[バグ修正: useAuthStore ログイン状態の永続化]**
    - `loadDevUser()` 関数を追加し、`sessionStorage` からログイン情報をリロード時に復元
    - 対象: `frontend/src/store/useAuthStore.ts`

  - **[バグ修正: ExtractModal Pattern B キャンセルボタン]**
    - キャンセル後も `isPending` が残る問題を `extractTasks.reset()` 呼び出しで修正

  - **[動作確認 8 項目実施]**（Playwright MCP ブラウザ検証）
    - 1-5 ✅: 起票ボタンで DB にタスクが登録される
    - 2-1 ✅: Pattern B 警告 Alert が表示される
    - 2-2 ✅: キャンセルボタンで `isPending` がリセットされる
    - 2-3 ❌→方針決定: 「それでも送信」ボタンが機能せず → 削除方針に決定
    - 4-1 ✅: ページリロード後もログイン状態が維持される
    - 4-2 ✅: ブラウザ「戻る」操作後もログイン状態が維持される
    - 5-1 ✅: F-32 サブタスク自動生成 が動作する（5 件提案を確認）
    - 5-2 ✅: F-29 AI チェック が動作する（担当者未設定・完了条件不明確を検知）

  - **[Pattern B 方針: 「それでも送信」ボタン削除]**
    - 背景: サーバーが Pattern B を常にブロックするため「それでも送信」は機能しない Dead Feature
    - 対応: Alert の action を「閉じる」1 ボタンのみに変更・説明文を「担当者に相談してください」に更新
    - 中長期方針: Azure OpenAI（M365 テナント内）移行後に Pattern B を解禁予定
    - コミット: `de0e1c2`

  - **[新規ドキュメント: docs/deployment-roadmap.md 作成]**
    - D-Ph0: 環境整備・IT 承認（1〜2 週間）
    - D-Ph1: パイロット展開 — Pattern A のみ・非機密部署（〜2 ヶ月）
    - D-Ph2: Azure OpenAI 移行 — Pattern B 解禁・人事財務へ拡大（〜6 ヶ月）
    - D-Ph3: 全社展開・Entra ID グループ連携（〜12 ヶ月）
    - D-Ph4: Ollama on-prem — 法務等の高機密部署（必要時）
    - LLM 選定フローチャート（M365 あり/なし/高機密の 3 分岐）収録
    - コミット: `6f8e760`

- **完了した作業（前セッション: 2026-05-28 セッション 1）**:
  - **[F-33 テキスト抽出 UI]**
    - `POST /tasks/extract` を JSON ボディ対応に修正・`ExtractResponse` Pydantic モデル追加
    - `ExtractedTask`・`ExtractResult` 型追加（`frontend/src/lib/api.ts`）
    - `useExtractTasks` フック追加（`frontend/src/hooks/useTasks.ts`）
    - `ExtractModal.tsx` 新規作成（スプリットパネル・編集サブモーダル・Pattern B 警告・昇格ボタン・AI ヒント）
    - タスク一覧ページに「テキストから作成」ボタン追加

  - **[F-12 工数自動算出]**
    - `HourEstimate` Pydantic モデル追加（`src/models/task_web.py`）
    - `GET /api/v1/tasks/estimate-hours` エンドポイント追加（タグ OR 一致・完了タスクの実績工数集計、N+1 なし）
    - ユニットテスト 5 件追加（`tests/unit/test_estimate_hours.py`）→ 合計 172 passed
    - `HourEstimate` 型・`getEstimateHours` 関数追加（`frontend/src/lib/api.ts`）
    - `useEstimateHours(tags)` フック（enabled: tags.length > 0・staleTime 2分）追加
    - `useRecordEstimatedHours()` フック（POST /tasks/{id}/work-hours）追加
    - タスク作成モーダルにタグ Select フィールド・推奨工数バッジ（青/グレー）・予定工数 InputNumber 追加
    - タスク作成後に estimated_hours が入力されていれば工数レコードを自動登録

  - **[F-30 遅延リスク AI 予測]** `_compute_risk_level()` 純粋関数・`TaskResponse.risk_level`・タスク一覧バッジ（高リスク/要注意）
  - **[F-31 タスクの自動棚卸し提案]** `StaleTaskItem` モデル・`GET /dashboard/stale-tasks`・Dashboard 棚卸しカード・`useArchiveTask(PUT)` フック
  - テスト 13 件追加（`test_delay_risk.py` 8件・`test_stale_tasks.py` 5件）→ 合計 183 passed（respx 除外時）

- **完了した作業（前セッション）**:
  - **[F-29 タスク要件の明確化プロンプト — Gemini AI チェック]**
    - `GeminiProvider.clarify_requirements()` 追加（Gemini API でルール＋AI 複合チェック）
    - `POST /tasks/{id}/clarify-requirements` エンドポイント（`ClarifyIssue` Pydantic モデル）
    - タスク詳細「詳細」タブに AI チェックボタン・要件不足 Alert 表示
    - テスト 7 件追加（`tests/unit/test_clarify_requirements.py`）→ 合計 170 passed

  - **[Admin 組織設定・アラート設定タブ]**
    - `GET/PATCH/DELETE /api/v1/admin/tags` — 部門タグ一覧・リネーム・削除 API 追加（`admin.py`）
    - `TagRenameRequest` Pydantic モデル追加（`task_web.py`）
    - Admin ページをタブ構成に刷新: ユーザー管理 / 組織設定 / アラート設定（`frontend/src/pages/Admin/`）
    - `useAdminTags` フック（一覧・リネーム・削除）・`useAdminUsers` フック追加
    - `useSettingsStore` Zustand ストア追加（アラート設定永続化）
    - Dashboard ロールスコープ修正（`_scope_condition()` で member/leader/manager/admin 別絞り込み）

  - **[DevLogin カード選択 UI 刷新]**
    - `GET /api/v1/dev/users` エンドポイント追加（`dev.py`・DEV_MODE=true のみ有効）
    - DevLogin をフォーム手入力 → DB からユーザー取得してカード選択方式に変更
    - ロール・部門タグをカラーバッジで視覚表示

  - **[Gantt 依存関係 UI 改善]**
    - 先行タスク(A)→後続タスク(B) の選択 UI を 2 ドロップダウン方式に統一
    - 依存関係削除（`Popconfirm` + `DeleteOutlined`）追加
    - `DepMapFull` 型で依存 ID を正確に管理

  - **[ruff 自動修正]** 38 件の import 整列・不要 import 除去・`datetime.UTC` 置換

- **完了した作業**:
  - **[F-32 サブタスク自動生成 — Gemini API 連携]**
    - `GeminiProvider.generate_subtasks()` 追加（`src/providers/gemini.py`）
    - `POST /tasks/{id}/generate-subtasks` エンドポイント（503 エラーハンドリング・logger.exception 付き）
    - `GenerateSubtasksResponse` Pydantic モデル追加
    - `useGenerateSubtasks()` フック追加（`frontend/src/hooks/useTaskDetails.ts`）
    - `SubtasksPanel.tsx` を AI 提案 UI に刷新（チェックボックス選択→一括追加）
    - テスト 6 件追加（`tests/unit/test_generate_subtasks.py`）→ 合計 128 passed

  - **[F-15 テンプレート機能 — 定型業務の雛形登録・一括作成]**
    - **Alembic 0005**: `task_templates.updated_at` カラム追加（`sa.text("now()")` 準拠）
    - **Pydantic モデル 7 種**: `TemplateSubtask` / `TemplateData` / `TemplateCreate` / `TemplateUpdate` / `TemplateResponse` / `TemplateApplyRequest` / `TemplateApplyResponse`（`src/models/task_web.py`）
    - **テンプレート CRUD ルーター**: `src/api/routers/templates.py`（GET/POST/PUT/DELETE・作成者 or admin 認可・`POST /{id}/apply` でメインタスク＋サブタスク一括作成）
    - **テスト 13 件**: `tests/unit/test_templates_router.py`（CRUD・403 認可・apply 3 件）→ 合計 141 passed
    - **フロントエンド**: `useTemplates.ts`（5 フック）・`/templates` 管理ページ（カード一覧・Drawer 作成/編集・Form.List サブタスク）・App.tsx ナビ追加
    - **タスク作成モーダル統合**: テンプレート選択 Select + DatePicker + 「このテンプレートで作成」ボタン・Divider で手動作成と区別
    - TypeScript チェック通過・全コミット origin/master にプッシュ済み

  - **[バグ修正セッション — SQLAlchemy MissingGreenlet 根本修正]**
    - **ガントチャート reschedule エラー修正**（`src/api/routers/tasks_crud.py` `reschedule_task`）
      - 原因: `_cascade_reschedule()` が `await db.execute(SELECT)` → autoflush → UPDATE → `updated_at` expire → `db.refresh(task, ["tags","sub_assignees","subtasks"])` が列属性を再ロードせず → `_task_to_response()` で `MissingGreenlet` → HTTP 500
      - 修正: `commit()` 後に部分 `db.refresh()` を廃止し、フル `SELECT` + `selectinload` で再クエリ
    - **`update_task` 同種バグ修正**（`tasks_crud.py` L275）
      - タグ更新時 `db.flush()` → UPDATE → `updated_at` expire → 部分 `db.refresh()` → `MissingGreenlet` → HTTP 500
      - 修正: `commit()` 後に同パターンで再クエリ
    - **ガントチャート React StrictMode 二重発火修正**（`frontend/src/pages/Gantt/index.tsx`）
      - `isReschedulingRef` + `useCallback` で同時実行を防御
      - `toLocalDate()` をコンポーネント外の純粋関数に移動（タイムゾーン問題修正）
    - **全 router の `db.refresh()` 安全性確認**: `tasks_crud.py` `update_task` のみが問題、他は全安全
    - **セキュリティレビュー実施**: `DEV_MODE` バイパス機能の脆弱性候補を分析→信頼度閾値(8)未満のため有意な脆弱性なし
    - **テスト**: `tests/unit/test_auth.py` 7 件 ✅ passed

  - **[Web App Phase 2B-3 — F-14 全タスク完了]** 負荷アラート（ワークロードバッジ）実装
    - `DailyWorkloadItem` Pydantic モデル追加（`src/models/task_web.py`）
    - `GET /dashboard/daily-workload` エンドポイント（due_date 日別集計・ロール別スコープ・1.0h デフォルト）
    - `tests/unit/test_daily_workload.py`（7 件追加 → 合計 122 passed）
    - `frontend/src/hooks/useDailyWorkload.ts`（5 分キャッシュ）
    - `frontend/src/components/WorkloadAlertBadge.tsx`（Badge + Popover + recharts BarChart + Cell 着色 + ReferenceLine）
    - `frontend/src/App.tsx` ヘッダー右端に WorkloadAlertBadge 統合
    - TypeScript チェック通過・フロントエンドビルド（Windows 環境の pre-existing クラッシュは無関係）

  - **[Web App Phase 2B-2 — 全 14 タスク完了]** ユーザー管理・権限制御・UX 強化
    - Alembic 0003（start_date 補完）・0004（department_tags JSONB）
    - ハイブリッド認証: JWT-first / DB-fallback・ROLE_HIERARCHY 公開
    - Admin API: GET/POST/PATCH/DELETE /api/v1/admin/users（admin 権限ガード）
    - ロールベース閲覧制御: member=own+public, leader=dept+public, manager/admin=全件
    - /tasks/similar の認可フィルタ（private タスク漏洩防止）・my_tasks_only + ロールフィルタ競合修正
    - F-07: my_tasks_only フィルタ・タスク作成時 visibility 選択（private/team/all）
    - F-04: /tasks/similar エンドポイント（トークン分割 ILIKE・スコア 0.5 以上・最大 5 件）
    - F-11: Schedule ページ週次 D&D グリッド（前後 3 日 + 今日 + 3 日・start_date 更新）
    - Admin Users ページ（/admin/users・admin ロール限定表示）・部門タグ Select mode=tags
    - テスト: 115 passed（新規 13 件: test_admin_router・test_visibility・test_similar_tasks）
    - バグ修正: visibility "public" → "all"・similar 認可バイパス・my_tasks_only ロール競合
    - git push: `6638870` → origin/master にプッシュ済み

  - **[Web App Phase 2B-1 — 全 6 タスク完了]** マルチビュー + F-36 自動リスケジュール実装
    - バックエンド: `due_date_gte`/`lte`/`assignee_ids` フィルタ追加、`POST /tasks/{id}/reschedule` エンドポイント新設（BFS 依存グラフ走査）
    - フロントエンド: `@dnd-kit`, `react-big-calendar`, `gantt-task-react` ライブラリ導入
    - カンバンビュー (`/board`): ステータス 4 列・dnd-kit D&D・CSS.Transform.toString()・drag/click 競合防止
    - カレンダービュー (`/calendar`): 月次・担当者 Multi-Select フィルタ・タスク密度ヒートマップ・`allDay` 期間バー対応
    - ガントチャート (`/gantt`): gantt-task-react・バー D&D で reschedule・依存関係矢印・`enabled` ガード・onError フィードバック
    - フック: `useTasksForView`・`useReschedule`・`useUsers` 新規作成
    - テスト: 118 passed（新規 4 件: test_reschedule.py）
    - バグ修正: BFS キュー条件・start_date 上書き・`allDay` フラグ・due_date なしタスクのクラッシュ防止
    - git push: `71eb868` (最終コミット) → origin/master にプッシュ済み

  - **[Web App Phase 2A — 全 12 タスク完了]** タスク詳細 UI 完成・Asana インポート機能実装
    - Alembic 0002: sections・task_assignees テーブル追加・Task 列追加（section_id, external_id, completed_at, order_index）
    - Section CRUD API（`/api/v1/projects/{id}/sections`）・Task Assignees API・タスク複製 API
    - キーワード検索（ILIKE）・section_id フィルタを `GET /tasks` に追加
    - ユーザー一覧 API のリーダーロール制限撤廃
    - Asana xlsx インポート: openpyxl 解析・preview/confirm 2 段階 API
    - App.tsx を Ant Design Sider レイアウトに刷新・/projects と /import ルート追加
    - プロジェクト一覧ページ（List.tsx）・プロジェクト詳細ページ（Section 別タスク管理）
    - タスク詳細を 4 タブ拡張（詳細・コメント・工数・サブタスク）・複製ボタン
    - タスク一覧検索 UI（キーワード・ステータス・プロジェクト・セクションフィルタ）
    - Asana インポートウィザード（3 ステップ: Upload → Preview → Complete）
    - バグ修正: `await db.delete()` の await 漏れを sections/task_details の 3 箇所で修正
  - **テスト**: バックエンド 114 passed（.venv Python 3.11）
  - **git コミット**: `31fc4e0`

## 実装計画ファイル（Phase 2B-1）
- `docs/superpowers/plans/2026-05-19-phase2b1-multiview-implementation.md`（Phase 2B-1 実装計画・全完了）
- `docs/specs/2026-05-19-phase2b1-multiview-design.md`（Phase 2B-1 設計書）

  - **[Web App Phase 1 — 全 18 タスク完了]** React + FastAPI + PostgreSQL タスク管理 Web アプリ実装（2026-05-19）
    - PostgreSQL 16 + SQLAlchemy 2.x（Mapped 型）+ Alembic 非同期マイグレーション
    - タスク一覧・詳細・ダッシュボード・スケジュール・ワークロードページ
    - MSAL Entra ID 認証・Zustand 状態管理・TanStack Query 5.x
    - **テスト**: バックエンド 79 passed / フロントエンドビルド成功

## テスト状況
| テストファイル | 件数 | 状態 |
|-------------|------|------|
| test_models.py | 9 | ✅ |
| test_state.py | 4 | ✅ |
| test_classifier.py | 6 | ✅ |
| test_approval.py | 5 | ✅ |
| test_routing.py | 3 | ✅ |
| test_providers.py | 11 | ✅ |
| test_agent.py | 2 | ✅ |
| test_langfuse_client.py | 3 | ✅ |
| test_polling_job.py | 6 | ✅ |
| test_task_web_models.py | 12 | ✅ |
| test_tasks_crud_router.py | 8 | ✅ |
| test_connectors.py | 10 | ✅ |
| test_teams_chat.py | 3 | ✅ |
| test_onenote.py | 3 | ✅ |
| test_reschedule.py | 4 | ✅ |
| test_daily_workload.py | 7 | ✅ |
| test_generate_subtasks.py | 6 | ✅ |
| test_templates_router.py | 13 | ✅ |
| test_clarify_requirements.py | 7 | ✅ |
| test_admin_router.py | 5 | ✅ |
| test_auth.py | 7 | ✅ |
| test_import.py | 5 | ✅ |
| test_past_performance.py | 6 | ✅ |
| test_projects_router.py | 4 | ✅ |
| test_sections_router.py | 4 | ✅ |
| test_similar_tasks.py | 4 | ✅ |
| test_visibility.py | 4 | ✅ |
| test_security_fixes.py | 5 | ✅ |
| test_estimate_hours.py | 5 | ✅ |
| test_delay_risk.py | 8 | ✅ |
| test_stale_tasks.py | 5 | ✅ |
| test_reorder.py | 5 | ✅ |
| test_task_recurrence.py | 7 | ✅ |
| test_update_me.py | 4 | ✅ |
| test_my_weekly_summary.py | 4 | ✅ |
| test_bulk_update.py | 4 | ✅ |
| **合計** | **240** | ✅ 全 passed |

## 前提条件ステータス
| 項目 | ステータス | 備考 |
|------|----------|------|
| Graph API アプリ登録 | ⏳ 申請中 | IT管理者と調整中 |
| Exchange Application Access Policy | ⏳ IT管理者対応待ち | Step 1: 担当者1名で検証 |
| Docker Desktop | ✅ 確認済み v28.5.1 | Langfuse コンテナ起動済み |
| Langfuse | ✅ 設定済み | http://localhost:3000 |
| PostgreSQL（Docker） | 🔧 設定済み（接続要確認） | docker-compose up で起動 |
| Python .venv | ✅ 動作確認 | pytest 114 passed |
| Node.js / npm | ✅ 動作確認 | TypeScript チェック通過 |

## ブロッカー
- **Graph API 申請**: IT管理者との調整中。承認後に Phase 1B 統合テストを実施可能
- **respx 未インストール**: `.venv` に `pip install respx` で解決可能（優先度低）

## 次セッションの開始手順
1. `docs/progress.md`（このファイル）を確認
2. Graph API 承認状況を確認
   - **承認済み** → `docs/tasks.md` の Phase 1B タスクから開始
   - **未承認** → 残機能の実装または品質向上（下記候補）
3. 残タスク候補:
   - **F-21 Teams 通知**: コメント投稿時に担当者へ Teams メッセージ送信（Graph API 承認後）
   - **デプロイ準備**: `docs/deployment-roadmap.md` の D-Ph0（本番環境構築・IT 部門承認資料作成）
   - **E2E テスト拡充**: Playwright テストスイートを CI に組み込む
   - **追加 UI 機能**: 必要に応じて `docs/requirements.md` の未着手機能から選択

## 実装計画ファイル
- `docs/superpowers/specs/2026-06-03-bulk-task-update-design.md`（タスク一括操作 設計書）
- `docs/superpowers/plans/2026-06-03-bulk-task-update.md`（タスク一括操作 実装計画・全完了）
- `docs/superpowers/plans/2026-05-27-f15-template.md`（F-15 テンプレート機能 実装計画・全完了）
- `docs/superpowers/specs/2026-05-27-f15-template-design.md`（F-15 テンプレート機能 設計書）
- `docs/superpowers/plans/2026-05-27-f32-generate-subtasks.md`（F-32 サブタスク自動生成 実装計画・全完了）
- `docs/superpowers/plans/2026-05-19-phase2a-task-detail-implementation.md`（Phase 2A 実装計画・全完了）
- `docs/specs/2026-05-19-phase2a-task-detail-design.md`（Phase 2A 設計書）
- `docs/superpowers/plans/2026-05-18-phase1-webapp-implementation.md`（Web App Phase 1 実装計画・全完了）
- `docs/specs/system-design.md`（詳細設計ドキュメント）
- `docs/requirements.md`（機能要件・全 37 機能）
