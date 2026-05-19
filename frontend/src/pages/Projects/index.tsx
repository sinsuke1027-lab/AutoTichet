import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Collapse,
  Form,
  Input,
  message,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useProjects } from '../../hooks/useProjects'
import { useSections, useCreateSection, useDeleteSection } from '../../hooks/useSections'
import { useTasks, useCreateTask } from '../../hooks/useTasks'
import type { Section, Task } from '../../lib/api'

export default function ProjectDetail() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: projects = [] } = useProjects()
  const project = projects.find((p) => p.id === projectId)
  const { data: sections = [] } = useSections(projectId)
  const { data: taskList } = useTasks({ project_id: projectId })
  const createSection = useCreateSection(projectId ?? '')
  const deleteSection = useDeleteSection(projectId ?? '')
  const createTask = useCreateTask()
  const [sectionModalOpen, setSectionModalOpen] = useState(false)
  const [taskModalSection, setTaskModalSection] = useState<string | null | undefined>(undefined)
  const [sectionForm] = Form.useForm()
  const [taskForm] = Form.useForm()

  const allTasks = taskList?.items ?? []

  const getTasksForSection = (sectionId: string | null) =>
    allTasks.filter((t) => (sectionId ? t.section_id === sectionId : !t.section_id))

  const handleCreateSection = async () => {
    const values = await sectionForm.validateFields()
    await createSection.mutateAsync({ name: values.name as string, order_index: sections.length })
    sectionForm.resetFields()
    setSectionModalOpen(false)
  }

  const handleDeleteSection = (section: Section) => {
    Modal.confirm({
      title: `「${section.name}」を削除しますか？`,
      content: 'タスクのセクション割り当ては解除されます',
      onOk: () => deleteSection.mutateAsync(section.id),
    })
  }

  const handleCreateTask = async () => {
    const values = await taskForm.validateFields()
    try {
      await createTask.mutateAsync({
        ...(values as { title: string }),
        project_id: projectId,
        section_id: taskModalSection ?? undefined,
      })
      taskForm.resetFields()
      setTaskModalSection(undefined)
    } catch {
      void message.error('タスクの作成に失敗しました')
    }
  }

  const taskColumns = [
    {
      title: 'タスク',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, rec: Task) => (
        <a onClick={() => navigate(`/tasks/${rec.id}`)}>{title}</a>
      ),
    },
    {
      title: '担当者',
      dataIndex: 'assignee_id',
      key: 'assignee_id',
      render: (id: string | null) => id ?? '—',
    },
    {
      title: '期限',
      dataIndex: 'due_date',
      key: 'due_date',
      render: (d: string | null) => d ?? '—',
    },
    {
      title: '優先度',
      dataIndex: 'priority',
      key: 'priority',
      render: (p: string) => <Tag>{p}</Tag>,
    },
  ]

  const sectionItems = [
    ...sections.map((sec) => ({
      key: sec.id,
      label: (
        <Space>
          <span>{sec.name}</span>
          <Button
            size="small"
            onClick={(e) => {
              e.stopPropagation()
              handleDeleteSection(sec)
            }}
          >
            削除
          </Button>
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Table
            rowKey="id"
            size="small"
            dataSource={getTasksForSection(sec.id)}
            columns={taskColumns}
            pagination={false}
          />
          <Button
            icon={<PlusOutlined />}
            size="small"
            onClick={() => setTaskModalSection(sec.id)}
          >
            タスクを追加
          </Button>
        </Space>
      ),
    })),
    {
      key: 'no-section',
      label: 'セクションなし',
      children: (
        <Table
          rowKey="id"
          size="small"
          dataSource={getTasksForSection(null)}
          columns={taskColumns}
          pagination={false}
        />
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {project?.name ?? 'プロジェクト'}
        </Typography.Title>
        <Button icon={<PlusOutlined />} onClick={() => setSectionModalOpen(true)}>
          セクション追加
        </Button>
      </Space>

      <Collapse items={sectionItems} defaultActiveKey={sections.map((s) => s.id)} />

      <Modal
        title="セクション追加"
        open={sectionModalOpen}
        onOk={handleCreateSection}
        onCancel={() => {
          setSectionModalOpen(false)
          sectionForm.resetFields()
        }}
        confirmLoading={createSection.isPending}
      >
        <Form form={sectionForm} layout="vertical">
          <Form.Item name="name" label="セクション名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="タスクを追加"
        open={taskModalSection !== undefined}
        onOk={handleCreateTask}
        onCancel={() => {
          setTaskModalSection(undefined)
          taskForm.resetFields()
        }}
        confirmLoading={createTask.isPending}
      >
        <Form form={taskForm} layout="vertical">
          <Form.Item name="title" label="タスク名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
