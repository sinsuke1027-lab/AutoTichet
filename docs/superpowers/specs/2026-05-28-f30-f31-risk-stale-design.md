# F-30 遅延リスク予測 / F-31 自動棚卸し提案 設計書

作成日: 2026-05-28

---

## 概要

| 機能 | 内容 |
|-----|------|
| F-30 | タスク一覧の各行にルールベースの遅延リスクバッジを表示 |
| F-31 | 14日以上放置のタスクを Dashboard カードで一覧し、キャンセルボタンを提供 |

両機能とも Gemini API 不要。既存 DB データのみで動作する。

---

## F-30: 遅延リスク AI 予測（ルールベース）

### スコアリングロジック

`_task_to_response()` 内で完結する純粋計算。DB 追加クエリなし。
`task.work_hours` は既に selectinload 済みの関係を利用する。

| 条件 | 加点 | 備考 |
|------|------|------|
| 期限超過（due_date < 今日、status が completed/cancelled 以外） | +40 | 最重要シグナル |
| 残り3日以内（未超過） | +20 | 直近の締切 |
| 残り4〜7日以内 | +10 | 近い締切 |
| status=not_started かつ due_date が14日以内 | +20 | 着手遅延 |
| 実績工数合計 > 予定工数合計 × 1.2 | +15 | 工数超過傾向 |
| status=in_progress かつ work_hours 記録なし | +10 | 進捗不明 |

**リスクレベル判定:**

| スコア | risk_level | フロントエンド表示 |
|--------|-----------|-----------------|
| ≥ 60 | `"high"` | `<Tag color="red">高リスク</Tag>` |
| 30〜59 | `"medium"` | `<Tag color="orange">要注意</Tag>` |
| < 30 | `null` | 表示なし |

due_date が null のタスク、または status が completed/cancelled のタスクは `null` を返す。

### バックエンド変更

**`src/models/task_web.py`**

```python
class TaskResponse(BaseModel):
    # ... 既存フィールド ...
    risk_level: str | None = None  # "high" | "medium" | null
```

**`src/api/routers/tasks_crud.py`**

`_compute_risk_level(task: Task) -> str | None` ヘルパー関数を追加し、
`_task_to_response()` 内で呼び出して `risk_level` をセットする。

```python
def _compute_risk_level(task: Task) -> str | None:
    # due_date なし・完了・キャンセルはスキップ
    # スコアを積み上げてリスクレベルを返す
```

### フロントエンド変更

**`frontend/src/lib/api.ts`**
`Task` 型に `risk_level: 'high' | 'medium' | null` を追加。

**`frontend/src/pages/Tasks/index.tsx`**
タスク一覧の title 列に `RiskBadge` インライン表示を追加。

```tsx
{task.risk_level === 'high' && <Tag color="red">高リスク</Tag>}
{task.risk_level === 'medium' && <Tag color="orange">要注意</Tag>}
```

### テスト

`tests/unit/test_delay_risk.py` に 6〜8 件:
- 期限超過タスク → high
- 残り2日タスク → medium 以上
- 完了タスク → null
- due_date なし → null
- 着手遅延（not_started + 10日後期限） → medium
- 工数超過タスク → スコア加算確認

---

## F-31: タスクの自動棚卸し提案

### 判定条件

- `status NOT IN ('completed', 'cancelled')`
- `updated_at < now() - 14日`
- ロールスコープ適用（`_scope_condition()` 流用）
- 最大10件、`updated_at` 昇順（最も放置期間が長いものから）

### バックエンド

**エンドポイント**

```
GET /api/v1/dashboard/stale-tasks
```

**Pydantic モデル（`src/models/task_web.py`）**

```python
class StaleTaskItem(BaseModel):
    id: uuid.UUID
    title: str
    assignee_id: str | None
    due_date: date | None
    updated_at: datetime
    days_stale: int
```

**実装ファイル:** `src/api/routers/dashboard.py`

`_scope_condition()` を再利用してロール別スコープを適用する。

### フロントエンド

**`frontend/src/hooks/useDashboard.ts`**

`useStaleTaskItems()` フックを追加（5分キャッシュ）。

**`frontend/src/pages/Dashboard/index.tsx`**

既存の KPI カード群の下（ワークロード行の下）に「📋 棚卸し提案」カードを追加。

```
┌─────────────────────────────────────────────┐
│ 📋 棚卸し提案（14日以上更新なし）             │
├──────────────────────────────────┬──────────┤
│ タスク名                          │ 放置日数  │ [キャンセルにする] │
│ ...                              │ ...      │ ...               │
└──────────────────────────────────┴──────────┘
```

- 「キャンセルにする」ボタン押下 → `PATCH /tasks/{id}` `{status: "cancelled"}`
- 成功後 `invalidateQueries(['stale-tasks'])` でカード即時リフレッシュ
- 放置タスクが 0件の場合はカード自体を非表示（`if (!items.length) return null`）

### テスト

`tests/unit/test_stale_tasks.py` に 5〜6 件:
- 15日未更新タスク → 返却される
- 13日未更新タスク → 返却されない
- 完了タスク15日未更新 → 返却されない
- キャンセルタスク15日未更新 → 返却されない
- days_stale の値が正確か確認

---

## 実装順序

1. F-30 バックエンド（`_compute_risk_level` + `TaskResponse.risk_level`）
2. F-30 テスト
3. F-30 フロントエンド（api.ts 型 + Tasks/index.tsx バッジ）
4. F-31 バックエンド（`StaleTaskItem` + `/dashboard/stale-tasks`）
5. F-31 テスト
6. F-31 フロントエンド（フック + Dashboard カード）
7. 全テスト確認・コミット

---

## 非機能要件

- F-30: `_compute_risk_level` は純粋関数（副作用なし・DB クエリなし）
- F-31: DB クエリは1本のみ（N+1 なし）
- 両機能とも Gemini API キー不要
- TypeScript strict モード準拠・Pydantic v2 型ヒント必須
