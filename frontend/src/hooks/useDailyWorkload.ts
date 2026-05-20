import { useQuery } from '@tanstack/react-query'
import api, { type DailyWorkloadItem } from '../lib/api'

export function useDailyWorkload() {
  return useQuery<DailyWorkloadItem[]>({
    queryKey: ['daily-workload'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/daily-workload')
      return data
    },
    staleTime: 5 * 60 * 1000,
  })
}
