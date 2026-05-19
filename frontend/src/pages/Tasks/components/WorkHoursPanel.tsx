import { Button, Form, InputNumber, Space, Table } from 'antd'
import { useWorkHours, useCreateWorkHour } from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
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
    </Space>
  )
}
