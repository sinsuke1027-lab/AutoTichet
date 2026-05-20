import { useState } from 'react'
import { Button, Form, Input, Select, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/useAuthStore'

export const DEV_USER_KEY = 'autoticket_dev_user'

interface DevUserForm {
  displayName: string
  userId: string
  role: string
  departmentTags: string
}

export default function DevLogin() {
  const [loading, setLoading] = useState(false)
  const setUser = useAuthStore((s) => s.setUser)
  const navigate = useNavigate()

  function onFinish(values: DevUserForm) {
    setLoading(true)
    const devUser = {
      userId: values.userId,
      displayName: values.displayName,
      email: `${values.userId}@dev.example.com`,
      role: values.role,
      departmentTags: values.departmentTags
        ? values.departmentTags.split(',').map((s) => s.trim()).filter(Boolean)
        : [],
    }
    sessionStorage.setItem(DEV_USER_KEY, JSON.stringify(devUser))
    setUser({ userId: devUser.userId, displayName: devUser.displayName, email: devUser.email, roles: [devUser.role] })
    navigate('/')
  }

  return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: 24 }}>
      <Typography.Title level={3}>開発用ログイン</Typography.Title>
      <Typography.Text type="warning">
        このページは開発テスト専用です（VITE_DEV_BYPASS_AUTH=true）
      </Typography.Text>
      <Form
        layout="vertical"
        onFinish={onFinish}
        style={{ marginTop: 24 }}
        initialValues={{ role: 'member', userId: `dev-${Math.random().toString(36).slice(2, 8)}` }}
      >
        <Form.Item
          name="displayName"
          label="表示名"
          rules={[{ required: true, message: '表示名を入力してください' }]}
        >
          <Input placeholder="田中 太郎" />
        </Form.Item>
        <Form.Item name="userId" label="ユーザーID" rules={[{ required: true, message: 'ユーザーIDを入力してください' }]}>
          <Input placeholder="user-001" />
        </Form.Item>
        <Form.Item name="role" label="ロール">
          <Select
            options={[
              { value: 'member', label: 'Member' },
              { value: 'leader', label: 'Leader' },
              { value: 'manager', label: 'Manager' },
              { value: 'admin', label: 'Admin' },
            ]}
          />
        </Form.Item>
        <Form.Item name="departmentTags" label="部門タグ（カンマ区切り、省略可）">
          <Input placeholder="engineering, product" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            開発環境でログイン
          </Button>
        </Form.Item>
      </Form>
    </div>
  )
}
