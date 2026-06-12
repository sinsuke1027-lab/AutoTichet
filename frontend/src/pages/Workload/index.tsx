import { Typography, Card, Progress, Tag, Space, Alert } from 'antd'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useWorkload } from '../../hooks/useDashboard'
import { useSettingsStore } from '../../store/useSettingsStore'

export default function Workload() {
  const { data: workload, isLoading } = useWorkload()
  const thresholdPct = useSettingsStore((s) => s.workloadThresholdPct)
  const threshold = thresholdPct / 100

  const chartData = (workload ?? []).map((item) => ({
    name: item.display_name,
    予定工数: item.estimated_hours,
    キャパシティ: item.capacity_hours,
    閾値: Math.round(item.capacity_hours * threshold * 10) / 10,
  }))

  const overloadUsers = (workload ?? []).filter(
    (u) => u.estimated_hours > u.capacity_hours * threshold,
  )

  return (
    <div>
      <Typography.Title level={4}>ワークロード（今後7日間）</Typography.Title>

      {overloadUsers.length > 0 && (
        <Alert
          type="warning"
          message={`${overloadUsers.map((u) => u.display_name).join('、')} が工数超過です`}
          style={{ marginBottom: 16 }}
        />
      )}

      <Card
        loading={isLoading}
        extra={
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            アラート閾値: {thresholdPct}%
          </Typography.Text>
        }
      >
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis unit="h" />
            <Tooltip />
            <Bar dataKey="予定工数" fill="#8884d8" />
            <Bar dataKey="キャパシティ" fill="#82ca9d" />
            {/* 閾値はユーザーごとにキャパシティが異なるため per-bar で描画（issue #33） */}
            <Bar dataKey="閾値" fill="#faad14" />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Space direction="vertical" style={{ width: '100%', marginTop: 16 }} size={8}>
        {(workload ?? []).map((item) => {
          const isOver = item.estimated_hours > item.capacity_hours * threshold
          const pct = item.capacity_hours > 0
            ? Math.round((item.estimated_hours / item.capacity_hours) * 100)
            : 0
          return (
            <Card key={item.user_id} size="small">
              <Space>
                {isOver && <Tag color="red">超過</Tag>}
                <span>{item.display_name}</span>
                <Progress
                  percent={pct}
                  strokeColor={isOver ? '#ff4d4f' : '#52c41a'}
                  style={{ width: 200 }}
                />
                <span>
                  {item.estimated_hours}h / {item.capacity_hours}h
                </span>
              </Space>
            </Card>
          )
        })}
      </Space>
    </div>
  )
}
