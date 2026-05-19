import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Gantt, ViewMode } from 'gantt-task-react'
import type { Task as GanttTask } from 'gantt-task-react'
import 'gantt-task-react/dist/index.css'
import { Alert, Button, Modal, Select, Space, Spin, Typography } from 'antd'
import { useProjects } from '../../hooks/useProjects'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useReschedule } from '../../hooks/useReschedule'
import api from '../../lib/api'
import type { DependencyResponse, Task } from '../../lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const { Title } = Typography

function toGanttTask(task: Task, depMap: Record<string, string[]>): GanttTask {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const end = task.due_date ? new Date(task.due_date) : new Date(today.getTime() + 86400000)
  const start = task.start_date ? new Date(task.start_date) : end
  const progress =
    task.status === 'completed' ? 100
    : task.status === 'in_progress' ? 50
    : 0
  return {
    id: task.id,
    name: task.title,
    start,
    end,
    progress,
    type: 'task',
    dependencies: depMap[task.id] ?? [],
    isDisabled: false,
  }
}

export default function GanttView() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState<string | undefined>()
  const [addDepTarget, setAddDepTarget] = useState<string | null>(null)
  const [addDepModal, setAddDepModal] = useState(false)
  const [selectedDepId, setSelectedDepId] = useState<string | undefined>()

  const { data: projects = [] } = useProjects()
  const { data: tasks = [], isLoading } = useTasksForView({
    project_id: projectId,
    limit: 200,
  })
  const reschedule = useReschedule()

  // 依存関係を並列取得
  const { data: depMap = {} } = useQuery<Record<string, string[]>>({
    queryKey: ['gantt-deps', projectId, tasks.map((t) => t.id).join(',')],
    enabled: tasks.length > 0 && !!projectId,
    queryFn: async () => {
      const results = await Promise.all(
        tasks.map((t) =>
          api
            .get<DependencyResponse[]>(`/tasks/${t.id}/dependencies`)
            .then((r) => ({ taskId: t.id, deps: r.data }))
        )
      )
      const map: Record<string, string[]> = {}
      for (const { taskId, deps } of results) {
        map[taskId] = deps.map((d) => d.depends_on_task_id)
      }
      return map
    },
  })

  // 依存関係追加
  const addDep = useMutation({
    mutationFn: async ({ taskId, dependsOn }: { taskId: string; dependsOn: string }) => {
      await api.post(`/tasks/${taskId}/dependencies`, { depends_on_task_id: dependsOn })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gantt-deps'] })
      setAddDepModal(false)
      setSelectedDepId(undefined)
    },
  })

  const ganttTasks = useMemo(
    () => tasks.map((t) => toGanttTask(t, depMap)),
    [tasks, depMap]
  )

  const handleDateChange = (ganttTask: GanttTask) => {
    const newStart = ganttTask.start.toISOString().slice(0, 10)
    const newEnd = ganttTask.end.toISOString().slice(0, 10)
    reschedule.mutate({
      taskId: ganttTask.id,
      body: { new_start_date: newStart, new_due_date: newEnd },
    })
  }

  if (!projectId) {
    return (
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Space align="center">
          <Title level={3} style={{ margin: 0 }}>ガント</Title>
          <Select
            placeholder="プロジェクトを選択してください"
            style={{ width: 300 }}
            options={projects.map((p) => ({ value: p.id, label: p.name }))}
            onChange={(v) => setProjectId(v)}
          />
        </Space>
        <Alert message="ガントを表示するにはプロジェクトを選択してください" type="info" showIcon />
      </Space>
    )
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space align="center" wrap>
        <Title level={3} style={{ margin: 0 }}>ガント</Title>
        <Select
          value={projectId}
          style={{ width: 240 }}
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          onChange={(v) => setProjectId(v)}
        />
      </Space>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : ganttTasks.length === 0 ? (
        <Alert message="このプロジェクトにタスクがありません" type="info" showIcon />
      ) : (
        <>
          <Gantt
            tasks={ganttTasks}
            viewMode={ViewMode.Day}
            onDateChange={handleDateChange}
            onDoubleClick={(task) => navigate(`/tasks/${task.id}`)}
            columnWidth={65}
            listCellWidth="200px"
            locale="ja"
          />
          <Space wrap>
            <Button
              onClick={() => {
                if (ganttTasks[0]) {
                  setAddDepTarget(ganttTasks[0].id)
                  setAddDepModal(true)
                }
              }}
              disabled={ganttTasks.length === 0}
            >
              依存関係を追加
            </Button>
          </Space>
        </>
      )}

      <Modal
        title="依存関係を追加"
        open={addDepModal}
        onOk={() => {
          if (addDepTarget && selectedDepId) {
            addDep.mutate({ taskId: addDepTarget, dependsOn: selectedDepId })
          }
        }}
        onCancel={() => {
          setAddDepModal(false)
          setSelectedDepId(undefined)
        }}
        okText="追加"
        cancelText="キャンセル"
        confirmLoading={addDep.isPending}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="依存元タスク（このタスクが完了後に開始）"
            style={{ width: '100%' }}
            options={tasks.map((t) => ({ value: t.id, label: t.title }))}
            value={addDepTarget ?? undefined}
            onChange={setAddDepTarget}
          />
          <Select
            placeholder="依存先タスク（depends_on）"
            style={{ width: '100%' }}
            options={tasks
              .filter((t) => t.id !== addDepTarget)
              .map((t) => ({ value: t.id, label: t.title }))}
            value={selectedDepId}
            onChange={setSelectedDepId}
          />
        </Space>
      </Modal>
    </Space>
  )
}
