import { useMutation, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import api from '../lib/api'
import type { RescheduleRequest, RescheduleResponse } from '../lib/api'

export function useReschedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ taskId, body }: { taskId: string; body: RescheduleRequest }) => {
      const res = await api.post<RescheduleResponse>(`/tasks/${taskId}/reschedule`, body)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks-view'] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: () => {
      void message.error('リスケジュールに失敗しました')
    },
  })
}
