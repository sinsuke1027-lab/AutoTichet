import { Typography, List, Tag, Card, Space } from 'antd'
import { useTodayTasks, useOverdueTasks } from '../../hooks/useDashboard'
import type { TodayTaskItem, OverdueTaskItem } from '../../lib/api'
import dayjs from 'dayjs'

const PRIORITY_COLOR: Record<string, string> = {
  low: 'green',
  medium: 'blue',
  high: 'orange',
  urgent: 'red',
}

export default function Schedule() {
  const { data: todayTasks, isLoading } = useTodayTasks()
  const { data: overdueTasks } = useOverdueTasks()

  return (
    <div>
      <Typography.Title level={4}>
        1日スケジュール — {dayjs().format('YYYY年M月D日（ddd）')}
      </Typography.Title>

      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Card title="今日やること" loading={isLoading}>
          <List
            dataSource={todayTasks ?? []}
            renderItem={(item: TodayTaskItem) => (
              <List.Item key={item.id}>
                <Space>
                  <Tag color={PRIORITY_COLOR[item.priority] ?? 'default'}>
                    {item.priority}
                  </Tag>
                  {item.title}
                </Space>
              </List.Item>
            )}
            locale={{ emptyText: '今日のタスクはありません' }}
          />
        </Card>

        {(overdueTasks?.length ?? 0) > 0 && (
          <Card title="期限超過">
            <List
              dataSource={overdueTasks ?? []}
              renderItem={(item: OverdueTaskItem) => (
                <List.Item key={item.id}>
                  <Space>
                    <Tag color="red">{item.due_date ?? '—'}</Tag>
                    {item.title}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Space>
    </div>
  )
}
