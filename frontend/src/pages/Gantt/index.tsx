import { useCallback, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Gantt, ViewMode } from 'gantt-task-react'
import type { Task as GanttTask } from 'gantt-task-react'
import 'gantt-task-react/dist/index.css'
import {
  Alert,
  Button,
  Card,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Typography,
} from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import { useProjects } from '../../hooks/useProjects'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useReschedule } from '../../hooks/useReschedule'
import api from '../../lib/api'
import { parseLocalDate } from '../../lib/date'
import type { DependencyResponse, Task } from '../../lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const { Title, Text } = Typography

function toLocalDate(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// taskId → [{id, depends_on_task_id}]  (depMap に id も持たせて削除に使う)
type DepMapFull = Record<string, DependencyResponse[]>

function toGanttTask(task: Task, depMap: DepMapFull): GanttTask {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const end = task.due_date ? parseLocalDate(task.due_date) : new Date(today)
  const start = task.start_date ? parseLocalDate(task.start_date) : end
  const safeEnd = start > end ? start : end
  const progress =
    task.status === 'completed' ? 100
    : task.status === 'in_progress' ? 50
    : 0
  return {
    id: task.id,
    name: task.title,
    start,
    end: safeEnd,
    progress,
    type: 'task',
    // gantt-task-react: dependencies = 「このタスクが待つ先行タスクID」
    // 先行タスク → このタスク の矢印が描かれる
    dependencies: (depMap[task.id] ?? []).map((d) => d.depends_on_task_id),
    isDisabled: false,
  }
}

export default function GanttView() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState<string | undefined>()
  const [addDepModal, setAddDepModal] = useState(false)
  const [addDepPredecessor, setAddDepPredecessor] = useState<string | undefined>() // 先行タスク (A)
  const [addDepSuccessor, setAddDepSuccessor] = useState<string | undefined>()   // 後続タスク (B)

  const { data: projects = [] } = useProjects({ scope: 'all' })
  const { data: tasks = [], isLoading } = useTasksForView({
    project_id: projectId,
    limit: 200,
    enabled: !!projectId,
  })
  const reschedule = useReschedule()

  const taskMap = useMemo(
    () => Object.fromEntries(tasks.map((t) => [t.id, t])),
    [tasks],
  )

  // 全タスクの依存関係を並列取得（id も含む）
  const { data: depMap = {} } = useQuery<DepMapFull>({
    queryKey: ['gantt-deps', projectId, [...tasks.map((t) => t.id)].sort().join(',')],
    enabled: tasks.length > 0 && !!projectId,
    queryFn: async () => {
      const results = await Promise.all(
        tasks.map((t) =>
          api
            .get<DependencyResponse[]>(`/tasks/${t.id}/dependencies`)
            .then((r) => ({ taskId: t.id, deps: r.data }))
        )
      )
      const map: DepMapFull = {}
      for (const { taskId, deps } of results) {
        map[taskId] = deps
      }
      return map
    },
  })

  // 全依存関係をフラットなリストに変換（削除UIで使用）
  const allDeps = useMemo(() => {
    const result: Array<{ id: string; successorId: string; predecessorId: string }> = []
    for (const [taskId, deps] of Object.entries(depMap)) {
      for (const dep of deps) {
        result.push({ id: dep.id, successorId: taskId, predecessorId: dep.depends_on_task_id })
      }
    }
    return result
  }, [depMap])

  // 依存関係追加
  // 先行タスク(A)が完了後に後続タスク(B)が開始 → B depends_on A
  // API: POST /tasks/{B}/dependencies { depends_on_task_id: A }
  const addDep = useMutation({
    mutationFn: async ({ predecessor, successor }: { predecessor: string; successor: string }) => {
      await api.post(`/tasks/${successor}/dependencies`, { depends_on_task_id: predecessor })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gantt-deps'] })
      setAddDepModal(false)
      setAddDepPredecessor(undefined)
      setAddDepSuccessor(undefined)
    },
  })

  // 依存関係削除
  const deleteDep = useMutation({
    mutationFn: async ({ taskId, depId }: { taskId: string; depId: string }) => {
      await api.delete(`/tasks/${taskId}/dependencies/${depId}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gantt-deps'] })
    },
  })

  const ganttTasks = useMemo(
    () => tasks.map((t) => toGanttTask(t, depMap)),
    [tasks, depMap]
  )

  // React StrictMode でガントライブラリのエフェクトが二重実行されると
  // mouseup リスナーが重複し onDateChange が複数回呼ばれる可能性があるため、
  // ref で同時実行を防ぐ
  const isReschedulingRef = useRef(false)
  const handleDateChange = useCallback((ganttTask: GanttTask) => {
    if (isReschedulingRef.current) return
    isReschedulingRef.current = true
    const newStart = toLocalDate(ganttTask.start)
    const newEnd = toLocalDate(ganttTask.end)
    reschedule.mutate(
      { taskId: ganttTask.id, body: { new_start_date: newStart, new_due_date: newEnd } },
      { onSettled: () => { isReschedulingRef.current = false } },
    )
  }, [reschedule])

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
                setAddDepPredecessor(undefined)
                setAddDepSuccessor(undefined)
                setAddDepModal(true)
              }}
            >
              依存関係を追加
            </Button>
          </Space>

          {/* 依存関係一覧・削除 */}
          {allDeps.length > 0 && (
            <Card
              title="依存関係一覧"
              size="small"
              style={{ marginTop: 8 }}
            >
              <List
                size="small"
                dataSource={allDeps}
                renderItem={(dep) => {
                  const predecessor = taskMap[dep.predecessorId]
                  const successor = taskMap[dep.successorId]
                  return (
                    <List.Item
                      actions={[
                        <Popconfirm
                          key="delete"
                          title="依存関係を削除"
                          description="この依存関係を削除しますか？"
                          onConfirm={() =>
                            deleteDep.mutate({ taskId: dep.successorId, depId: dep.id })
                          }
                          okText="削除"
                          okButtonProps={{ danger: true }}
                          cancelText="キャンセル"
                        >
                          <Button
                            icon={<DeleteOutlined />}
                            size="small"
                            danger
                            loading={deleteDep.isPending}
                          />
                        </Popconfirm>,
                      ]}
                    >
                      <Text>
                        {predecessor?.title ?? dep.predecessorId}
                        <Text type="secondary" style={{ margin: '0 8px' }}>→</Text>
                        {successor?.title ?? dep.successorId}
                      </Text>
                    </List.Item>
                  )
                }}
              />
            </Card>
          )}
        </>
      )}

      {/* 依存関係追加モーダル */}
      <Modal
        title="依存関係を追加"
        open={addDepModal}
        onOk={() => {
          if (addDepPredecessor && addDepSuccessor) {
            addDep.mutate({ predecessor: addDepPredecessor, successor: addDepSuccessor })
          }
        }}
        okButtonProps={{ disabled: !addDepPredecessor || !addDepSuccessor }}
        onCancel={() => {
          setAddDepModal(false)
          setAddDepPredecessor(undefined)
          setAddDepSuccessor(undefined)
        }}
        okText="追加"
        cancelText="キャンセル"
        confirmLoading={addDep.isPending}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
              先行タスク（このタスクが完了後に後続タスクが開始）
            </Text>
            <Select
              placeholder="先行タスクを選択"
              style={{ width: '100%' }}
              options={tasks
                .filter((t) => t.id !== addDepSuccessor)
                .map((t) => ({ value: t.id, label: t.title }))}
              value={addDepPredecessor}
              onChange={setAddDepPredecessor}
            />
          </div>
          <div style={{ textAlign: 'center' }}>
            <Text type="secondary">↓（矢印の向き：先行 → 後続）</Text>
          </div>
          <div>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
              後続タスク（先行タスクの完了後に開始するタスク）
            </Text>
            <Select
              placeholder="後続タスクを選択"
              style={{ width: '100%' }}
              options={tasks
                .filter((t) => t.id !== addDepPredecessor)
                .map((t) => ({ value: t.id, label: t.title }))}
              value={addDepSuccessor}
              onChange={setAddDepSuccessor}
            />
          </div>
        </Space>
      </Modal>
    </Space>
  )
}
