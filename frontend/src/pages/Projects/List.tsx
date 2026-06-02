import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Col,
  Dropdown,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd'
import { EllipsisOutlined, PlusOutlined } from '@ant-design/icons'
import {
  useProjects,
  useCreateProject,
  useArchiveProject,
  useUnarchiveProject,
} from '../../hooks/useProjects'

export default function ProjectList() {
  const navigate = useNavigate()
  const [includeArchived, setIncludeArchived] = useState(false)
  const { data: projects = [], isLoading } = useProjects(includeArchived)
  const createProject = useCreateProject()
  const archiveProject = useArchiveProject()
  const unarchiveProject = useUnarchiveProject()
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await createProject.mutateAsync(values)
      form.resetFields()
      setOpen(false)
    } catch {
      // validation error — do nothing
    }
  }

  const handleArchive = async (id: string) => {
    try {
      await archiveProject.mutateAsync(id)
      void message.success('アーカイブしました')
    } catch {
      void message.error('アーカイブに失敗しました')
    }
  }

  const handleUnarchive = async (id: string) => {
    try {
      await unarchiveProject.mutateAsync(id)
      void message.success('アーカイブを解除しました')
    } catch {
      void message.error('アーカイブ解除に失敗しました')
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          プロジェクト一覧
        </Typography.Title>
        <Space>
          <Switch checked={includeArchived} onChange={setIncludeArchived} />
          <Typography.Text>アーカイブ済みを表示</Typography.Text>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            プロジェクト作成
          </Button>
        </Space>
      </Space>

      {isLoading ? (
        <Typography.Text>読み込み中...</Typography.Text>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((p) => {
            const isArchived = p.status === 'archived'
            return (
              <Col key={p.id} xs={24} sm={12} lg={8}>
                <Card
                  hoverable={!isArchived}
                  onClick={() => !isArchived && navigate(`/projects/${p.id}`)}
                  style={isArchived ? { opacity: 0.5, cursor: 'default' } : undefined}
                  title={p.name}
                  extra={
                    <Space>
                      <Tag color={isArchived ? 'default' : 'green'}>
                        {isArchived ? 'アーカイブ済み' : 'active'}
                      </Tag>
                      <Dropdown
                        menu={{
                          items: isArchived
                            ? [{ key: 'unarchive', label: 'アーカイブ解除' }]
                            : [{ key: 'archive', label: 'アーカイブ' }],
                          onClick: ({ key, domEvent }) => {
                            domEvent.stopPropagation()
                            if (key === 'archive') void handleArchive(p.id)
                            else void handleUnarchive(p.id)
                          },
                        }}
                        trigger={['click']}
                      >
                        <Button
                          type="text"
                          icon={<EllipsisOutlined />}
                          size="small"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Dropdown>
                    </Space>
                  }
                >
                  <Typography.Text type="secondary">
                    {p.description ?? '説明なし'}
                  </Typography.Text>
                </Card>
              </Col>
            )
          })}
          {projects.length === 0 && (
            <Col span={24}>
              <Typography.Text type="secondary">プロジェクトがありません</Typography.Text>
            </Col>
          )}
        </Row>
      )}

      <Modal
        title="プロジェクト作成"
        open={open}
        onOk={handleCreate}
        onCancel={() => {
          setOpen(false)
          form.resetFields()
        }}
        confirmLoading={createProject.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="プロジェクト名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="説明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
