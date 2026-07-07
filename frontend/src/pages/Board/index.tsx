import { useCallback, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Card, Select, Space, Spin, Tag, Typography } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { useProjects } from '../../hooks/useProjects'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useUpdateTask, useReorderTask } from '../../hooks/useTasks'
import type { Task } from '../../lib/api'

const { Title } = Typography

const STATUS_COLUMNS = [
  { key: 'not_started', label: '未着手', color: '#d9d9d9' },
  { key: 'in_progress', label: '進行中', color: '#1677ff' },
  { key: 'completed', label: '完了', color: '#52c41a' },
  { key: 'cancelled', label: 'キャンセル', color: '#ff4d4f' },
]

const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'red',
  high: 'orange',
  medium: 'blue',
  low: 'default',
}

function TaskCard({ task, onCardClick }: { task: Task; onCardClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.3 : 1,
        marginBottom: 8,
        cursor: isDragging ? 'grabbing' : 'grab',
        zIndex: isDragging ? 1000 : undefined,
        position: isDragging ? 'relative' : undefined,
      }}
      {...attributes}
      {...listeners}
    >
      <Card
        size="small"
        onClick={onCardClick}
        hoverable
      >
        <div style={{ marginBottom: 4, fontWeight: 500, fontSize: 13 }}>{task.title}</div>
        <Space size={4} wrap>
          <Tag color={PRIORITY_COLORS[task.priority] ?? 'default'} style={{ fontSize: 11 }}>
            {task.priority}
          </Tag>
          {task.due_date && (
            <span style={{ fontSize: 11, color: '#888' }}>{task.due_date}</span>
          )}
        </Space>
        {task.assignee_name && (
          <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
            <UserOutlined style={{ marginRight: 4 }} />
            {task.assignee_name}
          </div>
        )}
      </Card>
    </div>
  )
}

function KanbanColumn({
  colKey,
  label,
  color,
  tasks,
  onCardClick,
}: {
  colKey: string
  label: string
  color: string
  tasks: Task[]
  onCardClick: (taskId: string) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: colKey })

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: '0 0 260px',
        background: isOver ? '#e6f4ff' : '#f5f5f5',
        borderRadius: 8,
        padding: 12,
        minHeight: 200,
        transition: 'background 0.15s',
      }}
    >
      <div
        style={{
          borderLeft: `4px solid ${color}`,
          paddingLeft: 8,
          marginBottom: 12,
          fontWeight: 600,
        }}
      >
        {label}{' '}
        <span style={{ color: '#888', fontSize: 13 }}>({tasks.length})</span>
      </div>
      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onCardClick={() => onCardClick(task.id)} />
        ))}
      </SortableContext>
    </div>
  )
}

