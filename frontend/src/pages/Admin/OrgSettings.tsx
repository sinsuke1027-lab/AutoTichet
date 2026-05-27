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
import { EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useAdminTags, useDeleteTag, useRenameTag } from '../../hooks/useAdminTags'
import { useAdminUsers } from '../../hooks/useAdminUsers'

export default function OrgSettings() {
  const { data: tags = [], isLoading } = useAdminTags()
  const { data: users = [] } = useAdminUsers()
  const renameTag = useRenameTag()
  const deleteTag = useDeleteTag()

  const [editingTag, setEditingTag] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const userCountByTag = Object.fromEntries(
    tags.map((tag) => [tag, users.filter((u) => u.department_tags.includes(tag)).length]),
  )

  const handleRename = async () => {
    if (!editingTag || !editValue.trim()) return
    try {
      await renameTag.mutateAsync({ tag: editingTag, newName: editValue.trim() })
      void message.success(`"${editingTag}" → "${editValue.trim()}" に変更しました`)
      setEditingTag(null)
    } catch {
      void message.error('名前変更に失敗しました')
    }
  }

  const columns = [
    {
      title: '部門タグ',
      dataIndex: 'tag',
      key: 'tag',
      render: (tag: string) => <strong>{tag}</strong>,
    },
    {
      title: '対象ユーザー数',
      key: 'count',
      render: (_: unknown, record: { tag: string }) => `${userCountByTag[record.tag] ?? 0} 名`,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: { tag: string }) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingTag(record.tag)
              setEditValue(record.tag)
            }}
          >
            名前変更
          </Button>
          <Popconfirm
            title={`"${record.tag}" を削除しますか？`}
            description={`${userCountByTag[record.tag] ?? 0} 名のユーザーからこのタグが削除されます。`}
            onConfirm={() => void deleteTag.mutateAsync(record.tag)}
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
      <div>
        <Typography.Title level={5} style={{ margin: 0 }}>
          部門タグ一元管理
        </Typography.Title>
        <Typography.Text type="secondary">
          システム内で使用中の部門タグを一覧・変更・削除できます。
          新しいタグはユーザー管理タブでユーザーを編集して追加してください。
        </Typography.Text>
      </div>

      <Card>
        <Table
          rowKey="tag"
          loading={isLoading}
          dataSource={tags.map((t) => ({ tag: t }))}
          columns={columns}
          pagination={false}
          size="small"
        />
      </Card>

      <Modal
        title="タグ名変更"
        open={!!editingTag}
        onOk={() => void handleRename()}
        onCancel={() => setEditingTag(null)}
        confirmLoading={renameTag.isPending}
        okText="変更"
        cancelText="キャンセル"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text>変更前: {editingTag}</Typography.Text>
          <Input
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onPressEnter={() => void handleRename()}
            placeholder="新しいタグ名"
          />
        </Space>
      </Modal>
    </Space>
  )
}
