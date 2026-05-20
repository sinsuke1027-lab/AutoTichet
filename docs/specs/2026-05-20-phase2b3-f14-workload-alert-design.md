# F-14 負荷アラート 設計書

**作成日**: 2026-05-20  
**フェーズ**: Web App Phase 2B-3  
**対象機能**: F-14 — ワークロード超過・期限超過のブラウザ通知 or バッジ

---

## 概要

ヘッダーにベルアイコン＋バッジを配置し、今後7日間の日別ワークロード超過を視覚的に通知する。
クリックで Popover を展開し、日別棒グラフと超過日リストを表示する。

## アーキテクチャ

```
App.tsx (Layout.Header 右端)
  └── WorkloadAlertBadge コンポーネント
        ├── useDailyWorkload() → GET /dashboard/daily-workload
        ├── Badge（超過日数を数値表示、0 の場合は非表示）
        └── Popover（クリック展開）
              ├── 7日間棒グラフ
              │     ├── 超過日: 赤バー (#ff4d4f)
              │     ├── 正常日: 青バー (#1677ff)
              │     └── capacity 水平破線（ReferenceLine）
              ├── 超過日リスト（例: 「5/22 超過: 6.5h / 8h」）
              └── 「詳細を見る →」 (/workload へのリンク)
```

---

## バックエンド

### 新規エンドポイント

```
GET /api/v1/dashboard/daily-workload
```

**認証**: 全ロール（ロール別に集計対象を切り替え）

### レスポンスモデル

```python
class DailyWorkloadItem(BaseModel):
    date: str           # "YYYY-MM-DD"（今日〜今日+6日の7件固定）
    total_hours: float  # due_date がその日のタスクの estimated_hours 合計
    capacity_hours: float  # ロール別の capacity（下記参照）
    overload: bool      # total_hours > capacity_hours
    task_count: int     # 対象タスク件数
```

### 集計ロジック

| ロール | 集計対象タスク | capacity_hours の算出 |
|--------|--------------|----------------------|
| member | 自分の `assignee_id` のタスクのみ | 自分の `capacity_hours_per_day` |
| leader | 部署タグ一致ユーザーのタスク | 対象ユーザーの `capacity_hours_per_day` 平均 |
| manager / admin | 全ユーザーのタスク | 全ユーザーの `capacity_hours_per_day` 平均 |

**除外条件:**
- `status IN ('completed', 'cancelled')`
- `due_date IS NULL`

**デフォルト値:**
- `TaskWorkHour.estimated_hours` が存在しないタスクは **1.0h** をデフォルトとして使用

**既存エンドポイントとの整合性:**
- `/dashboard/workload` はユーザー別・7日間合計集計（`TaskWorkHour` ベース）
- `/dashboard/daily-workload` は日別・`due_date` ベース（カレンダービューと一致）
- 2つは異なる軸（ユーザー軸 vs 日付軸）であり、補完関係

### 実装ファイル

- **修正**: `src/api/routers/dashboard.py` — 新エンドポイント追加
- **修正**: `src/models/task_web.py` — `DailyWorkloadItem` モデル追加
- **修正**: `src/api/main.py` — 変更不要（dashboard ルーターは既存）

---

## フロントエンド

### 新規ファイル

#### `frontend/src/hooks/useDailyWorkload.ts`

```typescript
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

export interface DailyWorkloadItem {
  date: string
  total_hours: number
  capacity_hours: number
  overload: boolean
  task_count: number
}

export function useDailyWorkload() {
  return useQuery<DailyWorkloadItem[]>({
    queryKey: ['daily-workload'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/daily-workload')
      return data
    },
    staleTime: 5 * 60 * 1000,  // 5分キャッシュ
  })
}
```

#### `frontend/src/components/WorkloadAlertBadge.tsx`

- **Badge**: `count={overloadDays.length}` — 超過日数を表示。0 の場合は `showZero={false}` で非表示。
- **Popover**: `trigger="click"` で展開。`placement="bottomRight"`。
- **グラフ**: recharts `BarChart`（Workload ページと同一ライブラリ）
  - X 軸: 日付（M/D 形式）
  - Y 軸: 時間（h）
  - `Bar`: `fill` を `overload` に応じて赤/青に変える（`Cell` コンポーネント）
  - `ReferenceLine`: capacity 値の水平破線
- **超過日リスト**: overload=true の日を `Tag color="red"` で列挙
- **リンク**: `<Link to="/workload">詳細を見る</Link>`

### 変更ファイル

#### `frontend/src/App.tsx`

`Layout.Header` に `WorkloadAlertBadge` を右端配置:

```tsx
<Layout.Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', padding: '0 24px' }}>
  <WorkloadAlertBadge />
</Layout.Header>
```

既存の App.tsx に Header が存在しない場合は追加する。

#### `frontend/src/lib/api.ts`

`DailyWorkloadItem` 型を追加（または hook ファイル側で定義）。

---

## テスト

### バックエンド（`tests/unit/test_daily_workload.py`）

| テスト | 内容 |
|--------|------|
| `test_daily_workload_member` | member ユーザー: 自分の due_date タスクのみ集計 |
| `test_daily_workload_manager` | manager ユーザー: 全タスク集計 |
| `test_overload_flag` | total_hours > capacity_hours で overload=True |
| `test_no_due_date_excluded` | due_date=null タスクは除外 |
| `test_completed_excluded` | completed タスクは除外 |
| `test_default_hours` | estimated_hours なしタスクは 1.0h |
| `test_7_days_returned` | レスポンスは必ず 7 件 |

### フロントエンド

TypeScript 型チェック通過 + ビルド成功を確認。

---

## 非機能要件

- API レスポンスタイム: < 500ms（インデックス: `Task.due_date`, `Task.assignee_id`）
- ポーリング不要: ユーザーが手動リフレッシュ or 5分 staleTime
- ブラウザ通知（Web Notifications API）は今回スコープ外（Popover バッジで代替）

---

## スコープ外（今回実装しない）

- ブラウザ通知（`Notification.requestPermission()`）: 別途 F-14B として検討
- WebSocket リアルタイム更新
- モバイル対応の別 UI
