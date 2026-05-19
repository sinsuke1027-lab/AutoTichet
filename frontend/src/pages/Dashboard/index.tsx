import { Col, Row, Statistic, Card, List, Tag, Typography } from 'antd'
import {
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useDashboardSummary, useTodayTasks, useOverdueTasks } from '../../hooks/useDashboard'
import type { TodayTaskItem, OverdueTaskItem } from '../../lib/api'

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300']

export default function Dashboard() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary()
  const { data: todayTasks } = useTodayTasks()
  const { data: overdueTasks } = useOverdueTasks()

  const pieData = summary
    ? [
        { name: '未着手', value: summary.not_started },
        { name: '進行中', value: summary.in_progress },
        { name: '完了', value: summary.completed },
      ]
    : []

  return (
    <div>
      <Typography.Title level={4}>ダッシュボード</Typography.Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="総タスク数" value={summary?.total_tasks ?? 0} loading={summaryLoading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="完了率" value={summary?.completion_rate ?? 0} suffix="%" loading={summaryLoading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="進行中" value={summary?.in_progress ?? 0} loading={summaryLoading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="期限超過"
              value={summary?.overdue ?? 0}
              valueStyle={{ color: summary?.overdue ? '#cf1322' : undefined }}
              loading={summaryLoading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="ステータス分布">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label>
                  {pieData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col span={12}>
          <Card title="今日やること" extra={<Tag color="blue">{todayTasks?.length ?? 0}件</Tag>}>
            <List
              dataSource={todayTasks ?? []}
              renderItem={(item: TodayTaskItem) => (
                <List.Item key={item.id}>
                  <Tag color={item.priority === 'urgent' ? 'red' : 'default'}>
                    {item.priority}
                  </Tag>
                  {item.title}
                </List.Item>
              )}
              locale={{ emptyText: '今日のタスクはありません' }}
              style={{ maxHeight: 200, overflowY: 'auto' }}
            />
          </Card>
        </Col>
      </Row>

      {(overdueTasks?.length ?? 0) > 0 && (
        <Card title="期限超過タスク" style={{ marginBottom: 24 }}>
          <List
            dataSource={overdueTasks ?? []}
            renderItem={(item: OverdueTaskItem) => (
              <List.Item key={item.id}>
                <Tag color="red">{item.due_date ?? '—'}</Tag>
                {item.title}
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  )
}
