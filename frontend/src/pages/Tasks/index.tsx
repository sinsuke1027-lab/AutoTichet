import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  DatePicker,
  Divider,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Progress,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { CopyOutlined, DownloadOutlined, FileTextOutlined, HolderOutlined, PlusOutlined, RedoOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useMutation } from '@tanstack/react-query'
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent } from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useTasks, useCreateTask, useEstimateHours, useRecordEstimatedHours, useReorderTask, useBulkUpdateTasks } from '../../hooks/useTasks'
import { useProjects } from '../../hooks/useProjects'
import { useSections } from '../../hooks/useSections'
import { useSimilarTasks } from '../../hooks/useSimilarTasks'
import { useUsers } from '../../hooks/useUsers'
import { useTemplates, useApplyTemplate } from '../../hooks/useTemplates'
import { useAuthStore } from '../../store/useAuthStore'
import type { Task } from '../../lib/api'
import api, { generateHandover } from '../../lib/api'
import ExtractModal from './ExtractModal'

const ROLE_LEVEL: Record<string, number> = { member: 0, leader: 1, manager: 2, admin: 3 }

const STATUS_OPTIONS = [
  { label: '全て', value: '' },
  { label: '未着手', value: 'not_started' },
  { label: '進行中', value: 'in_progress' },
  { label: '完了', value: 'completed' },
  { label: 'キャンセル', value: 'cancelled' },
]

interface DraggableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  'data-row-key': string
}

function DraggableRow({ 'data-row-key': id, style, ...props }: DraggableRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  return (
    <tr
      ref={setNodeRef}
      style={{
        ...style,
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        background: isDragging ? '#f0f5ff' : undefined,
      }}
      {...props}
      {...attributes}
      {...listeners}
    />
  )
}

