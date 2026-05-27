import { useState } from 'react'
import { Badge, Button, Popover, Space, Tag, Typography } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useDailyWorkload } from '../hooks/useDailyWorkload'
import { useSettingsStore } from '../store/useSettingsStore'

export default function WorkloadAlertBadge() {
  const [open, setOpen] = useState(false)
  const { data = [] } = useDailyWorkload()
  const thresholdPct = useSettingsStore((s) => s.workloadThresholdPct)
  const threshold = thresholdPct / 100

  const overloadDays = data.filter((d) => d.total_hours > d.capacity_hours * threshold)
  const capacityHours = data[0]?.capacity_hours ?? 8

  const chartData = data.map((d) => ({
    date: d.date.slice(5).replace('-', '/'),
    total: d.total_hours,
    overload: d.overload,
  }))

  const content = (
    <div style={{ width: 320 }}>
      <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
        今後7日間のワークロード
      </Typography.Text>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis unit="h" tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: unknown) => [`${String(v)}h`, '工数']} />
          <ReferenceLine
            y={capacityHours}
            stroke="#faad14"
            strokeDasharray="4 2"
            label={{ value: 'cap', fontSize: 10, fill: '#faad14' }}
          />
          <Bar dataKey="total" isAnimationActive={false}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.overload ? '#ff4d4f' : '#1677ff'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {overloadDays.length > 0 && (
        <Space wrap style={{ marginTop: 8 }}>
          {overloadDays.map((d) => (
            <Tag key={d.date} color="red">
              {d.date.slice(5).replace('-', '/')} 超過: {d.total_hours}h / {d.capacity_hours}h
            </Tag>
          ))}
        </Space>
      )}
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Link to="/workload" onClick={() => setOpen(false)}>
          詳細を見る →
        </Link>
      </div>
    </div>
  )

  return (
    <Popover
      content={content}
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
    >
      <Badge count={overloadDays.length} showZero={false}>
        <Button
          type="text"
          icon={<BellOutlined style={{ fontSize: 18, color: 'rgba(255,255,255,0.85)' }} />}
        />
      </Badge>
    </Popover>
  )
}
