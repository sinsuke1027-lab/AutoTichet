import { useState } from 'react'
import {
  Button,
  DatePicker,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Tooltip,
  Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { Milestone } from '../../lib/api'
import {
  useCreateMilestone,
  useDeleteMilestone,
  useMilestones,
  useToggleComplete,
  useUpdateMilestone,
} from '../../hooks/useMilestones'

interface Props {
  projectId: string
}

function getMarkerColor(m: Milestone): string {
  if (m.completed) return '#52c41a'
  return dayjs(m.due_date).isBefore(dayjs().startOf('day')) ? '#ff4d4f' : '#1677ff'
}

function getDaysLabel(m: Milestone): string {
  if (m.completed) return '完了済み'
  const diff = dayjs(m.due_date).diff(dayjs().startOf('day'), 'day')
  if (diff < 0) return `期限超過 ${Math.abs(diff)} 日`
  if (diff === 0) return '今日が期限'
  return `残 ${diff} 日`
}

export default function MilestoneTimeline({ projectId }: Props) {
  const { data: milestones = [] } = useMilestones(projectId)
  const createMilestone = useCreateMilestone(projectId)
  const updateMilestone = useUpdateMilestone(projectId)
  const toggleComplete = useToggleComplete(projectId)
  const deleteMilestone = useDeleteMilestone(projectId)

  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Milestone | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const handleCreate = async () => {
    const values = await createForm.validateFields()
    try {
      await createMilestone.mutateAsync({
        title: values.title as string,
        due_date: (values.due_date as dayjs.Dayjs).format('YYYY-MM-DD'),
      })
      createForm.resetFields()
      setCreateOpen(false)
    } catch {
      void message.error('マイルストーンの作成に失敗しました')
    }
  }

  const handleEdit = async () => {
    if (!editTarget) return
    const values = await editForm.validateFields()
    try {
      await updateMilestone.mutateAsync({
        milestoneId: editTarget.id,
        body: {
          title: values.title as string,
          due_date: (values.due_date as dayjs.Dayjs).format('YYYY-MM-DD'),
        },
      })
      setEditTarget(null)
    } catch {
      void message.error('マイルストーンの更新に失敗しました')
    }
  }

  const handleToggle = async (id: string) => {
    try {
      await toggleComplete.mutateAsync(id)
    } catch {
      void message.error('完了状態の変更に失敗しました')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteMilestone.mutateAsync(id)
      setEditTarget(null)
    } catch {
      void message.error('マイルストーンの削除に失敗しました')
    }
  }

  const openEdit = (m: Milestone) => {
    setEditTarget(m)
    editForm.setFieldsValue({ title: m.title, due_date: dayjs(m.due_date) })
  }

  // タイムライン軸の範囲計算
  const sorted = [...milestones].sort((a, b) => a.due_date.localeCompare(b.due_date))
  const rangeStart =
    sorted.length > 0
      ? dayjs(sorted[0].due_date).subtract(7, 'day')
      : dayjs().subtract(7, 'day')
  const rangeEnd =
    sorted.length > 0
      ? dayjs(sorted[sorted.length - 1].due_date).add(7, 'day')
      : dayjs().add(7, 'day')
  const rangeDays = rangeEnd.diff(rangeStart, 'day') || 1

  const getLeft = (dueDate: string) =>
    `${(dayjs(dueDate).diff(rangeStart, 'day') / rangeDays) * 100}%`

  return (
    <div style={{ marginBottom: 24 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <Typography.Text strong>マイルストーン</Typography.Text>
        <Button icon={<PlusOutlined />} size="small" onClick={() => setCreateOpen(true)}>
          追加
        </Button>
      </div>

      {milestones.length === 0 ? (
        <Typography.Text type="secondary">マイルストーンはまだありません</Typography.Text>
      ) : (
        <div
          style={{ position: 'relative', height: 48, background: '#f5f5f5', borderRadius: 4 }}
        >
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              right: 0,
              height: 2,
              background: '#d9d9d9',
            }}
          />
          {milestones.map((m) => (
            <Tooltip
              key={m.id}
              title={
                <div>
                  <div>{m.title}</div>
                  <div>{m.due_date}</div>
                  <div>{getDaysLabel(m)}</div>
                </div>
              }
            >
              <div
                onClick={() => openEdit(m)}
                style={{
                  position: 'absolute',
                  left: getLeft(m.due_date),
                  top: '50%',
                  transform: 'translate(-50%, -50%) rotate(45deg)',
                  width: 16,
                  height: 16,
                  background: getMarkerColor(m),
                  cursor: 'pointer',
                  border: '2px solid white',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
                }}
              />
            </Tooltip>
          ))}
        </div>
      )}

      {/* 作成モーダル */}
      <Modal
        title="マイルストーン追加"
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => {
          setCreateOpen(false)
          createForm.resetFields()
        }}
        confirmLoading={createMilestone.isPending}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="due_date" label="期日" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 編集モーダル */}
      <Modal
        title="マイルストーン編集"
        open={!!editTarget}
        onOk={() => void handleEdit()}
        onCancel={() => setEditTarget(null)}
        confirmLoading={updateMilestone.isPending}
        footer={[
          <Popconfirm
            key="delete"
            title="このマイルストーンを削除しますか？"
            onConfirm={() => editTarget && void handleDelete(editTarget.id)}
          >
            <Button danger>削除</Button>
          </Popconfirm>,
          <Button
            key="toggle"
            onClick={() => editTarget && void handleToggle(editTarget.id)}
            loading={toggleComplete.isPending}
          >
            {editTarget?.completed ? '完了を解除' : '完了にする'}
          </Button>,
          <Button key="cancel" onClick={() => setEditTarget(null)}>
            キャンセル
          </Button>,
          <Button
            key="ok"
            type="primary"
            onClick={() => void handleEdit()}
            loading={updateMilestone.isPending}
          >
            保存
          </Button>,
        ]}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="due_date" label="期日" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
