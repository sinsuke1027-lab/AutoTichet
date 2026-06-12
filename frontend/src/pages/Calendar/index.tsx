import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, dateFnsLocalizer } from 'react-big-calendar'
import type { EventPropGetter, DateCellWrapperProps } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay, startOfMonth, endOfMonth } from 'date-fns'
import { ja } from 'date-fns/locale/ja'
import { Select, Space, Typography } from 'antd'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { useTasksForView, useUsers } from '../../hooks/useTasksForView'
import { useProjects } from '../../hooks/useProjects'
import { parseLocalDate } from '../../lib/date'
import type { Task } from '../../lib/api'

const { Title } = Typography

const locales = { ja }
const localizer = dateFnsLocalizer({ format, parse, startOfWeek, getDay, locales })

const RBC_MESSAGES = {
  next: '次',
  previous: '前',
  today: '今日',
  month: '月',
  week: '週',
  day: '日',
  noEventsInRange: 'この期間にタスクはありません',
}

interface CalEvent {
  id: string
  title: string
  start: Date
  end: Date
  allDay: boolean
  resource: Task
}

function assigneeColor(userId: string | null): string {
  if (!userId) return '#1677ff'
  let hash = 0
  for (let i = 0; i < userId.length; i++) {
    hash = userId.charCodeAt(i) + ((hash << 5) - hash)
  }
  return `hsl(${Math.abs(hash) % 360}, 65%, 50%)`
}

export default function CalendarView() {
  const navigate = useNavigate()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [projectId, setProjectId] = useState<string | undefined>()
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])

  const { data: projects = [] } = useProjects()
  const { data: users = [] } = useUsers({ scope: 'visible' })

  const { monthStart, monthEnd } = useMemo(() => ({
    monthStart: startOfMonth(currentDate),
    monthEnd: endOfMonth(currentDate),
  }), [currentDate])

  const { data: tasks = [] } = useTasksForView({
    due_date_gte: format(monthStart, 'yyyy-MM-dd'),
    due_date_lte: format(monthEnd, 'yyyy-MM-dd'),
    project_id: projectId,
    assignee_ids: assigneeIds.length > 0 ? assigneeIds : undefined,
  })

  const events = useMemo<CalEvent[]>(() => {
    return tasks.map((task) => {
      const end = task.due_date ? parseLocalDate(task.due_date) : new Date()
      const hasRange = !!task.start_date
      const start = hasRange ? parseLocalDate(task.start_date!) : end
      return {
        id: task.id,
        title: task.title,
        start,
        end,
        allDay: !hasRange,
        resource: task,
      }
    })
  }, [tasks])

  const taskCountByDate = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const task of tasks) {
      if (task.due_date) counts[task.due_date] = (counts[task.due_date] ?? 0) + 1
    }
    return counts
  }, [tasks])

  const DensityCellWrapper = useCallback(
    ({ value, children }: DateCellWrapperProps) => {
      const key = format(value, 'yyyy-MM-dd')
      const count = taskCountByDate[key] ?? 0
      const bg =
        count === 0 ? undefined
        : count <= 2 ? '#e6f4ff'
        : count <= 5 ? '#91caff'
        : 'rgba(22, 119, 255, 0.15)'
      return <div style={{ flex: 1, minHeight: 'inherit', background: bg }}>{children}</div>
    },
    [taskCountByDate]
  )

  const eventPropGetter = useCallback<EventPropGetter<CalEvent>>(
    (event) => {
      return { style: { backgroundColor: assigneeColor(event.resource.assignee_id ?? null) } }
    },
    []
  )

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space align="center" wrap>
        <Title level={3} style={{ margin: 0 }}>
          カレンダー
        </Title>
        <Select
          allowClear
          placeholder="プロジェクト（任意）"
          style={{ width: 200 }}
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          onChange={(v) => setProjectId(v)}
        />
        <Select
          mode="multiple"
          allowClear
          placeholder="担当者（未選択: 全員）"
          style={{ minWidth: 240 }}
          options={users.map((u) => ({ value: u.user_id, label: u.display_name }))}
          onChange={(v: string[]) => setAssigneeIds(v)}
        />
      </Space>

      <Calendar
        localizer={localizer}
        events={events}
        views={['month']}
        defaultView="month"
        date={currentDate}
        onNavigate={setCurrentDate}
        style={{ height: 620 }}
        eventPropGetter={eventPropGetter}
        onSelectEvent={(event) => navigate(`/tasks/${(event as CalEvent).id}`)}
        messages={RBC_MESSAGES}
        components={{ dateCellWrapper: DensityCellWrapper }}
      />
    </Space>
  )
}
