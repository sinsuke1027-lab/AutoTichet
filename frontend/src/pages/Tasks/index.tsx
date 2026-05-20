import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Form,
  Input,
  message,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { useTasks, useCreateTask } from '../../hooks/useTasks'
import { useProjects } from '../../hooks/useProjects'
import { useSections } from '../../hooks/useSections'
import { useSimilarTasks } from '../../hooks/useSimilarTasks'
import type { Task } from '../../lib/api'

const STATUS_OPTIONS = [
  { label: '全て', value: '' },
  { label: '未着手', value: 'not_started' },
  { label: '進行中', value: 'in_progress' },
  { label: '完了', value: 'completed' },
  { label: 'キャンセル', value: 'cancelled' },
]

export default function TaskList() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState('')
  const [projectFilter, setProjectFilter] = useState<string | undefined>()
  const [sectionFilter, setSectionFilter] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [myTasksOnly, setMyTasksOnly] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const { data: taskList, isLoading } = useTasks({
    status: statusFilter || undefined,
    project_id: projectFilter,
    section_id: sectionFilter,
    q: searchQ || undefined,
    my_tasks_only: myTasksOnly || undefined,
  })
  const { data: projects = [] } = useProjects()
  const { data: sections = [] } = useSections(projectFilter)
  const createTask = useCreateTask()
  const { data: similarTasks = [] } = useSimilarTasks(newTitle)

  const handleSearch = () => setSearchQ(keyword)

  const handleCreate = async () => {
    const values = await form.validateFields()
    try {
      await createTask.mutateAsync(
        values as { title: string; description?: string; visibility?: string },
      )
      form.resetFields()
      setNewTitle('')
      setOpen(false)
    } catch {
      void message.error('タスクの作成に失敗しました')
    }
  }

  const columns = [
    {
      title: 'タスク名',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, rec: Task) => (
        <a onClick={() => navigate(`/tasks/${rec.id}`)}>{title}</a>
      ),
    },
    {
      title: 'ステータス',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag>{s}</Tag>,
    },
    { title: '優先度', dataIndex: 'priority', key: 'priority' },
    {
      title: '期限',
      dataIndex: 'due_date',
      key: 'due_date',
      render: (d: string | null) => d ?? '—',
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          タスク一覧
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新規タスク
        </Button>
      </Space>

      <Space wrap>
        <Input
          placeholder="キーワード検索"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          suffix={<SearchOutlined onClick={handleSearch} style={{ cursor: 'pointer' }} />}
          style={{ width: 220 }}
        />
        <Select
          placeholder="ステータス"
          options={STATUS_OPTIONS}
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 130 }}
        />
        <Select
          placeholder="プロジェクト"
          allowClear
          options={projects.map((p) => ({ label: p.name, value: p.id }))}
          value={projectFilter}
          onChange={(v: string | undefined) => {
            setProjectFilter(v)
            setSectionFilter(undefined)
          }}
          style={{ width: 160 }}
        />
        {projectFilter !== undefined && (
          <Select
            placeholder="セクション"
            allowClear
            options={sections.map((s) => ({ label: s.name, value: s.id }))}
            value={sectionFilter}
            onChange={setSectionFilter}
            style={{ width: 160 }}
          />
        )}
        <Space>
          <Switch checked={myTasksOnly} onChange={setMyTasksOnly} />
          <span>自分の ToDo のみ</span>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={taskList?.items ?? []}
        columns={columns}
        pagination={{ pageSize: 20, total: taskList?.total, showSizeChanger: false }}
      />

      <Modal
        title="新規タスク作成"
        open={open}
        onOk={() => void handleCreate()}
        onCancel={() => {
          setOpen(false)
          form.resetFields()
          setNewTitle('')
        }}
        confirmLoading={createTask.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="タスク名" rules={[{ required: true }]}>
            <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          </Form.Item>
          {similarTasks.length > 0 && (
            <Alert
              type="warning"
              style={{ marginBottom: 12 }}
              message={`類似タスクが見つかりました（${similarTasks.length}件）`}
              description={
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {similarTasks.map((t) => (
                    <li key={t.id}>
                      {t.title} ({t.status})
                    </li>
                  ))}
                </ul>
              }
            />
          )}
          <Form.Item name="description" label="説明">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="visibility" label="公開範囲" initialValue="team">
            <Select
              options={[
                { label: 'チーム共有', value: 'team' },
                { label: '全公開', value: 'all' },
                { label: '個人（ToDo）', value: 'private' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
