import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { Task, TaskListResponse } from '../lib/api'

interface TaskFilters {
  status?: string
  assignee?: string
  project_id?: string
  tag?: string
  limit?: number
  offset?: number
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
    },
  })
}

export function useUpdateTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: Partial<Task> & { id: string }) => {
      const { data } = await api.put(`/tasks/${id}`, body)
      return data
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task', id] })
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
    },
  })
}
