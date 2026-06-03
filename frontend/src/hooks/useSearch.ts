import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type SearchResponse, searchAll } from '../lib/api'

export function useSearch(input: string) {
  const [q, setQ] = useState(input)

  useEffect(() => {
    const timer = setTimeout(() => setQ(input), 300)
    return () => clearTimeout(timer)
  }, [input])

  return useQuery<SearchResponse>({
    queryKey: ['search', q],
    queryFn: () => searchAll(q),
    enabled: q.length >= 2,
    staleTime: 0,
  })
}
