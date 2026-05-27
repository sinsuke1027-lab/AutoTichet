import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface Comment {
  id: string
  task_id: string
  author_id: string
  content: string
  mentions: string[]
  sharepoint_links: string[]
  created_at: string
  updated_at: string
}

interface WorkHour {
  id: string
  task_id: string
  user_id: string
  estimated_hours: number | null
  actual_hours: number | null
  notes: string | null
  recorded_at: string
}

interface Subtask {
  id: string
  title: string
  status: string
  priority: string
}

export function useComments(taskId: string) {
  return useQuery<Comment[]>({
    queryKey: ['comments', taskId],
    queryFn: () => api.get(`/tasks/${taskId}/comments`).then((r) => r.data),
  })
}

export function useCreateComment(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) =>
      api.post(`/tasks/${taskId}/comments`, { content }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments', taskId] }),
  })
}

export function useWorkHours(taskId: string) {
  return useQuery<WorkHour[]>({
    queryKey: ['work-hours', taskId],
    queryFn: () => api.get(`/tasks/${taskId}/work-hours`).then((r) => r.data),
  })
}

export function useCreateWorkHour(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { estimated_hours?: number; actual_hours?: number; notes?: string }) =>
      api.post(`/tasks/${taskId}/work-hours`, body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['work-hours', taskId] }),
  })
}

export function useSubtasks(taskId: string) {
  return useQuery<Subtask[]>({
    queryKey: ['subtasks', taskId],
    queryFn: () => api.get(`/tasks/${taskId}/subtasks`).then((r) => r.data),
  })
}

export function useCreateSubtask(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) =>
      api
        .post('/tasks', {
          title,
          parent_task_id: taskId,
          status: 'not_started',
          visibility: 'team',
        })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subtasks', taskId] }),
  })
}

export function useUpdateSubtaskStatus(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.put(`/tasks/${id}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subtasks', taskId] }),
  })
}

export function useGenerateSubtasks(taskId: string) {
  return useMutation<{ suggested_titles: string[] }, Error>({
    mutationFn: () =>
      api.post(`/tasks/${taskId}/generate-subtasks`).then((r) => r.data),
  })
}
