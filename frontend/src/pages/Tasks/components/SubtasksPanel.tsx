import { Button, Checkbox, Input, Space, Tag, Typography } from 'antd'
import { useState } from 'react'
import {
  useSubtasks,
  useCreateSubtask,
  useUpdateSubtaskStatus,
} from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
}

export default function SubtasksPanel({ taskId }: Props) {
  const { data: subtasks = [] } = useSubtasks(taskId)
  const createSubtask = useCreateSubtask(taskId)
  const updateStatus = useUpdateSubtaskStatus(taskId)
  const [newTitle, setNewTitle] = useState('')

  const handleAdd = async () => {
    if (!newTitle.trim()) return
    await createSubtask.mutateAsync(newTitle.trim())
    setNewTitle('')
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
    </Space>
  )
}
