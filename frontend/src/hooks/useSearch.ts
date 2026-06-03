import { useDeferredValue } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type SearchResponse, searchAll } from '../lib/api'

export function useSearch(input: string) {
  const q = useDeferredValue(input)
  return useQuery<SearchResponse>({
    queryKey: ['search', q],
    queryFn: () => searchAll(q),
    enabled: q.length >= 2,
    staleTime: 0,
  })
}
