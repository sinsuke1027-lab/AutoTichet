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
