import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, List, Modal, Spin, Tag, Typography } from 'antd'
import { CommentOutlined, FileTextOutlined } from '@ant-design/icons'
import { useSearch } from '../hooks/useSearch'
import { useSearchStore } from '../store/useSearchStore'
import type { SearchResultItem } from '../lib/api'

const MATCH_TYPE_LABEL: Record<SearchResultItem['match_type'], string> = {
  title: 'タイトル',
  description: '説明',
  comment: 'コメント',
}

const MATCH_TYPE_COLOR: Record<SearchResultItem['match_type'], string> = {
  title: 'blue',
  description: 'cyan',
  comment: 'green',
}

export default function CommandPalette() {
  const { open, setOpen } = useSearchStore()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const { data, isFetching } = useSearch(input)

  // Ctrl+K / Cmd+K でトグル
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(true)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [setOpen])

  const handleClose = () => {
    setOpen(false)
    setInput('')
  }

  const handleSelect = (item: SearchResultItem) => {
    navigate(`/projects/${item.project_id}`)
    handleClose()
  }

  return (
    <Modal
      open={open}
      onCancel={handleClose}
      footer={null}
      width={600}
      style={{ top: 100 }}
      styles={{ body: { padding: 0 } }}
      title={null}
      closable={false}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Input
          autoFocus
          size="large"
          placeholder="タスク・コメントを検索… (Esc で閉じる)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          suffix={isFetching ? <Spin size="small" /> : null}
          bordered={false}
          style={{ fontSize: 16 }}
        />
      </div>

      {input.length >= 2 && (
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          {data && data.items.length > 0 ? (
            <List
              dataSource={data.items}
              renderItem={(item) => (
                <List.Item
                  onClick={() => handleSelect(item)}
                  style={{ padding: '10px 16px', cursor: 'pointer' }}
                >
                  <List.Item.Meta
                    avatar={
                      item.match_type === 'comment' ? (
                        <CommentOutlined style={{ color: '#52c41a', fontSize: 16, marginTop: 4 }} />
                      ) : (
                        <FileTextOutlined style={{ color: '#1677ff', fontSize: 16, marginTop: 4 }} />
                      )
                    }
                    title={
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Typography.Text strong>{item.title}</Typography.Text>
                        <Tag color={MATCH_TYPE_COLOR[item.match_type]} style={{ margin: 0 }}>
                          {MATCH_TYPE_LABEL[item.match_type]}
                        </Tag>
                      </div>
                    }
                    description={
                      <div>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {item.project_name}
                        </Typography.Text>
                        <br />
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {item.snippet}
                        </Typography.Text>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          ) : !isFetching ? (
            <div style={{ padding: '24px 16px', textAlign: 'center' }}>
              <Typography.Text type="secondary">一致するタスクが見つかりません</Typography.Text>
            </div>
          ) : null}
        </div>
      )}
    </Modal>
  )
}
