import { Typography, List, Tag, Card, Space } from 'antd'
import { useTodayTasks, useOverdueTasks } from '../../hooks/useDashboard'
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
            renderItem={(item: Record<string, unknown>) => (
              <List.Item>
                <Space>
                  <Tag color={PRIORITY_COLOR[String(item['priority'])] ?? 'default'}>
                    {String(item['priority'])}
                  </Tag>
                  {String(item['title'])}
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
              renderItem={(item: Record<string, unknown>) => (
                <List.Item>
                  <Space>
                    <Tag color="red">{String(item['due_date'])}</Tag>
                    {String(item['title'])}
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
