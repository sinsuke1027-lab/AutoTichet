import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import type { SimilarTask } from '../lib/api'

export function useSimilarTasks(title: string) {
  const [debounced, setDebounced] = useState(title)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(title), 500)
    return () => clearTimeout(timer)
  }, [title])

  return useQuery<SimilarTask[]>({
    queryKey: ['similar-tasks', debounced],
    queryFn: async () => {
      const { data } = await api.get<SimilarTask[]>('/tasks/similar', {
        params: { q: debounced },
      })
      return data
    },
    enabled: debounced.length >= 3,
  })
}