export default function TaskList() {
  const navigate = useNavigate()
  const roles = useAuthStore((s) => s.roles)
  const userLevel = Math.max(...roles.map((r) => ROLE_LEVEL[r] ?? 0), 0)
  const canFilterByAssignee = userLevel >= ROLE_LEVEL['leader']

  const [statusFilter, setStatusFilter] = useState('')
  const [projectFilter, setProjectFilter] = useState<string | undefined>()
  const [sectionFilter, setSectionFilter] = useState<string | undefined>()
  const [assigneeFilter, setAssigneeFilter] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [myTasksOnly, setMyTasksOnly] = useState(false)
  const [includeArchivedProjects, setIncludeArchivedProjects] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [localItems, setLocalItems] = useState<Task[]>([])
  const reorderTask = useReorderTask()
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [bulkStatus, setBulkStatus] = useState<string | undefined>()
  const [bulkAssignee, setBulkAssignee] = useState<string | undefined>()
  const bulkUpdate = useBulkUpdateTasks()
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))
  const [newTitle, setNewTitle] = useState('')
  const [open, setOpen] = useState(false)
  const [extractModalOpen, setExtractModalOpen] = useState(false)
  const [handoverOpen, setHandoverOpen] = useState(false)
  const [handoverDoc, setHandoverDoc] = useState('')
  const [handoverTarget, setHandoverTarget] = useState<string | undefined>()
  const generateHandoverMutation = useMutation({
    mutationFn: (assigneeId: string | undefined) => generateHandover(assigneeId),
  })
  const [form] = Form.useForm()
  const watchedTags = (Form.useWatch('tags', form) as string[] | undefined) ?? []
  const { data: estimate } = useEstimateHours(watchedTags)
  const recordEstimatedHours = useRecordEstimatedHours()
  const autoFilledRef = useRef(false)

  useEffect(() => {
    if (!estimate || estimate.task_count === 0 || estimate.avg_actual_hours == null) return
    const current = form.getFieldValue('estimated_hours') as number | undefined
    if (current == null || autoFilledRef.current) {
      form.setFieldValue('estimated_hours', estimate.avg_actual_hours)
      autoFilledRef.current = true
    }
  }, [estimate, form])

  const { data: taskList, isLoading } = useTasks({
    status: statusFilter || undefined,
    assignee: assigneeFilter,
    project_id: projectFilter,
    section_id: sectionFilter,
    q: searchQ || undefined,
    my_tasks_only: myTasksOnly || undefined,
    include_archived_projects: includeArchivedProjects || undefined,
  })
  const { data: projects = [] } = useProjects()
  const { data: sections = [] } = useSections(projectFilter)
  const { data: users = [] } = useUsers()
  const createTask = useCreateTask()
  const { data: similarTasks = [] } = useSimilarTasks(newTitle)
  const { data: templates = [] } = useTemplates()
  const applyTemplate = useApplyTemplate()
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | undefined>()
  const [templateBaseDate, setTemplateBaseDate] = useState<string>(
    new Date().toISOString().split('T')[0],
  )

  const handleSearch = () => setSearchQ(keyword)

  const handleBulkApply = async () => {
    try {
      const res = await bulkUpdate.mutateAsync({
        task_ids: selectedRowKeys,
        ...(bulkStatus ? { status: bulkStatus } : {}),
        ...(bulkAssignee ? { assignee_id: bulkAssignee } : {}),
      })
      void message.success(`${res.updated_count}件を更新しました`)
      setSelectedRowKeys([])
      setBulkStatus(undefined)
      setBulkAssignee(undefined)
    } catch {
      void message.error('一括更新に失敗しました')
    }
  }

  useEffect(() => {
    if (taskList?.items) setLocalItems(taskList.items)
  }, [taskList?.items])

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const activeId = String(active.id)
    const overId = String(over.id)
    const oldIndex = localItems.findIndex((t) => t.id === activeId)
    const newIndex = localItems.findIndex((t) => t.id === overId)
    if (oldIndex === -1 || newIndex === -1) return
    const newItems = arrayMove(localItems, oldIndex, newIndex)
    const prevItems = localItems
    setLocalItems(newItems)
    const beforeTask = newIndex > 0 ? newItems[newIndex - 1] : null
    const afterTask = newIndex < newItems.length - 1 ? newItems[newIndex + 1] : null
    reorderTask.mutate(
      { taskId: activeId, beforeId: beforeTask?.id ?? null, afterId: afterTask?.id ?? null },
      {
        onError: () => {
          setLocalItems(prevItems)
          void message.error('並び替えに失敗しました')
        },
      }
    )
  }

  const handleExportCsv = async () => {
    if (exporting) return
    setExporting(true)
    const params: Record<string, string> = {}
    if (statusFilter) params['status'] = statusFilter
    if (projectFilter) params['project_id'] = projectFilter
    if (sectionFilter) params['section_id'] = sectionFilter
    if (assigneeFilter) params['assignee'] = assigneeFilter
    if (searchQ) params['q'] = searchQ
    if (myTasksOnly) params['my_tasks_only'] = 'true'
    if (includeArchivedProjects) params['include_archived_projects'] = 'true'

    try {
      const { data } = await api.get<Blob>('/tasks/export/csv', {
        params,
        responseType: 'blob',
      })
      const url = URL.createObjectURL(data)
      const a = document.createElement('a')
      a.href = url
      a.download = `tasks_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`
      try {
        document.body.appendChild(a)
        a.click()
      } finally {
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
    } catch {
      void message.error('CSV のエクスポートに失敗しました')
    } finally {
      setExporting(false)
    }
  }

  const handleCreate = async (values: Record<string, unknown>) => {
    const { estimated_hours, recurrence_end_date, ...taskValues } = values as {
      estimated_hours?: number
      recurrence_end_date?: import('dayjs').Dayjs
      [key: string]: unknown
    }
    const payload = {
      ...taskValues,
      ...(recurrence_end_date
        ? { recurrence_end_date: recurrence_end_date.format('YYYY-MM-DD') }
        : {}),
    }
    const created = await createTask.mutateAsync(
      payload as Partial<import('../../lib/api').Task> & { title: string },
    )
    if (estimated_hours != null && created?.id) {
      await recordEstimatedHours.mutateAsync({
        taskId: created.id as string,
        estimatedHours: estimated_hours,
      })
    }
    setOpen(false)
    form.resetFields()
    autoFilledRef.current = false
    setNewTitle('')
  }

  const handleApplyTemplate = async () => {
    if (!selectedTemplateId) return
    try {
      const result = await applyTemplate.mutateAsync({
        id: selectedTemplateId,
        body: { base_date: templateBaseDate },
      })
      setOpen(false)
      setSelectedTemplateId(undefined)
      setTemplateBaseDate(new Date().toISOString().split('T')[0])
      navigate(`/tasks/${result.task_id}`)
    } catch {
      void message.error('テンプレートの適用に失敗しました')
    }
  }

  const STATUS_LABEL: Record<string, string> = {
    not_started: '未着手',
    in_progress: '進行中',
    completed: '完了',
    cancelled: 'キャンセル',
  }
  const STATUS_COLOR: Record<string, string> = {
    not_started: 'default',
    in_progress: 'processing',
    completed: 'success',
    cancelled: 'error',
  }

  const columns = [
    {
      key: 'drag-handle',
      width: 40,
      render: () => <HolderOutlined style={{ color: '#bbb', cursor: 'grab' }} />,
    },
    {
      title: 'タスク名',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, rec: Task) => (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <a onClick={() => navigate(`/tasks/${rec.id}`)}>{title}</a>
          {rec.risk_level === 'high' && <Tag color="red">高リスク</Tag>}
          {rec.risk_level === 'medium' && <Tag color="orange">要注意</Tag>}
          {rec.recurrence_rule && (
            <Tooltip title={`繰り返し: ${rec.recurrence_rule === 'daily' ? '毎日' : rec.recurrence_rule === 'weekly' ? '毎週' : '毎月'}`}>
              <RedoOutlined style={{ color: '#1677ff', fontSize: 12 }} />
            </Tooltip>
          )}
        </span>
      ),
    },
    {
      title: 'ステータス',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'}>{STATUS_LABEL[s] ?? s}</Tag>
      ),
    },
    { title: '優先度', dataIndex: 'priority', key: 'priority' },
    {
      title: '期限',
      dataIndex: 'due_date',
      key: 'due_date',
      render: (d: string | null) => d ?? '—',
    },
    {
      title: 'サブタスク',
      key: 'subtasks',
      width: 120,
      render: (_: unknown, rec: Task) => {
        const total = rec.subtask_count ?? 0
        if (total === 0) return <span style={{ color: '#bbb' }}>—</span>
        const done = rec.subtask_done_count ?? 0
        const pct = Math.round((done / total) * 100)
        return (
          <Tooltip title={`${done} / ${total} 件完了`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Progress
                percent={pct}
                size="small"
                style={{ width: 60, margin: 0 }}
                showInfo={false}
              />
              <span style={{ fontSize: 12, whiteSpace: 'nowrap', color: '#555' }}>
                {done}/{total}
              </span>
            </div>
          </Tooltip>
        )
      },
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          タスク一覧
        </Typography.Title>
        <Space>
          {canFilterByAssignee && (
            <Select
              placeholder="引き継ぎ対象者（未選択 = 自分）"
              allowClear
              options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
              value={handoverTarget}
              onChange={setHandoverTarget}
              style={{ width: 180 }}
            />
          )}
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void handleExportCsv()}>
            CSV エクスポート
          </Button>
          <Button
            icon={<FileTextOutlined />}
            loading={generateHandoverMutation.isPending}
            onClick={async () => {
              try {
                const res = await generateHandoverMutation.mutateAsync(handoverTarget)
                setHandoverDoc(res.document)
                setHandoverOpen(true)
              } catch {
                void message.error('引き継ぎ書の生成に失敗しました')
              }
            }}
          >
            引き継ぎ書を生成
          </Button>
          <Button icon={<RobotOutlined />} onClick={() => setExtractModalOpen(true)}>
            テキストから作成
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            新規タスク
          </Button>
        </Space>
      </Space>

      <Space wrap>
        <Input
          placeholder="キーワード検索"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={handleSearch}
          suffix={<SearchOutlined onClick={handleSearch} style={{ cursor: 'pointer' }} />}
          style={{ width: 220 }}
        />
        <Select
          placeholder="ステータス"
          options={STATUS_OPTIONS}
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 130 }}
        />
        <Select
          placeholder="プロジェクト"
          allowClear
          options={projects.map((p) => ({ label: p.name, value: p.id }))}
          value={projectFilter}
          onChange={(v: string | undefined) => {
            setProjectFilter(v)
            setSectionFilter(undefined)
          }}
          style={{ width: 160 }}
        />
        {projectFilter !== undefined && (
          <Select
            placeholder="セクション"
            allowClear
            options={sections.map((s) => ({ label: s.name, value: s.id }))}
            value={sectionFilter}
            onChange={setSectionFilter}
            style={{ width: 160 }}
          />
        )}
        {canFilterByAssignee && (
          <Select
            placeholder="担当者"
            allowClear
            options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
            value={assigneeFilter}
            onChange={(v: string | undefined) => {
              setAssigneeFilter(v)
              if (v) setMyTasksOnly(false)
            }}
            style={{ width: 150 }}
          />
        )}
        <Space>
          <Switch
            checked={myTasksOnly}
            onChange={(v) => {
              setMyTasksOnly(v)
              if (v) setAssigneeFilter(undefined)
            }}
          />
          <span>自分の ToDo のみ</span>
        </Space>
        <Space>
          <Switch
            checked={includeArchivedProjects}
            onChange={setIncludeArchivedProjects}
          />
          <span>アーカイブ済みプロジェクトを含む</span>
        </Space>
      </Space>

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <SortableContext items={localItems.map((t) => t.id)} strategy={verticalListSortingStrategy}>
          <Table
            rowKey="id"
            loading={isLoading}
            dataSource={localItems}
            columns={columns}
            pagination={{ pageSize: 20, total: taskList?.total, showSizeChanger: false }}
            components={{ body: { row: DraggableRow } }}
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys as string[]),
            }}
          />
        </SortableContext>
      </DndContext>

      <Modal
        title="新規タスク作成"
        open={open}
        onOk={async () => {
          try {
            const values = await form.validateFields()
            await handleCreate(values as Record<string, unknown>)
          } catch {
            void message.error('タスクの作成に失敗しました')
          }
        }}
        onCancel={() => {
          setOpen(false)
          form.resetFields()
          setNewTitle('')
          setSelectedTemplateId(undefined)
          setTemplateBaseDate(new Date().toISOString().split('T')[0])
        }}
        confirmLoading={createTask.isPending}
      >
        {templates.length > 0 && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
            <Typography.Text strong>
              <RobotOutlined style={{ marginRight: 6 }} />
              テンプレートから作成
            </Typography.Text>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                <Select
                  placeholder="テンプレートを選択"
                  style={{ width: 220 }}
                  allowClear
                  options={templates.map((t) => ({ label: t.name, value: t.id }))}
                  value={selectedTemplateId}
                  onChange={setSelectedTemplateId}
                />
                <DatePicker
                  placeholder="基準日"
                  value={selectedTemplateId ? dayjs(templateBaseDate) : undefined}
                  onChange={(d) => d && setTemplateBaseDate(d.format('YYYY-MM-DD'))}
                />
                <Button
                  type="primary"
                  disabled={!selectedTemplateId}
                  loading={applyTemplate.isPending}
                  onClick={() => void handleApplyTemplate()}
                >
                  このテンプレートで作成
                </Button>
              </Space>
            </div>
          </div>
        )}
        {templates.length > 0 && <Divider plain>または手動で作成</Divider>}
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="タスク名" rules={[{ required: true }]}>
            <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          </Form.Item>
          {similarTasks.length > 0 && (
            <Alert
              type="warning"
              style={{ marginBottom: 12 }}
              message={`類似タスクが見つかりました（${similarTasks.length}件）`}
              description={
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {similarTasks.map((t) => (
                    <li key={t.id}>
                      {t.title} ({t.status})
                    </li>
                  ))}
                </ul>
              }
            />
          )}
          <Form.Item name="description" label="説明">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="tags" label="タグ">
            <Select
              mode="tags"
              style={{ width: '100%' }}
              placeholder="タグを入力（Enter で確定）"
              tokenSeparators={[',']}
            />
          </Form.Item>

          {estimate && estimate.task_count >= 1 && estimate.avg_actual_hours != null ? (
            <Form.Item label=" " colon={false}>
              <Tag color="blue">
                🤖 過去{estimate.task_count}件: 平均 {estimate.avg_actual_hours}h
                {estimate.min_actual_hours != null &&
                  ` / 最小 ${estimate.min_actual_hours}h / 最大 ${estimate.max_actual_hours}h`}
              </Tag>
            </Form.Item>
          ) : watchedTags.length > 0 ? (
            <Form.Item label=" " colon={false}>
              <Tag color="default">🤖 データ不足（0件）</Tag>
            </Form.Item>
          ) : null}

          <Form.Item name="estimated_hours" label="予定工数（h）">
            <InputNumber
              min={0}
              step={0.5}
              style={{ width: '100%' }}
              placeholder="例: 2.0"
              onChange={() => { autoFilledRef.current = false }}
            />
          </Form.Item>
          <Form.Item name="recurrence_rule" label="繰り返し">
            <Select
              allowClear
              placeholder="なし"
              style={{ width: 160 }}
              options={[
                { label: '毎日', value: 'daily' },
                { label: '毎週', value: 'weekly' },
                { label: '毎月', value: 'monthly' },
              ]}
            />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev: Record<string, unknown>, curr: Record<string, unknown>) => prev.recurrence_rule !== curr.recurrence_rule}
          >
            {({ getFieldValue }: { getFieldValue: (name: string) => unknown }) =>
              getFieldValue('recurrence_rule') ? (
                <Form.Item name="recurrence_end_date" label="繰り返し終了日">
                  <DatePicker style={{ width: 160 }} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item name="visibility" label="公開範囲" initialValue="team">
            <Select
              options={[
                { label: 'チーム共有', value: 'team' },
                { label: '全公開', value: 'all' },
                { label: '個人（ToDo）', value: 'private' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="引き継ぎ書"
        open={handoverOpen}
        onCancel={() => {
          setHandoverOpen(false)
          setHandoverDoc('')
        }}
        width={720}
        footer={
          <Button
            icon={<CopyOutlined />}
            onClick={() => {
              void navigator.clipboard.writeText(handoverDoc)
              void message.success('コピーしました')
            }}
          >
            クリップボードにコピー
          </Button>
        }
      >
        <Input.TextArea value={handoverDoc} rows={20} readOnly style={{ fontFamily: 'monospace' }} />
      </Modal>
      <ExtractModal
        open={extractModalOpen}
        onClose={() => setExtractModalOpen(false)}
      />
      {selectedRowKeys.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0,
          background: '#fff', borderTop: '1px solid #f0f0f0',
          padding: '12px 24px', zIndex: 100,
          display: 'flex', alignItems: 'center', gap: 12,
          boxShadow: '0 -2px 8px rgba(0,0,0,0.08)',
        }}>
          <Typography.Text strong>{selectedRowKeys.length}件選択中</Typography.Text>
          <Select
            placeholder="ステータスを変更"
            allowClear
            style={{ width: 160 }}
            options={STATUS_OPTIONS.filter((o) => o.value !== '')}
            value={bulkStatus}
            onChange={setBulkStatus}
          />
          <Select
            placeholder="担当者を変更"
            allowClear
            style={{ width: 160 }}
            options={users.map((u) => ({ label: u.display_name, value: u.user_id }))}
            value={bulkAssignee}
            onChange={setBulkAssignee}
          />
          <Button
            type="primary"
            loading={bulkUpdate.isPending}
            disabled={!bulkStatus && !bulkAssignee}
            onClick={() => void handleBulkApply()}
          >
            適用
          </Button>
          <Button onClick={() => {
            setSelectedRowKeys([])
            setBulkStatus(undefined)
            setBulkAssignee(undefined)
          }}>
            選択解除
          </Button>
        </div>
      )}
    </Space>
  )
}
