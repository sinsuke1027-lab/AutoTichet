import {
  DeleteOutlined,
  EditOutlined,
  MinusCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Drawer,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Spin,
  Typography,
  message,
} from 'antd'
import { useState } from 'react'
import {
  useCreateTemplate,
  useDeleteTemplate,
  useTemplates,
  useUpdateTemplate,
} from '../../hooks/useTemplates'
import type { TemplateCreate, TemplateData, TemplateResponse } from '../../hooks/useTemplates'
import { useAuthStore } from '../../store/useAuthStore'

const { Title, Text } = Typography

const PRIORITY_OPTIONS = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '緊急', value: 'urgent' },
]

const VISIBILITY_OPTIONS = [
  { label: 'チーム共有', value: 'team' },
  { label: '全公開', value: 'all' },
  { label: '個人', value: 'private' },
]

function TemplateForm({
  initial,
  onFinish,
  loading,
}: {
  initial?: TemplateResponse
  onFinish: (values: TemplateCreate) => void
  loading: boolean
}) {
  const [form] = Form.useForm()

  const handleFinish = (values: Record<string, unknown>) => {
    const subtasks = (values.subtasks as Array<Record<string, unknown>> | undefined) ?? []
    const templateData: TemplateData = {
      title: values.td_title as string,
      description: (values.td_description as string | undefined) ?? null,
      priority: (values.td_priority as string | undefined) ?? 'medium',
      visibility: (values.td_visibility as string | undefined) ?? 'team',
      tags: [],
      estimated_hours: (values.td_estimated_hours as number | undefined) ?? null,
      due_date_offset_days: (values.td_due_date_offset_days as number | undefined) ?? 0,
      subtasks: subtasks.map((s) => ({
        title: s.title as string,
        priority: (s.priority as string | undefined) ?? 'medium',
        due_date_offset_days: (s.due_date_offset_days as number | undefined) ?? 0,
      })),
    }
    onFinish({
      name: values.name as string,
      description: (values.description as string | undefined) ?? null,
      template_data: templateData,
    })
  }

  const initialValues = initial
    ? {
        name: initial.name,
        description: initial.description,
        td_title: initial.template_data.title,
        td_description: initial.template_data.description,
        td_priority: initial.template_data.priority ?? 'medium',
        td_visibility: initial.template_data.visibility ?? 'team',
        td_estimated_hours: initial.template_data.estimated_hours,
        td_due_date_offset_days: initial.template_data.due_date_offset_days ?? 0,
        subtasks: initial.template_data.subtasks ?? [],
      }
    : { td_priority: 'medium', td_visibility: 'team', td_due_date_offset_days: 0 }

  return (
    <Form form={form} layout="vertical" initialValues={initialValues} onFinish={handleFinish}>
      <Form.Item name="name" label="テンプレート名" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="description" label="テンプレートの説明">
        <Input.TextArea rows={2} />
      </Form.Item>

      <Title level={5}>タスク本体</Title>
      <Form.Item name="td_title" label="タイトル" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="td_description" label="説明">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Space wrap>
        <Form.Item name="td_priority" label="優先度">
          <Select options={PRIORITY_OPTIONS} style={{ width: 100 }} />
        </Form.Item>
        <Form.Item name="td_visibility" label="公開範囲">
          <Select options={VISIBILITY_OPTIONS} style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="td_estimated_hours" label="予定工数(h)">
          <InputNumber min={0} step={0.5} style={{ width: 90 }} />
        </Form.Item>
        <Form.Item name="td_due_date_offset_days" label="期限(基準日+日)">
          <InputNumber min={0} style={{ width: 100 }} />
        </Form.Item>
      </Space>

      <Title level={5}>サブタスク</Title>
      <Form.List name="subtasks">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name }) => (
              <Space key={key} align="baseline" wrap>
                <Form.Item name={[name, 'title']} rules={[{ required: true, message: '必須' }]}>
                  <Input placeholder="サブタスク名" style={{ width: 200 }} />
                </Form.Item>
                <Form.Item name={[name, 'priority']}>
                  <Select options={PRIORITY_OPTIONS} style={{ width: 90 }} placeholder="優先度" />
                </Form.Item>
                <Form.Item name={[name, 'due_date_offset_days']}>
                  <InputNumber min={0} placeholder="期限+日" style={{ width: 80 }} />
                </Form.Item>
                <MinusCircleOutlined onClick={() => remove(name)} style={{ color: 'red' }} />
              </Space>
            ))}
            <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
              サブタスクを追加
            </Button>
          </>
        )}
      </Form.List>

      <div style={{ marginTop: 16 }}>
        <Button type="primary" htmlType="submit" loading={loading}>
          保存
        </Button>
      </div>
    </Form>
  )
}

