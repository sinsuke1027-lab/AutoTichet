import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Col, Form, Input, Modal, Row, Space, Tag, Typography } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useProjects, useCreateProject } from '../../hooks/useProjects'

export default function ProjectList() {
  const navigate = useNavigate()
  const { data: projects = [], isLoading } = useProjects()
  const createProject = useCreateProject()
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

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          プロジェクト一覧
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          プロジェクト作成
        </Button>
      </Space>

      {isLoading ? (
        <Typography.Text>読み込み中...</Typography.Text>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((p) => (
            <Col key={p.id} xs={24} sm={12} lg={8}>
              <Card
                hoverable
                onClick={() => navigate(`/projects/${p.id}`)}
                title={p.name}
                extra={
                  <Tag color={p.status === 'active' ? 'green' : 'default'}>{p.status}</Tag>
                }
              >
                <Typography.Text type="secondary">
                  {p.description ?? '説明なし'}
                </Typography.Text>
              </Card>
            </Col>
          ))}
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
