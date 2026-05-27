import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Descriptions,
  message,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import { CopyOutlined, DeleteOutlined } from '@ant-design/icons'
import { useTask, useUpdateTask, useDeleteTask } from '../../hooks/useTasks'
import { useSections } from '../../hooks/useSections'
import { useClarifyRequirements } from '../../hooks/useTaskDetails'
import CommentsPanel from './components/CommentsPanel'
import WorkHoursPanel from './components/WorkHoursPanel'
import SubtasksPanel from './components/SubtasksPanel'
import api from '../../lib/api'

const STATUS_OPTIONS = [
  { label: '未着手', value: 'not_started' },
  { label: '進行中', value: 'in_progress' },
  { label: '完了', value: 'completed' },
  { label: 'キャンセル', value: 'cancelled' },
]

const PRIORITY_OPTIONS = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '最高', value: 'urgent' },
]

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: task, isLoading } = useTask(id ?? '')
  const updateTask = useUpdateTask(id ?? '')
  const deleteTask = useDeleteTask()
  const { data: sections = [] } = useSections(task?.project_id ?? undefined)
  const [duplicating, setDuplicating] = useState(false)
  const clarify = useClarifyRequirements(id ?? '')

  if (isLoading) return <Spin />
  if (!task) return <Typography.Text>タスクが見つかりません</Typography.Text>

  const handleFieldChange = async (field: string, value: unknown) => {
    try {
      await updateTask.mutateAsync({ [field]: value })
    } catch {
      void message.error('更新に失敗しました')
    }
  }

  const handleDelete = async () => {
    try {
      await deleteTask.mutateAsync(id ?? '')
      void message.success('タスクを削除しました')
      navigate('/tasks')
    } catch {
      void message.error('削除に失敗しました')
    }
  }

  const handleDuplicate = async () => {
    setDuplicating(true)
    try {
      const res = await api.post<{ id: string }>(`/tasks/${id}/duplicate`)
      void message.success('タスクを複製しました')
      navigate(`/tasks/${res.data.id}`)
    } catch {
      void message.error('複製に失敗しました')
    } finally {
      setDuplicating(false)
    }
  }

  const tabItems = [
    {
      key: 'detail',
      label: '詳細',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="ステータス">
              <Select
                value={task.status}
                options={STATUS_OPTIONS}
                onChange={(v) => handleFieldChange('status', v)}
                style={{ width: 140 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="優先度">
              <Select
                value={task.priority}
                options={PRIORITY_OPTIONS}
                onChange={(v) => handleFieldChange('priority', v)}
                style={{ width: 120 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="セクション">
              <Select
                value={task.section_id ?? undefined}
                allowClear
                options={sections.map((s) => ({ label: s.name, value: s.id }))}
                onChange={(v: string | undefined) => handleFieldChange('section_id', v ?? null)}
                style={{ width: 200 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="期限">{task.due_date ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="公開範囲">{task.visibility}</Descriptions.Item>
            <Descriptions.Item label="タグ">
              {task.tags.map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
            </Descriptions.Item>
            <Descriptions.Item label="説明">{task.description ?? '—'}</Descriptions.Item>
          </Descriptions>
          <Button
            onClick={async () => {
              const result = await clarify.mutateAsync()
              if (result.issues.length === 0) {
                void message.success('問題は検出されませんでした')
              }
            }}
            loading={clarify.isPending}
          >
            🤖 AI チェック
          </Button>
          {clarify.data && clarify.data.issues.length > 0 && (
            <Alert
              type="warning"
              message="以下の項目を確認してください"
              description={
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {clarify.data.issues.map((issue) => (
                    <li key={issue.field}>
                      {issue.message}
                      {issue.suggestion && (
                        <Typography.Text type="secondary">
                          {' — '}{issue.suggestion}
                        </Typography.Text>
                      )}
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </Space>
      ),
    },
    {
      key: 'comments',
      label: 'コメント',
      children: <CommentsPanel taskId={id ?? ''} />,
    },
    {
      key: 'work-hours',
      label: '工数',
      children: <WorkHoursPanel taskId={id ?? ''} />,
    },
    {
      key: 'subtasks',
      label: 'サブタスク',
      children: <SubtasksPanel taskId={id ?? ''} />,
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {task.title}
        </Typography.Title>
        <Space>
          <Button icon={<CopyOutlined />} onClick={handleDuplicate} loading={duplicating}>
            複製
          </Button>
          <Popconfirm
            title="タスクを削除"
            description="このタスクを削除しますか？この操作は元に戻せません。"
            onConfirm={handleDelete}
            okText="削除"
            okButtonProps={{ danger: true }}
            cancelText="キャンセル"
          >
            <Button
              icon={<DeleteOutlined />}
              danger
              loading={deleteTask.isPending}
            >
              削除
            </Button>
          </Popconfirm>
        </Space>
      </Space>
      <Tabs items={tabItems} />
    </Space>
  )
}
