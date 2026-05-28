import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  DatePicker,
  Divider,
  Form,
  Input,
  message,
  Modal,
  Progress,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useTasks, useCreateTask } from '../../hooks/useTasks'
import { useProjects } from '../../hooks/useProjects'
import { useSections } from '../../hooks/useSections'
import { useSimilarTasks } from '../../hooks/useSimilarTasks'
import { useUsers } from '../../hooks/useUsers'
import { useTemplates, useApplyTemplate } from '../../hooks/useTemplates'
import { useAuthStore } from '../../store/useAuthStore'
import type { Task } from '../../lib/api'

const ROLE_LEVEL: Record<string, number> = { member: 0, leader: 1, manager: 2, admin: 3 }

const STATUS_OPTIONS = [
  { label: '全て', value: '' },
  { label: '未着手', value: 'not_started' },
  { label: '進行中', value: 'in_progress' },
  { label: '完了', value: 'completed' },
  { label: 'キャンセル', value: 'cancelled' },
]

export default function TaskList() {
  const navigate = useNavigate()
  const roles = useAuthStore((s) => s.roles)
  const userLevel = Math.max(...roles.map((r) => ROLE_LEVEL[r] ?? 0), 0)
  const canFilterByAssignee = userLevel >= ROLE_LEVEL['leader']

  const [statusFilter, setStatusFilter] = useState('')
  const [projectFilter, setProjectFilter] = useState<string | undefined>()
  const [sectionFilter, setSectionFilter] = useState<string | undefined>()
  const [assigneeFilter, setAssigneeFilter] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [myTasksOnly, setMyTasksOnly] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const { data: taskList, isLoading } = useTasks({
    status: statusFilter || undefined,
    assignee: assigneeFilter,
    project_id: projectFilter,
    section_id: sectionFilter,
    q: searchQ || undefined,
    my_tasks_only: myTasksOnly || undefined,
  })
  const { data: projects = [] } = useProjects()
  const { data: sections = [] } = useSections(projectFilter)
  const { data: users = [] } = useUsers()
  const createTask = useCreateTask()
  const { data: similarTasks = [] } = useSimilarTasks(newTitle)
  const { data: templates = [] } = useTemplates()
  const applyTemplate = useApplyTemplate()
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | undefined>()
  const [templateBaseDate, setTemplateBaseDate] = useState<string>(
    new Date().toISOString().split('T')[0],
  )

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

  const handleApplyTemplate = async () => {
    if (!selectedTemplateId) return
    try {
      const result = await applyTemplate.mutateAsync({
        id: selectedTemplateId,
        body: { base_date: templateBaseDate },
      })
      setOpen(false)
      setSelectedTemplateId(undefined)
      setTemplateBaseDate(new Date().toISOString().split('T')[0])
      navigate(`/tasks/${result.task_id}`)
    } catch {
      void message.error('テンプレートの適用に失敗しました')
    }
  }

  const STATUS_LABEL: Record<string, string> = {
    not_started: '未着手',
    in_progress: '進行中',
    completed: '完了',
    cancelled: 'キャンセル',
  }
  const STATUS_COLOR: Record<string, string> = {
    not_started: 'default',
    in_progress: 'processing',
    completed: 'success',
    cancelled: 'error',
  }

  const columns = [
    {
      title: 'タスク名',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, rec: Task) => (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <a onClick={() => navigate(`/tasks/${rec.id}`)}>{title}</a>
          {rec.risk_level === 'high' && <Tag color="red">高リスク</Tag>}
          {rec.risk_level === 'medium' && <Tag color="orange">要注意</Tag>}
        </span>
      ),
    },
    {
      title: 'ステータス',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'}>{STATUS_LABEL[s] ?? s}</Tag>
      ),
    },
    { title: '優先度', dataIndex: 'priority', key: 'priority' },
    {
      title: '期限',
      dataIndex: 'due_date',
      key: 'due_date',
      render: (d: string | null) => d ?? '—',
    },
    {
      title: 'サブタスク',
      key: 'subtasks',
      width: 120,
      render: (_: unknown, rec: Task) => {
        const total = rec.subtask_count ?? 0
        if (total === 0) return <span style={{ color: '#bbb' }}>—</span>
        const done = rec.subtask_done_count ?? 0
        const pct = Math.round((done / total) * 100)
        return (
          <Tooltip title={`${done} / ${total} 件完了`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Progress
                percent={pct}
                size="small"
                style={{ width: 60, margin: 0 }}
                showInfo={false}
              />
              <span style={{ fontSize: 12, whiteSpace: 'nowrap', color: '#555' }}>
                {done}/{total}
              </span>
            </div>
          </Tooltip>
        )
      },
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
        {canFilterByAssignee && (
          <Select
            placeholder="担当者"
            allowClear
            options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
            value={assigneeFilter}
            onChange={(v: string | undefined) => {
              setAssigneeFilter(v)
              if (v) setMyTasksOnly(false)
            }}
            style={{ width: 150 }}
          />
        )}
        <Space>
          <Switch
            checked={myTasksOnly}
            onChange={(v) => {
              setMyTasksOnly(v)
              if (v) setAssigneeFilter(undefined)
            }}
          />
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
          setSelectedTemplateId(undefined)
          setTemplateBaseDate(new Date().toISOString().split('T')[0])
        }}
        confirmLoading={createTask.isPending}
      >
        {templates.length > 0 && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
            <Typography.Text strong>
              <RobotOutlined style={{ marginRight: 6 }} />
              テンプレートから作成
            </Typography.Text>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                <Select
                  placeholder="テンプレートを選択"
                  style={{ width: 220 }}
                  allowClear
                  options={templates.map((t) => ({ label: t.name, value: t.id }))}
                  value={selectedTemplateId}
                  onChange={setSelectedTemplateId}
                />
                <DatePicker
                  placeholder="基準日"
                  value={selectedTemplateId ? dayjs(templateBaseDate) : undefined}
                  onChange={(d) => d && setTemplateBaseDate(d.format('YYYY-MM-DD'))}
                />
                <Button
                  type="primary"
                  disabled={!selectedTemplateId}
                  loading={applyTemplate.isPending}
                  onClick={() => void handleApplyTemplate()}
                >
                  このテンプレートで作成
                </Button>
              </Space>
            </div>
          </div>
        )}
        {templates.length > 0 && <Divider plain>または手動で作成</Divider>}
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
