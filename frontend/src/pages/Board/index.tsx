import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import { Card, Select, Space, Spin, Tag, Typography } from 'antd'
import { useProjects } from '../../hooks/useProjects'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useUpdateTask } from '../../hooks/useTasks'
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

function TaskCard({ task }: { task: Task }) {
  const navigate = useNavigate()
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined,
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
        onClick={() => !isDragging && navigate(`/tasks/${task.id}`)}
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
      </Card>
    </div>
  )
}

function KanbanColumn({
  colKey,
  label,
  color,
  tasks,
}: {
  colKey: string
  label: string
  color: string
  tasks: Task[]
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
      {tasks.map((task) => (
        <TaskCard key={task.id} task={task} />
      ))}
    </div>
  )
}

export default function Board() {
  const [projectId, setProjectId] = useState<string | undefined>()
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const { data: projects = [] } = useProjects()
  const { data: tasks = [], isLoading } = useTasksForView({ project_id: projectId })
  const updateTask = useUpdateTask()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const columns = STATUS_COLUMNS

  const getColumnTasks = (colKey: string) => tasks.filter((t) => t.status === colKey)

  const handleDragStart = ({ active }: DragStartEvent) => {
    setActiveTask(tasks.find((t) => t.id === active.id) ?? null)
  }

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveTask(null)
    if (!over) return
    const overColKey = columns.find((c) => c.key === String(over.id))?.key
    if (!overColKey) return
    updateTask.mutate({ id: String(active.id), status: overColKey })
  }

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
                tasks={getColumnTasks(col.key)}
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
