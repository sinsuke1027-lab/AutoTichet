import { useState } from 'react'
import {
  Button,
  Card,
  Input,
  message,
  Modal,
  Popconfirm,
  Space,
  Table,
  Typography,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  DepartmentTagResponse,
  useAdminTags,
  useCreateTag,
  useDeleteTag,
  useUpdateTag,
} from '../../hooks/useAdminTags'
import { useAdminUsers } from '../../hooks/useAdminUsers'

export default function OrgSettings() {
  const { data: tags = [], isLoading } = useAdminTags()
  const { data: users = [] } = useAdminUsers()
  const createTag = useCreateTag()
  const updateTag = useUpdateTag()
  const deleteTag = useDeleteTag()

  // 編集モーダル
  const [editingTag, setEditingTag] = useState<DepartmentTagResponse | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // 新規追加モーダル
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')

  const userCountByTag = Object.fromEntries(
    tags.map((t) => [t.name, users.filter((u) => u.department_tags.includes(t.name)).length]),
  )

  const handleUpdate = async () => {
    if (!editingTag || !editName.trim()) return
    try {
      await updateTag.mutateAsync({
        tag: editingTag.name,
        newName: editName.trim() !== editingTag.name ? editName.trim() : undefined,
        description: editDescription.trim() || null,
      })
      void message.success('タグを更新しました')
      setEditingTag(null)
    } catch {
      void message.error('更新に失敗しました')
    }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await createTag.mutateAsync({
        name: newName.trim(),
        description: newDescription.trim() || null,
      })
      void message.success(`"${newName.trim()}" を追加しました`)
      setCreateOpen(false)
      setNewName('')
      setNewDescription('')
    } catch {
      void message.error('タグの追加に失敗しました')
    }
  }

  const columns = [
    {
      title: '部門タグ',
      key: 'name',
      render: (_: unknown, record: DepartmentTagResponse) => <strong>{record.name}</strong>,
    },
    {
      title: '説明',
      key: 'description',
      render: (_: unknown, record: DepartmentTagResponse) =>
        record.description ? (
          record.description
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: '対象ユーザー数',
      key: 'count',
      render: (_: unknown, record: DepartmentTagResponse) =>
        `${userCountByTag[record.name] ?? 0} 名`,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: DepartmentTagResponse) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingTag(record)
              setEditName(record.name)
              setEditDescription(record.description ?? '')
            }}
          >
            編集
          </Button>
          <Popconfirm
            title={`"${record.name}" を削除しますか？`}
            description={`${userCountByTag[record.name] ?? 0} 名のユーザーからこのタグが削除されます。`}
            onConfirm={() => void deleteTag.mutateAsync(record.name)}
            okText="削除"
            cancelText="キャンセル"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              削除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            部門タグ一元管理
          </Typography.Title>
          <Typography.Text type="secondary">
            システム内で使用する部門タグを管理します。タグを追加して各ユーザーに割り当ててください。
          </Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          タグを追加
        </Button>
      </div>

      <Card>
        <Table
          rowKey="name"
          loading={isLoading}
          dataSource={tags}
          columns={columns}
          pagination={false}
          size="small"
        />
      </Card>

      {/* 編集モーダル */}
      <Modal
        title="タグを編集"
        open={!!editingTag}
        onOk={() => void handleUpdate()}
        onCancel={() => setEditingTag(null)}
        confirmLoading={updateTag.isPending}
        okText="保存"
        cancelText="キャンセル"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>タグ名</Typography.Text>
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onPressEnter={() => void handleUpdate()}
              placeholder="タグ名"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text strong>説明</Typography.Text>
            <Input.TextArea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="このタグの説明（省略可）"
              rows={2}
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      </Modal>

      {/* 新規追加モーダル */}
      <Modal
        title="タグを追加"
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => {
          setCreateOpen(false)
          setNewName('')
          setNewDescription('')
        }}
        confirmLoading={createTag.isPending}
        okText="追加"
        cancelText="キャンセル"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>タグ名 *</Typography.Text>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onPressEnter={() => void handleCreate()}
              placeholder="例: 営業部"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text strong>説明</Typography.Text>
            <Input.TextArea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="このタグの説明（省略可）"
              rows={2}
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      </Modal>
    </Space>
  )
}
