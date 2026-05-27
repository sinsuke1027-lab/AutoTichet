import { RobotOutlined } from '@ant-design/icons'
import { Button, Checkbox, Input, Space, Spin, Tag, Typography } from 'antd'
import { useState } from 'react'
import {
  useCreateSubtask,
  useGenerateSubtasks,
  useSubtasks,
  useUpdateSubtaskStatus,
} from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
}

export default function SubtasksPanel({ taskId }: Props) {
  const { data: subtasks = [] } = useSubtasks(taskId)
  const createSubtask = useCreateSubtask(taskId)
  const updateStatus = useUpdateSubtaskStatus(taskId)
  const generateSubtasks = useGenerateSubtasks(taskId)
  const [newTitle, setNewTitle] = useState('')
  const [suggestions, setSuggestions] = useState<string[] | null>(null)
  const [checked, setChecked] = useState<Set<string>>(new Set())

  const handleAdd = async () => {
    if (!newTitle.trim()) return
    await createSubtask.mutateAsync(newTitle.trim())
    setNewTitle('')
  }

  const handleGenerate = async () => {
    const result = await generateSubtasks.mutateAsync()
    setSuggestions(result.suggested_titles)
    setChecked(new Set(result.suggested_titles))
  }

  const toggleChecked = (title: string) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(title)) next.delete(title)
      else next.add(title)
      return next
    })
  }

  const handleCreateChecked = async () => {
    for (const title of suggestions ?? []) {
      if (checked.has(title)) {
        await createSubtask.mutateAsync(title)
      }
    }
    setSuggestions(null)
    setChecked(new Set())
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {subtasks.map((s) => (
        <Space key={s.id}>
          <Checkbox
            checked={s.status === 'completed'}
            onChange={(e) =>
              updateStatus.mutate({
                id: s.id,
                status: e.target.checked ? 'completed' : 'not_started',
              })
            }
          />
          <Typography.Text delete={s.status === 'completed'}>{s.title}</Typography.Text>
          <Tag>{s.status}</Tag>
        </Space>
      ))}

      <Space.Compact style={{ width: '100%' }}>
        <Input
          placeholder="サブタスクを追加..."
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onPressEnter={handleAdd}
        />
        <Button onClick={handleAdd} loading={createSubtask.isPending}>
          追加
        </Button>
      </Space.Compact>

      {suggestions === null ? (
        <Button
          icon={<RobotOutlined />}
          onClick={handleGenerate}
          loading={generateSubtasks.isPending}
        >
          AI でサブタスクを提案
        </Button>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text type="secondary">提案されたサブタスク（追加するものを選択）</Typography.Text>
          {generateSubtasks.isPending ? (
            <Spin />
          ) : (
            suggestions.map((title) => (
              <Checkbox
                key={title}
                checked={checked.has(title)}
                onChange={() => toggleChecked(title)}
              >
                {title}
              </Checkbox>
            ))
          )}
          <Space>
            <Button
              type="primary"
              onClick={handleCreateChecked}
              loading={createSubtask.isPending}
              disabled={checked.size === 0}
            >
              選択して追加（{checked.size}件）
            </Button>
            <Button onClick={() => { setSuggestions(null); setChecked(new Set()) }}>
              キャンセル
            </Button>
          </Space>
        </Space>
      )}
    </Space>
  )
}
