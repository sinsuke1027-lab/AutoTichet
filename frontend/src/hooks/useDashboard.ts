import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, {
  type DashboardSummary,
  type WorkloadItem,
  type TodayTaskItem,
  type OverdueTaskItem,
  type StaleTaskItem,
} from '../lib/api'

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/summary')
      return data
    },
  })
}

export function useTodayTasks() {
  return useQuery<TodayTaskItem[]>({
    queryKey: ['dashboard', 'today'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/today')
      return data
    },
  })
}

export function useOverdueTasks() {
  return useQuery<OverdueTaskItem[]>({
    queryKey: ['dashboard', 'overdue'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/overdue')
      return data
    },
  })
}

export function useWorkload() {
  return useQuery<WorkloadItem[]>({
    queryKey: ['dashboard', 'workload'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/workload')
      return data
    },
  })
}

export function useStaleTaskItems() {
  return useQuery<StaleTaskItem[]>({
    queryKey: ['dashboard', 'stale-tasks'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/stale-tasks')
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}

export function useArchiveTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (taskId: string) => {
      await api.patch(`/tasks/${taskId}`, { status: 'cancelled' })
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['dashboard', 'stale-tasks'] })
      void qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
