import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Form,
  message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useTasks, useCreateTask } from '../../hooks/useTasks'
import type { Task } from '../../lib/api'

const STATUS_COLOR: Record<string, string> = {
  not_started: 'default',
  in_progress: 'processing',
  completed: 'success',
  cancelled: 'error',
}

const STATUS_LABEL: Record<string, string> = {
  not_started: '未着手',
  in_progress: '進行中',
  completed: '完了',
  cancelled: 'キャンセル',
}

const PRIORITY_COLOR: Record<string, string> = {
  low: 'green',
  medium: 'blue',
  high: 'orange',
  urgent: 'red',
}

export default function TaskList() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const { data, isLoading } = useTasks({ status: statusFilter })
  const createTask = useCreateTask()

  const columns: ColumnsType<Task> = [
    {
      title: 'タイトル',
      dataIndex: 'title',
      render: (text: string, record: Task) => (
        <Button type="link" onClick={() => navigate(`/tasks/${record.id}`)}>
          {text}
        </Button>
      ),
    },
    {
      title: 'ステータス',
      dataIndex: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'}>{STATUS_LABEL[s] ?? s}</Tag>
      ),
    },
    {
      title: '優先度',
      dataIndex: 'priority',
      render: (p: string) => <Tag color={PRIORITY_COLOR[p] ?? 'default'}>{p}</Tag>,
    },
    {
      title: '期限',
      dataIndex: 'due_date',
      render: (d: string | null) => (d ? dayjs(d).format('YYYY/MM/DD') : '—'),
    },
    {
      title: 'タグ',
      dataIndex: 'tags',
      render: (tags: string[]) => tags.map((t) => <Tag key={t}>{t}</Tag>),
    },
  ]

  const handleCreate = async () => {
    const values = await form.validateFields()
    try {
      await createTask.mutateAsync(values)
      message.success('タスクを作成しました')
      form.resetFields()
      setModalOpen(false)
    } catch {
      message.error('タスクの作成に失敗しました')
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          タスク一覧
        </Typography.Title>
        <Space>
          <Select
            allowClear
            placeholder="ステータス"
            style={{ width: 120 }}
            onChange={setStatusFilter}
            options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新規タスク
          </Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.items ?? []}
        columns={columns}
        pagination={{ total: data?.total, pageSize: 50 }}
      />

      <Modal
        title="新規タスク作成"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        okText="作成"
        cancelText="キャンセル"
        confirmLoading={createTask.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true, message: '必須' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="詳細">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="priority" label="優先度" initialValue="medium">
            <Select
              options={[
                { value: 'low', label: '低' },
                { value: 'medium', label: '中' },
                { value: 'high', label: '高' },
                { value: 'urgent', label: '緊急' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
