# F-28 工数自動初期値設定 設計書

**最終更新:** 2026-05-28  
**ステータス:** 承認済み  
**対応要件:** F-28「過去実績から工数の初期値を自動設定」（Should / Phase 2）  
**依存:** F-27 完了済み（`usePastPerformance` フック・`GET /tasks/{id}/past-performance` API）

---

## 1. 概要

タスク詳細の工数タブを開いたとき、「予定工数(h)」フィールドに同タグの過去実績平均値を自動入力する。
ユーザーは入力済みの値をそのまま使うか、上書きして記録できる。

---

## 2. 変更ファイル

`frontend/src/pages/Tasks/components/WorkHoursPanel.tsx` のみ。  
バックエンド変更・新規 API・新規 Pydantic モデルは不要。

---

## 3. 実装内容

### 3-1. `usePastPerformance` の呼び出し追加

`WorkHoursPanel` コンポーネント内で `usePastPerformance(taskId)` を呼び出す。  
`PastPerformanceSection` が既に同じ queryKey `['past-performance', taskId]` でキャッシュしているため、追加の API リクエストは発生しない。

### 3-2. `useEffect` による自動入力

```typescript
const { data: perfData, isSuccess: perfSuccess } = usePastPerformance(taskId)

useEffect(() => {
  if (perfSuccess && perfData?.avg_actual_hours != null) {
    const current = form.getFieldValue('estimated_hours')
    if (current == null) {
      form.setFieldValue('estimated_hours', Number(perfData.avg_actual_hours.toFixed(1)))
    }
  }
}, [perfSuccess])
```

**動作仕様:**

| 条件 | 動作 |
|------|------|
| 過去データあり・フォームが空 | `avg_actual_hours` を小数点1桁で自動入力 |
| 過去データあり・ユーザーが既に入力済み | 上書きしない |
| 過去データなし（`avg_actual_hours === null`） | 何もしない |
| データ取得中（`isSuccess === false`） | 何もしない |

- `toFixed(1)` で小数点1桁に丸める（InputNumber の `precision={1}` と一致）
- `perfSuccess` を dependency にすることでデータ到着時に一度だけ発火

---

## 4. テスト方針

バックエンド変更なしのため、バックエンドテスト追加なし。  
フロントエンド: TypeScript 型チェック（`npx tsc --noEmit`）のみ。

---

## 5. スコープ外

- タスク作成モーダルでの自動入力（F-28 は工数タブのみ）
- 自動入力された値に視覚的な区別（バッジ等）を付ける
- 平均以外の値（中央値・最小値等）を使うオプション
