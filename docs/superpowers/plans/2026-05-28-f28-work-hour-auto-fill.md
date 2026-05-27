# F-28 工数自動初期値設定 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク詳細の工数タブを開いたとき、「予定工数(h)」フィールドに同タグの過去実績平均値を自動入力する。

**Architecture:** `WorkHoursPanel.tsx` 内で `usePastPerformance(taskId)` を呼び出し、データ到着時に `useEffect` で `form.setFieldValue` を呼ぶ。`PastPerformanceSection` が同じ `queryKey` でキャッシュ済みなので追加 API リクエストは発生しない。フォームが空のときのみ自動入力し、ユーザーが既に入力した値は上書きしない。

**Tech Stack:** React 18 (`useEffect`), TanStack Query v5 (`usePastPerformance`), Ant Design 5.x (`Form.useForm`, `form.setFieldValue`, `form.getFieldValue`)

---

## ファイル変更マップ

| 対象 | 変更内容 |
|------|---------|
| Modify: `frontend/src/pages/Tasks/components/WorkHoursPanel.tsx` | `useEffect` インポート追加・`WorkHoursPanel` 内に `usePastPerformance` + `useEffect` 追加 |

---

### Task 1: WorkHoursPanel に自動入力ロジックを追加

**Files:**
- Modify: `frontend/src/pages/Tasks/components/WorkHoursPanel.tsx`

#### 背景と注意点

現在の `WorkHoursPanel.tsx`（L1–L141）には React からの import がない。`PastPerformanceSection`（L22–L73）は既に `usePastPerformance` を呼んでいるが、`WorkHoursPanel` 本体（L75–L141）は呼んでいない。

TanStack Query の queryKey `['past-performance', taskId]` は `PastPerformanceSection` と `WorkHoursPanel` で共有されるため、2 回目の `usePastPerformance` 呼び出しは追加 API リクエストを発生させない。

- [ ] **Step 1: `useEffect` import を追加し、`WorkHoursPanel` に自動入力ロジックを実装する**

`frontend/src/pages/Tasks/components/WorkHoursPanel.tsx` を以下の内容に完全置換する:

```tsx
import { useEffect } from 'react'
import { Button, Divider, Form, InputNumber, List, Space, Spin, Statistic, Table, Typography } from 'antd'
import { useWorkHours, useCreateWorkHour, usePastPerformance } from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
}

interface PastPerformanceSimilarTaskItem {
  id: string
  title: string
  actual_hours: number
}

interface PastPerformanceData {
  avg_actual_hours: number | null
  min_actual_hours: number | null
  max_actual_hours: number | null
  task_count: number
  similar_tasks: PastPerformanceSimilarTaskItem[]
}

function PastPerformanceSection({ taskId }: Props) {
  const { data, isLoading } = usePastPerformance(taskId)

  return (
    <div>
      <Divider orientation="left" plain>
        過去の類似タスク実績
      </Divider>
      {isLoading ? (
        <Spin size="small" />
      ) : !data || data.task_count === 0 ? (
        <Typography.Text type="secondary">過去データなし</Typography.Text>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <Statistic
              title="平均実績"
              value={data.avg_actual_hours ?? 0}
              suffix="h"
              precision={1}
            />
            <Statistic
              title="最小"
              value={data.min_actual_hours ?? 0}
              suffix="h"
              precision={1}
            />
            <Statistic
              title="最大"
              value={data.max_actual_hours ?? 0}
              suffix="h"
              precision={1}
            />
            <Statistic title="件数" value={data.task_count} suffix="件" />
          </Space>
          <List<PastPerformanceSimilarTaskItem>
            size="small"
            dataSource={data.similar_tasks}
            renderItem={(item) => (
              <List.Item>
                <Typography.Text>{item.title}</Typography.Text>
                <Typography.Text type="secondary" style={{ marginLeft: 'auto' }}>
                  {item.actual_hours}h
                </Typography.Text>
              </List.Item>
            )}
          />
        </Space>
      )}
    </div>
  )
}

export default function WorkHoursPanel({ taskId }: Props) {
  const { data: records = [] } = useWorkHours(taskId)
  const createWorkHour = useCreateWorkHour(taskId)
  const [form] = Form.useForm()
  const { data: perfData, isSuccess: perfSuccess } = usePastPerformance(taskId)

  useEffect(() => {
    if (perfSuccess && perfData?.avg_actual_hours != null) {
      const current = form.getFieldValue('estimated_hours')
      if (current == null) {
        form.setFieldValue('estimated_hours', Number(perfData.avg_actual_hours.toFixed(1)))
      }
    }
  }, [perfSuccess])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    await createWorkHour.mutateAsync(
      values as { estimated_hours?: number; actual_hours?: number; notes?: string },
    )
    form.resetFields()
  }

  const columns = [
    {
      title: '記録日時',
      dataIndex: 'recorded_at',
      key: 'recorded_at',
      render: (d: string) => new Date(d).toLocaleString('ja-JP'),
    },
    {
      title: '予定(h)',
      dataIndex: 'estimated_hours',
      key: 'estimated_hours',
      render: (v: number | null) => v ?? '—',
    },
    {
      title: '実績(h)',
      dataIndex: 'actual_hours',
      key: 'actual_hours',
      render: (v: number | null) => v ?? '—',
    },
    {
      title: 'メモ',
      dataIndex: 'notes',
      key: 'notes',
      render: (v: string | null) => v ?? '—',
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Form form={form} layout="inline">
        <Form.Item name="estimated_hours" label="予定工数(h)">
          <InputNumber min={0} step={0.5} precision={1} />
        </Form.Item>
        <Form.Item name="actual_hours" label="実績工数(h)">
          <InputNumber min={0} step={0.5} precision={1} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" onClick={handleSubmit} loading={createWorkHour.isPending}>
            記録
          </Button>
        </Form.Item>
      </Form>
      <Table
        rowKey="id"
        dataSource={records}
        columns={columns}
        size="small"
        pagination={false}
        locale={{ emptyText: '工数記録はありません' }}
      />
      <PastPerformanceSection taskId={taskId} />
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript 型チェックを実行して通過を確認する**

```powershell
cd frontend
npx tsc --noEmit
```

期待結果: エラー出力なし（0 errors）

- [ ] **Step 3: コミットする**

```powershell
git add frontend/src/pages/Tasks/components/WorkHoursPanel.tsx
git commit -m "feat: F-28 工数タブを開いた際に過去実績平均値を自動入力"
```
