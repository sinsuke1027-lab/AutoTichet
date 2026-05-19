import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import type { Task, TaskListResponse, UserProfile } from '../lib/api'

interface ViewFilters {
  due_date_gte?: string
  due_date_lte?: string
  project_id?: string
  assignee_ids?: string[]
  status?: string
  limit?: number
  enabled?: boolean
}

export function useTasksForView(filters: ViewFilters) {
  return useQuery<Task[]>({
    queryKey: ['tasks-view', filters],
    enabled: filters.enabled ?? true,
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.due_date_gte) params.set('due_date_gte', filters.due_date_gte)
      if (filters.due_date_lte) params.set('due_date_lte', filters.due_date_lte)
      if (filters.project_id) params.set('project_id', filters.project_id)
      if (filters.status) params.set('status', filters.status)
      params.set('limit', String(filters.limit ?? 200))
      filters.assignee_ids?.forEach((id) => params.append('assignee_ids', id))
      const res = await api.get<TaskListResponse>(`/tasks?${params}`)
      return res.data.items
    },
  })
}

export function useUsers() {
  return useQuery<UserProfile[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await api.get<UserProfile[]>('/users')
      return res.data
    },
  })
}
