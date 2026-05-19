import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useAddAssignee(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) =>
      api.post(`/tasks/${taskId}/assignees`, { user_id: userId, role: 'sub' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['task', taskId] }),
  })
}

export function useRemoveAssignee(taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => api.delete(`/tasks/${taskId}/assignees/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['task', taskId] }),
  })
}