export default function TemplatesPage() {
  const { data: templates = [], isLoading } = useTemplates()
  const createTemplate = useCreateTemplate()
  const deleteTemplate = useDeleteTemplate()
  const userId = useAuthStore((s) => s.userId)
  const roles = useAuthStore((s) => s.roles)
  const isAdmin = roles.includes('admin')

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<TemplateResponse | undefined>()

  const updateTemplate = useUpdateTemplate(editTarget?.id ?? '')

  const handleCreate = async (values: TemplateCreate) => {
    try {
      await createTemplate.mutateAsync(values)
      setDrawerOpen(false)
      void message.success('テンプレートを作成しました')
    } catch {
      void message.error('作成に失敗しました')
    }
  }

  const handleUpdate = async (values: TemplateCreate) => {
    try {
      await updateTemplate.mutateAsync(values)
      setDrawerOpen(false)
      setEditTarget(undefined)
      void message.success('テンプレートを更新しました')
    } catch {
      void message.error('更新に失敗しました')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteTemplate.mutateAsync(id)
      void message.success('テンプレートを削除しました')
    } catch {
      void message.error('削除に失敗しました')
    }
  }

  if (isLoading) return <Spin />

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Title level={3} style={{ margin: 0 }}>
          テンプレート
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditTarget(undefined)
            setDrawerOpen(true)
          }}
        >
          新規テンプレート
        </Button>
      </Space>

      {templates.length === 0 && (
        <Text type="secondary">テンプレートがありません。「新規テンプレート」から作成してください。</Text>
      )}

      {templates.map((t) => {
        const canEdit = t.created_by === userId || isAdmin
        return (
          <Card
            key={t.id}
            size="small"
            title={t.name}
            extra={
              canEdit && (
                <Space>
                  <Button
                    icon={<EditOutlined />}
                    size="small"
                    onClick={() => {
                      setEditTarget(t)
                      setDrawerOpen(true)
                    }}
                  />
                  <Popconfirm
                    title="このテンプレートを削除しますか？"
                    onConfirm={() => void handleDelete(t.id)}
                    okText="削除"
                    okButtonProps={{ danger: true }}
                    cancelText="キャンセル"
                  >
                    <Button icon={<DeleteOutlined />} size="small" danger />
                  </Popconfirm>
                </Space>
              )
            }
          >
            {t.description && <Text type="secondary">{t.description}</Text>}
            <div style={{ marginTop: 4 }}>
              <Text>タスク: {t.template_data.title}</Text>
              {(t.template_data.subtasks?.length ?? 0) > 0 && (
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  （サブタスク {t.template_data.subtasks?.length} 件）
                </Text>
              )}
            </div>
          </Card>
        )
      })}

      <Drawer
        title={editTarget ? 'テンプレートを編集' : 'テンプレートを作成'}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setEditTarget(undefined)
        }}
        width={560}
        destroyOnClose
      >
        <TemplateForm
          initial={editTarget}
          onFinish={editTarget ? handleUpdate : handleCreate}
          loading={createTemplate.isPending || updateTemplate.isPending}
        />
      </Drawer>
    </Space>
  )
}
