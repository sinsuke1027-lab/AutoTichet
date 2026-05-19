import { useQuery } from '@tanstack/react-query'
import api, { DashboardSummary, WorkloadItem, TodayTaskItem, OverdueTaskItem } from '../lib/api'

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
