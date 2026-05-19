import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Descriptions,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useTask, useUpdateTask } from '../../hooks/useTasks'

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: task, isLoading } = useTask(id ?? '')
  const updateTask = useUpdateTask()

  if (isLoading) return <div>読み込み中...</div>
  if (!task) return <div>タスクが見つかりません</div>

  const handleStatusChange = async (status: string) => {
    await updateTask.mutateAsync({ id: task.id, status })
    message.success('ステータスを更新しました')
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          一覧へ
        </Button>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {task.title}
        </Typography.Title>
      </Space>

      <Card>
        <Descriptions column={2} bordered>
          <Descriptions.Item label="ステータス">
            <Select
              value={task.status}
              onChange={handleStatusChange}
              options={[
                { value: 'not_started', label: '未着手' },
                { value: 'in_progress', label: '進行中' },
                { value: 'completed', label: '完了' },
                { value: 'cancelled', label: 'キャンセル' },
              ]}
              style={{ width: 120 }}
            />
          </Descriptions.Item>
          <Descriptions.Item label="優先度">
            <Tag>{task.priority}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="期限">
            {task.due_date ? dayjs(task.due_date).format('YYYY/MM/DD') : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="公開範囲">{task.visibility}</Descriptions.Item>
          <Descriptions.Item label="タグ" span={2}>
            {task.tags.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </Descriptions.Item>
          <Descriptions.Item label="詳細" span={2}>
            {task.description ?? '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  )
}
