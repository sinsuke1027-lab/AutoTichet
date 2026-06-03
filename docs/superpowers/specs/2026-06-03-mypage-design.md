# マイページ 設計書

> **For agentic workers:** この設計書を実装する際は `superpowers:writing-plans` スキルで実装計画を作成してから着手すること。

**Goal:** ログインユーザー自身の今週タスク・工数・プロフィールを一画面で確認・編集できる個人専用ページを追加する。

**Architecture:** 既存のダッシュボード（チーム全体俯瞰）は変更せず、`/mypage` を独立したルートとして追加する。バックエンドは新規エンドポイント2本のみ追加し、その他は既存APIを流用する。

**Tech Stack:** React 18 + TypeScript + Ant Design 5.x + recharts / TanStack Query 5.x / FastAPI + SQLAlchemy 2.x

---

## 1. 方針

| 項目 | 決定 |
|------|------|
| ダッシュボードとの関係 | **変更なし**。ダッシュボードはチーム全体の俯瞰ビューとして現状維持 |
| マイページの責務 | 自分の仕事を管理する場所（朝の確認 + 週次振り返り） |
| アクセス方法 | サイドバーナビに「マイページ」を追加（ダッシュボードの直下） |
| プロフィール編集 | マイページ内の Modal で行う（管理者の `/admin/users/{id}` とは別） |

---

## 2. ページレイアウト

```
┌─────────────────────┬──────────────────────┐
│  プロフィールカード   │   今週サマリーKPI     │
│  (表示名・ロール・   │  (タスク数・完了率・  │
│   部門タグ・編集)    │   予定工数・遅延数)   │
├─────────────────────┴──────────────────────┤
│        工数グラフ（過去4週 予定 vs 実績）    │
├─────────────────────┬──────────────────────┤
│  今週のタスク一覧    │   期限超過タスク      │
│  (due_date が今週)   │   (自分のもの限定)   │
└─────────────────────┴──────────────────────┘
```

---

## 3. バックエンド

### 3-1. 新規エンドポイント

#### `PATCH /api/v1/users/me`

自分自身のプロフィールのみ更新可能。管理者用 `PATCH /admin/users/{id}` とは独立。

**Request モデル（`UserProfileUpdate`、`src/models/task_web.py` に追加）:**

```python
class UserProfileUpdate(BaseModel):
    display_name: str | None = None
    capacity_hours_per_day: float | None = None
    department_tags: list[str] | None = None
```

**Response:** 既存 `UserProfile` モデルをそのまま返す。

**実装:** `src/api/routers/users.py` に追加。`current_user.user_id` で自分のレコードを特定し更新する。

---

#### `GET /api/v1/dashboard/my-weekly-summary`

過去4週分の週次工数集計を返す。グラフ描画用。

**Response モデル（`WeeklyWorkSummary`、`src/models/task_web.py` に追加）:**

```python
class WeeklyWorkSummary(BaseModel):
    week_start: date          # 週の月曜日
    planned_hours: float      # work_hours.planned_hours の合計
    actual_hours: float       # work_hours.actual_hours の合計
    task_count: int           # その週に due_date があるタスク数
    completed_count: int      # そのうち completed のタスク数
    overdue_count: int        # 現在時点での期限超過タスク数（最新週のみ、他週は 0）

# GET /api/v1/dashboard/my-weekly-summary → List[WeeklyWorkSummary]（4件、古い順）
```

**集計ロジック:**
- `work_hours` テーブルを `date` の週（月曜起算）でグループ化し、`task.assignee_id == current_user.user_id` に絞る
- タスク数・完了数は `tasks.due_date` の週で集計
- `overdue_count` は `due_date < today AND status NOT IN ('completed','cancelled')` のタスク数（最新週のみセット）

**実装:** `src/api/routers/dashboard.py` に追加。

---

### 3-2. テスト

`tests/unit/test_my_weekly_summary.py` に4件追加:

| テスト | 内容 |
|--------|------|
| `test_returns_4_weeks` | 過去4週分のデータが返る |
| `test_empty_work_hours` | work_hours が0件のとき planned/actual が 0.0 |
| `test_unauthenticated_401` | 認証なしで 401 |
| `test_no_other_user_data` | 別ユーザーのデータが混入しない |

---

## 4. フロントエンド

### 4-1. ファイル構成

```
frontend/src/
  pages/MyPage/
    index.tsx          ← メインページ（レイアウト組み立て）
    ProfileCard.tsx    ← プロフィール表示・編集 Modal
    WeeklySummary.tsx  ← KPI カード4枚 + 工数 BarChart
  hooks/
    useMyPage.ts       ← データ取得フック群（新規）
  lib/
    api.ts             ← UserProfileUpdate / WeeklyWorkSummary インターフェース追加
```

