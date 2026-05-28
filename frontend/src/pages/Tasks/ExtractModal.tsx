import { useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { EditOutlined, RiseOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useExtractTasks, useCreateTask } from '../../hooks/useTasks'
import { useUsers } from '../../hooks/useUsers'
import { useProjects } from '../../hooks/useProjects'
import type { ExtractedTask } from '../../lib/api'

const { Text, Title } = Typography
const { TextArea } = Input

const SOURCE_OPTIONS = [
  { label: 'メール', value: 'email' },
  { label: '会議文字起こし', value: 'meeting' },
  { label: 'チャット', value: 'chat' },
]

const PRIORITY_OPTIONS = [
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
]

interface CandidateTask extends ExtractedTask {
  _id: string
  selected: boolean
  promoted: boolean
  editedTitle: string
  editedAssigneeId: string | null
  editedDueDate: string | null
  editedPriority: 'high' | 'medium' | 'low'
  editedProjectId: string | null
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function ExtractModal({ open, onClose }: Props) {
  const [sourceType, setSourceType] = useState<string>('email')
  const [text, setText] = useState('')
  const [candidates, setCandidates] = useState<CandidateTask[]>([])
  const [patternB, setPatternB] = useState(false)
  const [editTarget, setEditTarget] = useState<CandidateTask | null>(null)
  const [editForm] = Form.useForm()

  const extractTasks = useExtractTasks()
  const createTask = useCreateTask()
  const { data: users = [] } = useUsers()
  const { data: projects = [] } = useProjects()

  const handleClose = () => {
    setText('')
    setCandidates([])
    setPatternB(false)
    setSourceType('email')
    onClose()
  }

  const handleExtract = async () => {
    if (!text.trim()) return
    setPatternB(false)
    const result = await extractTasks.mutateAsync({ text, sourceType })
    if (result.skipped_reason) {
      setPatternB(true)
      setCandidates([])
      return
    }
    setCandidates(
      result.tasks.map((t, i) => ({
        ...t,
        _id: `${i}-${Date.now()}`,
        selected: t.is_task,
        promoted: false,
        editedTitle: t.title,
        editedAssigneeId: null,
        editedDueDate: t.deadline ?? null,
        editedPriority: t.priority,
        editedProjectId: null,
      })),
    )
  }

  const toggleSelect = (id: string) => {
    setCandidates((prev) =>
      prev.map((c) => (c._id === id ? { ...c, selected: !c.selected } : c)),
    )
  }

  const promoteCandidate = (id: string) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c._id === id ? { ...c, is_task: true, promoted: true, selected: true } : c,
      ),
    )
  }

  const openEdit = (candidate: CandidateTask) => {
    setEditTarget(candidate)
    editForm.setFieldsValue({
      title: candidate.editedTitle,
      assignee_id: candidate.editedAssigneeId,
      due_date: candidate.editedDueDate ? dayjs(candidate.editedDueDate) : null,
      priority: candidate.editedPriority,
      project_id: candidate.editedProjectId,
    })
  }

  const handleEditSave = () => {
    const values = editForm.getFieldsValue()
    if (!editTarget) return
    setCandidates((prev) =>
      prev.map((c) =>
        c._id === editTarget._id
          ? {
              ...c,
              editedTitle: values.title as string,
              editedAssigneeId: (values.assignee_id as string | null) ?? null,
              editedDueDate: values.due_date
                ? (values.due_date as dayjs.Dayjs).format('YYYY-MM-DD')
                : null,
              editedPriority: values.priority as 'high' | 'medium' | 'low',
              editedProjectId: (values.project_id as string | null) ?? null,
            }
          : c,
      ),
    )
    setEditTarget(null)
    editForm.resetFields()
  }

  const selectedCount = candidates.filter((c) => c.selected).length

  const handleCreateAll = async () => {
    const targets = candidates.filter((c) => c.selected)
    let successCount = 0
    for (const c of targets) {
      try {
        await createTask.mutateAsync({
          title: c.editedTitle,
          assignee_id: c.editedAssigneeId ?? undefined,
          due_date: c.editedDueDate ?? undefined,
          priority: c.editedPriority,
          project_id: c.editedProjectId ?? undefined,
          visibility: c.visibility,
        } as Parameters<typeof createTask.mutateAsync>[0])
        successCount++
      } catch {
        void message.error(`「${c.editedTitle}」の起票に失敗しました`)
      }
    }
    if (successCount > 0) {
      void message.success(`${successCount} 件のタスクを起票しました`)
      handleClose()
    }
  }

  const priorityColor: Record<string, string> = {
    high: 'red',
    medium: 'orange',
    low: 'default',
  }

  return (
    <>
      <Modal
        open={open}
        onCancel={handleClose}
        footer={null}
        title="テキストからタスクを抽出"
        width={1000}
        styles={{ body: { padding: 0 } }}
      >
        <Row style={{ minHeight: 480 }}>
          {/* 左パネル */}
          <Col
            span={10}
            style={{ padding: 20, borderRight: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            <div>
              <Text strong>入力元</Text>
              <Radio.Group
                options={SOURCE_OPTIONS}
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as string)}
                optionType="button"
                buttonStyle="solid"
                size="small"
                style={{ display: 'flex', marginTop: 8 }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Text strong>テキスト</Text>
              <TextArea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={14}
                placeholder="会議文字起こし・メール文面・チャットコメントを貼り付けてください"
                style={{ marginTop: 8, resize: 'vertical' }}
              />
            </div>
            {patternB && (
              <Alert
                type="warning"
                message="機密データが検知されました"
                description="社外秘キーワードが含まれているため、外部 LLM への送信をブロックしました。テキストを変更するか、担当者に相談してください。"
                action={
                  <Button size="small" onClick={() => { setPatternB(false); extractTasks.reset() }}>
                    閉じる
                  </Button>
                }
              />
            )}
            <Button
              type="primary"
              onClick={handleExtract}
              loading={extractTasks.isPending}
              disabled={!text.trim()}
              block
            >
              抽出する
            </Button>
          </Col>

          {/* 右パネル */}
          <Col span={14} style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', maxHeight: 560 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Title level={5} style={{ margin: 0 }}>
                抽出結果（{candidates.length} 件）
              </Title>
              {selectedCount > 0 && (
                <Popconfirm
                  title={`選択した ${selectedCount} 件を起票しますか？`}
                  onConfirm={handleCreateAll}
                  okText="起票する"
                  cancelText="キャンセル"
                >
                  <Button type="primary" size="small" loading={createTask.isPending}>
                    選択した {selectedCount} 件を起票
                  </Button>
                </Popconfirm>
              )}
            </div>

            {extractTasks.isError && (
              <Alert type="error" message="抽出に失敗しました。再試行してください。" />
            )}
            {candidates.length === 0 && !extractTasks.isPending && !extractTasks.isError && (
              <Text type="secondary" style={{ textAlign: 'center', marginTop: 40, display: 'block' }}>
                左のテキストを入力して「抽出する」を押してください
              </Text>
            )}

            {candidates.map((c) => {
              const isDisabled = !c.is_task && !c.promoted
              return (
                <Card
                  key={c._id}
                  size="small"
                  style={{
                    opacity: isDisabled ? 0.55 : 1,
                    borderColor: isDisabled ? '#d9d9d9' : undefined,
                  }}
                  extra={
                    isDisabled ? (
                      <Button
                        size="small"
                        icon={<RiseOutlined />}
                        onClick={() => promoteCandidate(c._id)}
                      >
                        昇格
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => openEdit(c)}
                      >
                        編集
                      </Button>
                    )
                  }
                  title={
                    <Space>
                      <Checkbox
                        checked={c.selected}
                        disabled={isDisabled}
                        onChange={() => toggleSelect(c._id)}
                      />
                      <Text
                        strong={!isDisabled}
                        type={isDisabled ? 'secondary' : undefined}
                        style={{ maxWidth: 260 }}
                        ellipsis={{ tooltip: c.editedTitle }}
                      >
                        {c.editedTitle}
                      </Text>
                    </Space>
                  }
                >
                  <Space wrap size={4}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      担当: {c.editedAssigneeId
                        ? (users.find((u) => u.user_id === c.editedAssigneeId)?.display_name ?? '未設定')
                        : '未設定'}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      期日: {c.editedDueDate ?? '未設定'}
                    </Text>
                    <Tag color={priorityColor[c.editedPriority]} style={{ fontSize: 11 }}>
                      {c.editedPriority === 'high' ? '高' : c.editedPriority === 'medium' ? '中' : '低'}
                    </Tag>
                  </Space>
                  <Progress
                    percent={Math.round(c.confidence_score * 100)}
                    size="small"
                    style={{ marginTop: 4, marginBottom: 0 }}
                    format={(p) => `信頼度 ${p}%`}
                  />
                </Card>
              )
            })}
          </Col>
        </Row>
      </Modal>

      {/* 編集サブモーダル */}
      <Modal
        open={!!editTarget}
        onCancel={() => { setEditTarget(null); editForm.resetFields() }}
        onOk={handleEditSave}
        title="タスクを編集"
        okText="保存"
        cancelText="キャンセル"
        width={480}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true, message: 'タイトルを入力してください' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="assignee_id"
            label={
              editTarget?.assignee_name
                ? `担当者（🤖 AI提案: ${editTarget.assignee_name}）`
                : '担当者'
            }
          >
            <Select
              allowClear
              showSearch
              placeholder="担当者を選択"
              filterOption={(input, option) =>
                String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={users
                .filter((u) =>
                  editTarget?.assignee_name
                    ? u.display_name.includes(editTarget.assignee_name)
                    : true
                )
                .concat(
                  editTarget?.assignee_name
                    ? users.filter(
                        (u) => !u.display_name.includes(editTarget.assignee_name ?? '')
                      )
                    : [],
                )
                .map((u) => ({ label: u.display_name, value: u.user_id }))}
            />
          </Form.Item>
          <Form.Item name="due_date" label="期日">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="priority" label="優先度">
            <Select options={PRIORITY_OPTIONS} />
          </Form.Item>
          <Form.Item name="project_id" label="プロジェクト">
            <Select
              allowClear
              placeholder="プロジェクトを選択"
              options={projects.map((p) => ({ label: p.name, value: p.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
