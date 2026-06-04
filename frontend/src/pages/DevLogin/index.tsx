import { useEffect, useState } from 'react'
import { Alert, Badge, Card, Col, Row, Spin, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/useAuthStore'

export const DEV_USER_KEY = 'autoticket_dev_user'

interface DevUser {
  user_id: string
  display_name: string
  email: string | null
  role: string
  department_tags: string[]
  capacity_hours_per_day: number
}

const ROLE_COLOR: Record<string, string> = {
  admin: '#f5222d',
  manager: '#fa8c16',
  leader: '#1677ff',
  member: '#52c41a',
}

const DEPT_LABEL: Record<string, string> = {
  general_affairs: '総務',
  human_resources: '人事',
}

export default function DevLogin() {
  const [users, setUsers] = useState<DevUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const setUser = useAuthStore((s) => s.setUser)
  const navigate = useNavigate()

  const API_BASE = import.meta.env.VITE_API_URL ?? ''

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/dev/users`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<DevUser[]>
      })
      .then(setUsers)
      .catch(() => setError('ユーザー一覧の取得に失敗しました。バックエンドが起動しているか確認してください。'))
      .finally(() => setLoading(false))
  }, [])

  function login(u: DevUser) {
    const devUser = {
      userId: u.user_id,
      displayName: u.display_name,
      email: u.email ?? `${u.user_id}@dev.example.com`,
      role: u.role,
      departmentTags: u.department_tags,
    }
    sessionStorage.setItem(DEV_USER_KEY, JSON.stringify(devUser))
    setUser({ userId: devUser.userId, displayName: devUser.displayName, email: devUser.email, roles: [devUser.role], departmentTags: devUser.departmentTags })
    navigate('/')
  }

  return (
    <div style={{ maxWidth: 720, margin: '60px auto', padding: '0 24px' }}>
      <Typography.Title level={3} style={{ marginBottom: 4 }}>
        開発用ログイン
      </Typography.Title>
      <Typography.Text type="warning" style={{ display: 'block', marginBottom: 24 }}>
        VITE_DEV_BYPASS_AUTH=true — ログインしたいユーザーを選択してください
      </Typography.Text>

      {loading && <Spin size="large" style={{ display: 'block', textAlign: 'center', marginTop: 48 }} />}
      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      <Row gutter={[16, 16]}>
        {users.map((u) => (
          <Col key={u.user_id} xs={24} sm={12} md={8}>
            <Card
              hoverable
              onClick={() => login(u)}
              styles={{ body: { padding: '16px 20px' } }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <Badge
                  count={u.role}
                  style={{ backgroundColor: ROLE_COLOR[u.role] ?? '#888', fontSize: 11 }}
                />
              </div>
              <Typography.Text strong style={{ fontSize: 15 }}>
                {u.display_name}
              </Typography.Text>
              <div style={{ marginTop: 4, color: '#888', fontSize: 12 }}>
                {u.department_tags.map((t) => DEPT_LABEL[t] ?? t).join(' / ') || '—'}
              </div>
              <div style={{ marginTop: 2, color: '#aaa', fontSize: 11 }}>
                {u.user_id}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}
