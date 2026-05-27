import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Tabs, Typography } from 'antd'
import { UserOutlined, ApartmentOutlined, BellOutlined } from '@ant-design/icons'
import { useAuthStore } from '../../store/useAuthStore'
import AdminUsersContent from './Users'
import OrgSettings from './OrgSettings'
import AlertSettings from './AlertSettings'

export default function AdminPage() {
  const roles = useAuthStore((s) => s.roles)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') ?? 'users'

  useEffect(() => {
    if (roles.length > 0 && !roles.includes('admin')) {
      navigate('/')
    }
  }, [roles, navigate])

  if (!roles.includes('admin')) return null

  return (
    <div>
      <Typography.Title level={3} style={{ margin: '0 0 16px' }}>
        管理設定
      </Typography.Title>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setSearchParams({ tab: key })}
        items={[
          {
            key: 'users',
            label: (
              <span>
                <UserOutlined />
                ユーザー管理
              </span>
            ),
            children: <AdminUsersContent />,
          },
          {
            key: 'org',
            label: (
              <span>
                <ApartmentOutlined />
                組織設定
              </span>
            ),
            children: <OrgSettings />,
          },
          {
            key: 'alert',
            label: (
              <span>
                <BellOutlined />
                アラート設定
              </span>
            ),
            children: <AlertSettings />,
          },
        ]}
      />
    </div>
  )
}
