# F-27 過去実績参照機能 設計書

**最終更新:** 2026-05-28  
**ステータス:** 承認済み  
**対応要件:** F-27「同種作業の過去実績時間を参考情報として表示」（Should / Phase 2）

---

## 1. 概要

タスク詳細ページの工数タブに「過去の類似タスク実績」セクションを追加する。
現在のタスクと同じタグを持つ完了済みタスクの実績工数（平均・最小・最大・件数）と
類似タスク最新3件のリストを表示し、工数見積もりの参考情報として提供する。

**ユースケース例:**
- 「月次報告」タグが付いたタスクを開くと、過去の月次報告タスクの平均実績 2.5h が表示される
- 見積もり工数を入力する際の参考にできる

---

## 2. バックエンド

### 2-1. 新規エンドポイント

```
GET /api/v1/tasks/{task_id}/past-performance
```

| 項目 | 内容 |
|------|------|
| 認証 | 全認証済みユーザー |
| ルーター | `src/api/routers/task_details.py` に追加 |
| タスク不存在時 | 404 |
| タグなし / 実績なし | 200 + 空レスポンス（`task_count: 0`） |

### 2-2. クエリロジック

1. 対象タスクのタグ一覧を `task_tags` から取得
2. タグが0件の場合は即座に空レスポンスを返す
3. 以下の条件でタスクを絞り込む:
   - `tasks.id != task_id`（自分自身を除外）
   - `tasks.status = 'completed'`
   - `task_tags.tag IN (<対象タスクのタグ一覧>)`（1件でも一致）
   - `task_work_hours.actual_hours IS NOT NULL`
4. 集計: `AVG`, `MIN`, `MAX`, `COUNT(DISTINCT task_id)` を `actual_hours` に対して計算
5. 類似タスク上位3件: `recorded_at DESC` でソートしたタスク ID・タイトル・`actual_hours`

### 2-3. Pydantic モデル（`src/models/task_web.py` に追加）

```python
class PastPerformanceSimilarTask(BaseModel):
    id: uuid.UUID
    title: str
    actual_hours: float

class PastPerformanceResponse(BaseModel):
    avg_actual_hours: float | None   # None = 実績データなし
    min_actual_hours: float | None
    max_actual_hours: float | None
    task_count: int                  # 実績ありの類似タスク数
    similar_tasks: list[PastPerformanceSimilarTask]  # 最大3件
```

---

## 3. フロントエンド

### 3-1. フック（既存ファイルに追加）

**ファイル:** `frontend/src/hooks/useTaskDetails.ts`

```typescript
export function usePastPerformance(taskId: string) {
  return useQuery({
    queryKey: ['tasks', taskId, 'past-performance'],
    queryFn: () => api.get(`/tasks/${taskId}/past-performance`).then(r => r.data),
    enabled: !!taskId,
    staleTime: 5 * 60 * 1000,  // 5分キャッシュ
  })
}
```

### 3-2. UI（工数タブへの追加）

**ファイル:** `frontend/src/pages/Tasks/TaskDetail.tsx`

工数タブの既存工数一覧の下に `PastPerformanceSection` コンポーネントを追加する（同ファイル内）。

**表示仕様:**

```
┌── 過去の類似タスク実績 ────────────────────┐
│  平均: 2.5h  最小: 1.0h  最大: 4.5h  4件   │
│  ─────────────────────────────────────    │
│  ・月次報告書作成（2026-04-30）  2.0h       │
│  ・月次報告書作成（2026-03-31）  3.0h       │
│  ・月次報告書作成（2026-02-28）  2.5h       │
└────────────────────────────────────────   ┘
```

- タグ0件または `task_count === 0` の場合: 「過去データなし」と表示（セクション自体は表示）
- ローディング中: Ant Design `<Spin />`
- 統計は Ant Design `<Statistic />` コンポーネントで表示
- タスク一覧は `<List size="small" />` で表示

---

## 4. テスト

**ファイル:** `tests/unit/test_past_performance.py`

| # | テストケース | 検証内容 |
|---|-------------|---------|
| 1 | タグ一致の完了タスクがある場合 | 200・avg/min/max/count が正しい |
| 2 | タグが0件のタスク | 200・`task_count=0`・`similar_tasks=[]` |
| 3 | 完了タスクがない（未完了のみ） | 200・`task_count=0` |
| 4 | 自分自身が結果に含まれない | 200・対象タスクIDがsimilar_tasksにない |
| 5 | タスクが存在しない | 404 |
| 6 | actual_hours が null のタスクは除外 | 200・null 工数レコードは集計されない |

---

## 5. スコープ外

- 類似判定基準をタグ以外（タイトルキーワード等）に切り替えるUI
- 類似タスクへのナビゲーションリンク
- 担当者別フィルタ（担当者が同じ人の実績のみ表示など）