export default function Board() {
  const [projectId, setProjectId] = useState<string | undefined>()
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const dragOccurredRef = useRef(false)
  const navigate = useNavigate()

  const { data: projects = [] } = useProjects({ scope: 'all' })
  const { data: tasks = [], isLoading } = useTasksForView({ project_id: projectId })
  const queryClient = useQueryClient()
  const updateTask = useUpdateTask()
  const reorderTask = useReorderTask()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const columns = STATUS_COLUMNS

  const columnTasks = useMemo(
    () =>
      STATUS_COLUMNS.reduce<Record<string, Task[]>>((acc, col) => {
        acc[col.key] = tasks.filter((t) => t.status === col.key)
        return acc
      }, {}),
    [tasks]
  )

  const handleDragStart = ({ active }: DragStartEvent) => {
    dragOccurredRef.current = true
    setActiveTask(tasks.find((t) => t.id === active.id) ?? null)
  }

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveTask(null)
    if (!over) {
      dragOccurredRef.current = false
      return
    }
    const activeId = String(active.id)
    const overId = String(over.id)

    // active タスクが属するカラムを特定
    const activeColKey = STATUS_COLUMNS.find((col) =>
      (columnTasks[col.key] ?? []).some((t) => t.id === activeId)
    )?.key

    // over がカラムキーかタスク ID かを判定してカラムを特定
    const overColKey =
      STATUS_COLUMNS.find((col) => col.key === overId)?.key ??
      STATUS_COLUMNS.find((col) => (columnTasks[col.key] ?? []).some((t) => t.id === overId))?.key

    if (!activeColKey || !overColKey) {
      dragOccurredRef.current = false
      return
    }

    if (activeColKey === overColKey) {
      // 同一カラム内の並び替え
      const colTasks = columnTasks[activeColKey] ?? []
      const activeIndex = colTasks.findIndex((t) => t.id === activeId)
      // over.id がカラムキーのとき（空白部分へのドロップ）は末尾扱い
      const overIndex =
        overId === activeColKey
          ? colTasks.length - 1
          : colTasks.findIndex((t) => t.id === overId)
      if (activeIndex !== -1 && overIndex !== -1 && activeIndex !== overIndex) {
        const newOrder = arrayMove(colTasks, activeIndex, overIndex)
        const beforeTask = overIndex > 0 ? newOrder[overIndex - 1] : null
        const afterTask = overIndex < newOrder.length - 1 ? newOrder[overIndex + 1] : null

        // 楽観的更新: サーバー応答を待たずに並び替えを即時反映する
        const queryKey = ['tasks-view', { project_id: projectId }]
        const previous = queryClient.getQueryData<Task[]>(queryKey)
        let colCursor = 0
        queryClient.setQueryData<Task[]>(queryKey, (old = []) =>
          old.map((t) => (t.status === activeColKey ? newOrder[colCursor++] : t))
        )

        reorderTask.mutate(
          {
            taskId: activeId,
            beforeId: beforeTask?.id ?? null,
            afterId: afterTask?.id ?? null,
          },
          {
            onError: () => {
              queryClient.setQueryData(queryKey, previous)
            },
          }
        )
      }
    } else {
      // 別カラムへのドロップ → ステータス更新のみ（楽観的更新）。
      // カラム間の挿入位置は保持しない（仕様）: reorder はセクション/プロジェクト一致を
      // 要求する（issue #21）ため、ステータスのみ変更し並びはサーバ規則に委ねる（issue #38）。
      const queryKey = ['tasks-view', { project_id: projectId }]
      const previous = queryClient.getQueryData<Task[]>(queryKey)
      queryClient.setQueryData<Task[]>(queryKey, (old = []) =>
        old.map((t) => (t.id === activeId ? { ...t, status: overColKey } : t))
      )
      updateTask.mutate(
        { id: activeId, status: overColKey },
        {
          onError: () => {
            queryClient.setQueryData(queryKey, previous)
          },
          onSettled: () => {
            void queryClient.invalidateQueries({ queryKey: ['tasks-view'] })
          },
        }
      )
    }

    // dragOccurredRef は次の click イベントのタイミングでリセットするため setTimeout を使う
    setTimeout(() => { dragOccurredRef.current = false }, 100)
  }

  const handleCardClick = useCallback((taskId: string) => {
    if (!dragOccurredRef.current) {
      navigate(`/tasks/${taskId}`)
    }
  }, [navigate])

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space align="center">
        <Title level={3} style={{ margin: 0 }}>
          カンバン
        </Title>
        <Select
          allowClear
          placeholder="プロジェクト（任意）"
          style={{ width: 240 }}
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          onChange={(v) => setProjectId(v)}
        />
      </Space>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 16 }}>
            {columns.map((col) => (
              <KanbanColumn
                key={col.key}
                colKey={col.key}
                label={col.label}
                color={col.color}
                tasks={columnTasks[col.key] ?? []}
                onCardClick={handleCardClick}
              />
            ))}
          </div>
          <DragOverlay>
            {activeTask && (
              <Card
                size="small"
                style={{ width: 240, opacity: 0.9, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
              >
                <div style={{ fontWeight: 500 }}>{activeTask.title}</div>
              </Card>
            )}
          </DragOverlay>
        </DndContext>
      )}
    </Space>
  )
}
