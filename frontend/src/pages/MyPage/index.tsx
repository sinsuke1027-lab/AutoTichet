import { Card, Col, List, Row, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useMyOverdueTasks, useMyWeeklyTasks } from '../../hooks/useMyPage'
import ProfileCard from './ProfileCard'
import WeeklySummary from './WeeklySummary'
import type { Task } from '../../lib/api'

const STATUS_COLORS: Record<string, string> = {
  not_started: 'default',
  in_progress: 'processing',
  completed: 'success',
  cancelled: 'error',
}

const STATUS_LABELS: Record<string, string> = {
  not_started: '未着手',
  in_progress: '進行中',
  completed: '完了',
  cancelled: 'キャンセル',
}

export default function MyPage() {
  const navigate = useNavigate()
  const { data: weeklyTasksData } = useMyWeeklyTasks()
  const { data: overdueTasksData } = useMyOverdueTasks()

  const weeklyTasks = weeklyTasksData?.items ?? []
  const overdueTasks = (overdueTasksData?.items ?? []).filter(
    (t) => t.status !== 'completed' && t.status !== 'cancelled',
  )

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Typography.Title level={4} style={{ margin: 0 }}>
        マイページ
      </Typography.Title>

      <Row gutter={16}>
        <Col span={10}>
          <ProfileCard />
        </Col>
        <Col span={14}>
          <WeeklySummary />
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card
            title="今週のタスク"
            extra={<Tag color="blue">{weeklyTasks.length}件</Tag>}
          >
            <List
              dataSource={weeklyTasks}
              renderItem={(task: Task) => (
                <List.Item
                  key={task.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/tasks/${task.id}`)}
                >
                  <Space>
                    <Tag color={STATUS_COLORS[task.status]}>
                      {STATUS_LABELS[task.status] ?? task.status}
                    </Tag>
                    <Typography.Text>{task.title}</Typography.Text>
                  </Space>
                </List.Item>
              )}
              locale={{ emptyText: '今週のタスクはありません' }}
              style={{ maxHeight: 300, overflowY: 'auto' }}
            />
          </Card>
        </Col>

        <Col span={12}>
          <Card
            title="期限超過タスク"
            extra={
              overdueTasks.length > 0 ? (
                <Tag color="red">{overdueTasks.length}件</Tag>
              ) : null
            }
          >
            <List
              dataSource={overdueTasks}
              renderItem={(task: Task) => (
                <List.Item
                  key={task.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/tasks/${task.id}`)}
                >
                  <Space>
                    <Tag color="red">{task.due_date ?? '—'}</Tag>
                    <Typography.Text>{task.title}</Typography.Text>
                  </Space>
                </List.Item>
              )}
              locale={{ emptyText: '期限超過タスクはありません' }}
              style={{ maxHeight: 300, overflowY: 'auto' }}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
