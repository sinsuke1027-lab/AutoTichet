import { useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Card, Space, Tag, Typography } from 'antd'
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import dayjs from 'dayjs'
import 'dayjs/locale/ja'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useUpdateTask } from '../../hooks/useTasks'
import type { Task } from '../../lib/api'

dayjs.locale('ja')

function getWeekDays(): dayjs.Dayjs[] {
  const today = dayjs()
  return Array.from({ length: 7 }, (_, i) => today.subtract(3, 'day').add(i, 'day'))
}

function TaskCard({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  })
  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        opacity: isDragging ? 0.5 : 1,
        cursor: 'grab',
        marginBottom: 4,
      }}
      {...listeners}
      {...attributes}
    >
      <Card size="small" style={{ fontSize: 12 }}>
        <div style={{ fontWeight: 500 }}>{task.title}</div>
        {task.due_date && (
          <Tag color="blue" style={{ marginTop: 4, fontSize: 10 }}>
            期限: {task.due_date}
          </Tag>
        )}
      </Card>
    </div>
  )
}

function DateColumn({ day, tasks }: { day: dayjs.Dayjs; tasks: Task[] }) {
  const isToday = day.isSame(dayjs(), 'day')
  const dateKey = day.format('YYYY-MM-DD')
  const { setNodeRef, isOver } = useDroppable({ id: dateKey })

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: 1,
        minWidth: 120,
        minHeight: 200,
        padding: 8,
        border: `2px solid ${isOver ? '#1677ff' : isToday ? '#91caff' : '#d9d9d9'}`,
        borderRadius: 6,
        background: isOver ? '#e6f4ff' : isToday ? '#f0f7ff' : 'white',
        transition: 'border-color 0.15s, background 0.15s',
      }}
    >
      <div
        style={{
          fontWeight: isToday ? 700 : 400,
          marginBottom: 8,
          textAlign: 'center',
          fontSize: 12,
          color: isToday ? '#1677ff' : '#333',
        }}
      >
        {day.format('M/D')}
        <br />
        {day.format('ddd')}
      </div>
      {tasks.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}
    </div>
  )
}

function UnassignedColumn({ tasks }: { tasks: Task[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: '__unassigned__' })
  return (
    <div
      ref={setNodeRef}
      style={{
        width: 140,
        minHeight: 200,
        padding: 8,
        border: `2px dashed ${isOver ? '#1677ff' : '#d9d9d9'}`,
        borderRadius: 6,
        background: isOver ? '#e6f4ff' : '#fafafa',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          fontWeight: 400,
          marginBottom: 8,
          textAlign: 'center',
          fontSize: 12,
          color: '#888',
        }}
      >
        未配置
      </div>
      {tasks.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}
    </div>
  )
}

export default function Schedule() {
  const days = useMemo(() => getWeekDays(), [])

  const { data: tasks = [] } = useTasksForView({ limit: 200 })
  const updateTask = useUpdateTask()
  const queryClient = useQueryClient()
  const viewQueryKey = ['tasks-view', { limit: 200 }]

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const tasksByDate = useMemo(() => {
    const map: Record<string, Task[]> = { __unassigned__: [] }
    for (const day of days) map[day.format('YYYY-MM-DD')] = []
    for (const task of tasks) {
      // start_date が ISO 日時（"...T..."）を含む場合に備え日付部分のみをキーにする（issue #30）
      const key = task.start_date ? task.start_date.slice(0, 10) : '__unassigned__'
      if (key in map) map[key].push(task)
      else map['__unassigned__'].push(task)
    }
    return map
  }, [tasks, days])

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over) return
    const taskId = active.id as string
    const task = active.data.current?.task as Task | undefined
    const newDate = over.id === '__unassigned__' ? null : (over.id as string)
    const currentDate = task?.start_date ?? null
    if (newDate === currentDate) return
    // 楽観的更新でドロップを即時反映し、失敗時はロールバックする（issue #37）
    const previous = queryClient.getQueryData<Task[]>(viewQueryKey)
    queryClient.setQueryData<Task[]>(viewQueryKey, (old = []) =>
      old.map((t) => (t.id === taskId ? { ...t, start_date: newDate } : t)),
    )
    updateTask.mutate(
      { id: taskId, start_date: newDate },
      {
        onError: () => queryClient.setQueryData(viewQueryKey, previous),
        onSettled: () => void queryClient.invalidateQueries({ queryKey: ['tasks-view'] }),
      },
    )
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          スケジュール — 週次ビュー
        </Typography.Title>
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8 }}>
          <UnassignedColumn tasks={tasksByDate['__unassigned__'] ?? []} />
          {days.map((day) => (
            <DateColumn
              key={day.format('YYYY-MM-DD')}
              day={day}
              tasks={tasksByDate[day.format('YYYY-MM-DD')] ?? []}
            />
          ))}
        </div>
      </Space>
    </DndContext>
  )
}
