import { Col, Row, Statistic, Card, List, Tag, Typography, Button, Space, Popconfirm } from 'antd'
import { SettingOutlined, UserOutlined, ApartmentOutlined, BellOutlined, InboxOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import {
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useDashboardSummary, useTodayTasks, useOverdueTasks, useStaleTaskItems, useArchiveTask } from '../../hooks/useDashboard'
import { useAuthStore } from '../../store/useAuthStore'
import type { TodayTaskItem, OverdueTaskItem, StaleTaskItem } from '../../lib/api'

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300']

export default function Dashboard() {
  const navigate = useNavigate()
  const roles = useAuthStore((s) => s.roles)
  const isAdmin = roles.includes('admin')

  const { data: summary, isLoading: summaryLoading } = useDashboardSummary()
  const { data: todayTasks } = useTodayTasks()
  const { data: overdueTasks } = useOverdueTasks()
  const { data: staleTasks } = useStaleTaskItems()
  const archiveTask = useArchiveTask()

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

      {(staleTasks?.length ?? 0) > 0 && (
        <Card
          title={
            <Space>
              <InboxOutlined />
              棚卸し提案
              <Tag color="warning">{staleTasks?.length}件</Tag>
            </Space>
          }
          style={{ marginBottom: 24 }}
          extra={<Typography.Text type="secondary">14日以上更新なし</Typography.Text>}
        >
          <List
            dataSource={staleTasks ?? []}
            renderItem={(item: StaleTaskItem) => (
              <List.Item
                key={item.id}
                actions={[
                  <Popconfirm
                    key="archive"
                    title="このタスクをキャンセルにしますか？"
                    onConfirm={() => archiveTask.mutate(item.id)}
                    okText="キャンセルにする"
                    cancelText="閉じる"
                  >
                    <Button size="small" danger>キャンセルにする</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={item.title}
                  description={`${item.days_stale}日間放置${item.due_date ? ` / 期限: ${item.due_date}` : ''}`}
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {isAdmin && (
        <Card
          title={
            <Space>
              <SettingOutlined style={{ color: '#722ed1' }} />
              <span style={{ color: '#722ed1' }}>管理者メニュー</span>
            </Space>
          }
          style={{ borderColor: '#d3adf7', background: '#f9f0ff' }}
        >
          <Space wrap size="middle">
            <Button
              icon={<UserOutlined />}
              onClick={() => navigate('/admin?tab=users')}
            >
              ユーザー管理
            </Button>
            <Button
              icon={<ApartmentOutlined />}
              onClick={() => navigate('/admin?tab=org')}
            >
              組織設定（部門タグ）
            </Button>
            <Button
              icon={<BellOutlined />}
              onClick={() => navigate('/admin?tab=alert')}
            >
              アラート設定
            </Button>
          </Space>
        </Card>
      )}
    </div>
  )
}