---

### 4-2. `api.ts` 追加型定義

```typescript
export interface UserProfileUpdate {
  display_name?: string | null
  capacity_hours_per_day?: number | null
  department_tags?: string[] | null
}

export interface WeeklyWorkSummary {
  week_start: string        // "2026-05-25" 形式
  planned_hours: number
  actual_hours: number
  task_count: number
  completed_count: number
  overdue_count: number
}
```

---

### 4-3. `useMyPage.ts`

```typescript
// 自分のプロフィール取得（GET /users/me）
export function useMyProfile(): UseQueryResult<UserProfile>

// プロフィール更新（PATCH /users/me）
export function useUpdateMyProfile(): UseMutationResult<UserProfile, unknown, UserProfileUpdate>

// 週次サマリー取得（GET /dashboard/my-weekly-summary）
export function useMyWeeklySummary(): UseQueryResult<WeeklyWorkSummary[]>

// 今週タスク（既存 useTasks を呼ぶラッパー）
export function useMyWeeklyTasks(): UseQueryResult<TaskListResponse>
// → useTasks({ my_tasks_only: true, due_date_gte: weekStart, due_date_lte: weekEnd, limit: 20 })

// 自分の期限超過タスク（既存 useTasks を呼ぶラッパー）
export function useMyOverdueTasks(): UseQueryResult<TaskListResponse>
// → useTasks({ my_tasks_only: true, due_date_lte: format(subDays(new Date(), 1), 'yyyy-MM-dd'), limit: 10 })
//   フロント側で status が 'completed'/'cancelled' のものを除外して表示
// ⚠️ 実装注意: useTasks.ts の TaskFilters に due_date_gte / due_date_lte を追加する必要あり
//   （バックエンドには既存パラメータとして存在する）
```

---

### 4-4. `ProfileCard.tsx`

- **表示:** 表示名・メール・ロールバッジ・部門タグ（`<Tag>`）・1日稼働時間 (`capacity_hours_per_day` h)
- **「プロフィールを編集」ボタン** → `<Modal>` を開く
- **Modal フォーム項目:**
  - 表示名: `<Input>`
  - 1日稼働時間: `<InputNumber min={1} max={24} step={0.5}>`
  - 部門タグ: `<Select mode="tags">`
- **保存:** `useUpdateMyProfile().mutateAsync()` → 成功後 Modal を閉じ `message.success`

---

### 4-5. `WeeklySummary.tsx`

**上段 KPI カード（4枚）:**

| カード | 値 |
|--------|-----|
| 今週タスク数 | `summaries[3].task_count` |
| 今週完了率 | `completed_count / task_count * 100`（%） |
| 今週予定工数 | `summaries[3].planned_hours` h |
| 期限超過 | `summaries[3].overdue_count`（赤色） |

**下段 BarChart（recharts）:**

```typescript
const chartData = summaries.map(s => ({
  week: `${format(parseISO(s.week_start), 'M/d')}週`,
  planned: s.planned_hours,
  actual: s.actual_hours,
}))
// Bar: planned（青）/ actual（緑）
// 既存 WorkloadAlertBadge と同パターン
```

---

### 4-6. `index.tsx`

```tsx
<Space direction="vertical" style={{ width: '100%' }} size="large">
  <Typography.Title level={4}>マイページ</Typography.Title>
  <Row gutter={16}>
    <Col span={10}><ProfileCard /></Col>
    <Col span={14}><WeeklySummary /></Col>
  </Row>
  <Row gutter={16}>
    <Col span={12}>
      {/* 今週のタスク一覧 */}
      <Card title="今週のタスク">
        <List dataSource={weeklyTasks} ... />
      </Card>
    </Col>
    <Col span={12}>
      {/* 期限超過タスク */}
      <Card title="期限超過タスク">
        <List dataSource={overdueTasks} ... />
      </Card>
    </Col>
  </Row>
</Space>
```

---

### 4-7. `App.tsx` 変更点

```typescript
// NAV_ITEMS にダッシュボードの直下へ追加
{ key: '/mypage', icon: <UserOutlined />, label: 'マイページ' }

// Routes に追加
<Route path="/mypage" element={<MyPage />} />
```

---

## 5. 変更しないもの

| 対象 | 理由 |
|------|------|
| `Dashboard/index.tsx` | チーム全体ビューとして現状維持 |
| `GET /dashboard/summary` | 変更なし |
| `GET /dashboard/today-tasks` | 変更なし |
| `GET /dashboard/stale-tasks` | 変更なし |
| `PATCH /admin/users/{id}` | 管理者専用として存続 |
