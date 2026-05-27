import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { type Task, type TaskListResponse } from '../lib/api'

interface TaskFilters {
  status?: string
  assignee?: string
  project_id?: string
  section_id?: string
  q?: string
  tag?: string
  limit?: number
  offset?: number
  my_tasks_only?: boolean
}

export function useTasks(filters: TaskFilters = {}) {
  return useQuery<TaskListResponse>({
    queryKey: ['tasks', filters],
    queryFn: async () => {
      const { data } = await api.get('/tasks', { params: filters })
      return data
    },
  })
}

export function useTask(id: string) {
  return useQuery<Task>({
    queryKey: ['task', id],
    queryFn: async () => {
      const { data } = await api.get(`/tasks/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCreateTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<Task> & { title: string }) => {
      const { data } = await api.post('/tasks', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks-view'] })
    },
  })
}

export function useUpdateTask(taskId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<Task> & { id?: string }) => {
      const id = taskId ?? body.id
      if (!id) throw new Error('task id is required')
      const { id: _id, ...rest } = body
      const { data } = await api.put(`/tasks/${id}`, rest)
      return data
    },
    onSuccess: (_, body) => {
      const id = taskId ?? body.id
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks-view'] })
      if (id) queryClient.invalidateQueries({ queryKey: ['task', id] })
    },
  })
}

export function useDeleteTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/tasks/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks-view'] })
    },
  })
}
