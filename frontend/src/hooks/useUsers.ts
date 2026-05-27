import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

interface UserSummary {
  user_id: string
  display_name: string
  role: string
}

export function useUsers() {
  return useQuery<UserSummary[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await api.get<UserSummary[]>('/users')
      return data
    },
  })
}
