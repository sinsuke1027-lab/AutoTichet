import { Card, Col, Row, Spin, Statistic } from 'antd'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useMyWeeklySummary } from '../../hooks/useMyPage'

export default function WeeklySummary() {
  const { data: summaries, isLoading } = useMyWeeklySummary()

  if (isLoading) return <Spin />
  if (!summaries || summaries.length === 0) return null

  const current = summaries[summaries.length - 1]
  const completionRate =
    current.task_count > 0
      ? Math.round((current.completed_count / current.task_count) * 100)
      : 0

  const chartData = summaries.map((s) => ({
    week: `${s.week_start.slice(5, 10).replace('-', '/')}週`,
    予定: s.planned_hours,
    実績: s.actual_hours,
  }))

  return (
    <Card title="今週のサマリー">
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Statistic title="今週タスク数" value={current.task_count} />
        </Col>
        <Col span={6}>
          <Statistic title="完了率" value={completionRate} suffix="%" />
        </Col>
        <Col span={6}>
          <Statistic title="予定工数" value={current.planned_hours} suffix="h" />
        </Col>
        <Col span={6}>
          <Statistic
            title="期限超過"
            value={current.overdue_count}
            valueStyle={{ color: current.overdue_count > 0 ? '#cf1322' : undefined }}
          />
        </Col>
      </Row>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={{ fontSize: 12 }} />
          <YAxis unit="h" tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => `${v}h`} />
          <Legend />
          <Bar dataKey="予定" fill="#1677ff" />
          <Bar dataKey="実績" fill="#52c41a" />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}
