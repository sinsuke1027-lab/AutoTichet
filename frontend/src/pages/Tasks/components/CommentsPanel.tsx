import { Avatar, Button, Input, List, Space, Typography } from 'antd'
import { useState } from 'react'
import { useComments, useCreateComment } from '../../../hooks/useTaskDetails'

interface Props {
  taskId: string
}

export default function CommentsPanel({ taskId }: Props) {
  const { data: comments = [] } = useComments(taskId)
  const createComment = useCreateComment(taskId)
  const [content, setContent] = useState('')

  const handleSubmit = async () => {
    if (!content.trim()) return
    await createComment.mutateAsync(content.trim())
    setContent('')
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <List
        dataSource={comments}
        renderItem={(c) => (
          <List.Item key={c.id}>
            <List.Item.Meta
              avatar={<Avatar>{c.author_id.slice(0, 1).toUpperCase()}</Avatar>}
              title={
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {new Date(c.created_at).toLocaleString('ja-JP')}
                </Typography.Text>
              }
              description={c.content}
            />
          </List.Item>
        )}
        locale={{ emptyText: 'コメントはまだありません' }}
      />
      <Input.TextArea
        rows={3}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="コメントを入力..."
      />
      <Button
        type="primary"
        onClick={handleSubmit}
        loading={createComment.isPending}
        disabled={!content.trim()}
      >
        送信
      </Button>
    </Space>
  )
}
