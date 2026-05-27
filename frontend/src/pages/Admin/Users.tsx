import { useState } from 'react'
import {
  Button,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import {
  useAdminUsers,
  useCreateAdminUser,
  useDeleteAdminUser,
  useUpdateAdminUser,
} from '../../hooks/useAdminUsers'
import type { AdminUser } from '../../lib/api'

const ROLE_OPTIONS = [
  { label: 'メンバー', value: 'member' },
  { label: 'リーダー', value: 'leader' },
  { label: 'マネージャー', value: 'manager' },
  { label: '管理者', value: 'admin' },
]

export default function AdminUsers() {
  const { data: users = [], isLoading } = useAdminUsers()
  const createUser = useCreateAdminUser()
  const updateUser = useUpdateAdminUser()
  const deleteUser = useDeleteAdminUser()

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<AdminUser | null>(null)
  const [form] = Form.useForm()

  const existingTags = [...new Set(users.flatMap((u) => u.department_tags))]

  const handleOpen = (user?: AdminUser) => {
    setEditing(user ?? null)
    if (user) {
      form.setFieldsValue({
        display_name: user.display_name,
        email: user.email,
        role: user.role,
        department_tags: user.department_tags,
        capacity_hours_per_day: user.capacity_hours_per_day,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ role: 'member', department_tags: [], capacity_hours_per_day: 8.0 })
    }
    setOpen(true)
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await updateUser.mutateAsync({ userId: editing.user_id, body: values })
      } else {
        await createUser.mutateAsync(values as AdminUser & { user_id: string })
      }
      setOpen(false)
      form.resetFields()
    } catch {
      void message.error('操作に失敗しました')
    }
  }

  const columns = [
    { title: '氏名', dataIndex: 'display_name', key: 'display_name' },
    {
      title: 'メール',
      dataIndex: 'email',
      key: 'email',
      render: (v: string | null) => v ?? '—',
    },
    { title: 'ロール', dataIndex: 'role', key: 'role' },
    {
      title: '部門タグ',
      dataIndex: 'department_tags',
      key: 'department_tags',
      render: (tags: string[]) => tags.join(', ') || '—',
    },
    { title: '稼働時間/日', dataIndex: 'capacity_hours_per_day', key: 'cap' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AdminUser) => (
        <Space>
          <Button size="small" onClick={() => handleOpen(record)}>
            編集
          </Button>
          <Popconfirm
            title="このユーザーを削除しますか？"
            onConfirm={() => void deleteUser.mutateAsync(record.user_id)}
          >
            <Button size="small" danger>
              削除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={5} style={{ margin: 0 }}>
          ユーザー一覧
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpen()}>
          ユーザー追加
        </Button>
      </Space>

      <Table rowKey="user_id" loading={isLoading} dataSource={users} columns={columns} />

      <Modal
        title={editing ? 'ユーザー編集' : 'ユーザー追加'}
        open={open}
        onOk={() => void handleOk()}
        onCancel={() => {
          setOpen(false)
          form.resetFields()
        }}
        confirmLoading={createUser.isPending || updateUser.isPending}
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <>
              <Form.Item name="user_id" label="ユーザーID" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="display_name" label="氏名" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="email" label="メールアドレス">
                <Input />
              </Form.Item>
            </>
          )}
          {editing && (
            <Form.Item name="display_name" label="氏名" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          )}
          <Form.Item name="role" label="ロール">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="department_tags" label="部門タグ">
            <Select
              mode="tags"
              options={existingTags.map((t) => ({ label: t, value: t }))}
            />
          </Form.Item>
          <Form.Item name="capacity_hours_per_day" label="稼働時間/日">
            <InputNumber min={0} max={24} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
