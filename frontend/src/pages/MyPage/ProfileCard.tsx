import { useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { EditOutlined, UserOutlined } from '@ant-design/icons'
import { useMyProfile, useUpdateMyProfile } from '../../hooks/useMyPage'

const ROLE_LABELS: Record<string, string> = {
  member: 'メンバー',
  leader: 'リーダー',
  manager: 'マネージャー',
  admin: '管理者',
}

const ROLE_COLORS: Record<string, string> = {
  member: 'default',
  leader: 'blue',
  manager: 'orange',
  admin: 'red',
}

export default function ProfileCard() {
  const { data: profile, isLoading } = useMyProfile()
  const updateProfile = useUpdateMyProfile()
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  if (isLoading) return <Card><Spin /></Card>
  if (!profile) return <Card><Typography.Text type="secondary">プロフィールが見つかりません</Typography.Text></Card>

  const handleOpen = () => {
    form.setFieldsValue({
      display_name: profile.display_name,
      capacity_hours_per_day: profile.capacity_hours_per_day,
      department_tags: profile.department_tags,
    })
    setOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    try {
      await updateProfile.mutateAsync(values)
      void message.success('プロフィールを更新しました')
      setOpen(false)
    } catch {
      void message.error('更新に失敗しました')
    }
  }

  return (
    <>
      <Card
        title={
          <Space>
            <UserOutlined />
            プロフィール
          </Space>
        }
        extra={
          <Button icon={<EditOutlined />} size="small" onClick={handleOpen}>
            編集
          </Button>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Typography.Title level={4} style={{ margin: 0 }}>
            {profile.display_name}
          </Typography.Title>
          <Typography.Text type="secondary">{profile.email ?? '—'}</Typography.Text>
          <Space wrap>
            <Tag color={ROLE_COLORS[profile.role] ?? 'default'}>
              {ROLE_LABELS[profile.role] ?? profile.role}
            </Tag>
            {profile.department_tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </Space>
          <Typography.Text>
            1日稼働時間: <strong>{profile.capacity_hours_per_day}h</strong>
          </Typography.Text>
        </Space>
      </Card>

      <Modal
        title="プロフィールを編集"
        open={open}
        onOk={handleSave}
        onCancel={() => setOpen(false)}
        confirmLoading={updateProfile.isPending}
        okText="保存"
        cancelText="キャンセル"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="表示名"
            name="display_name"
            rules={[{ required: true, message: '表示名を入力してください' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="1日稼働時間（時間）" name="capacity_hours_per_day">
            <InputNumber min={1} max={24} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="部門タグ" name="department_tags">
            <Select mode="tags" placeholder="タグを入力して Enter" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
