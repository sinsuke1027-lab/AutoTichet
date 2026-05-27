import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export function useAdminTags() {
  return useQuery<string[]>({
    queryKey: ['admin-tags'],
    queryFn: async () => {
      const { data } = await api.get<string[]>('/admin/tags')
      return data
    },
  })
}

export function useRenameTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ tag, newName }: { tag: string; newName: string }) => {
      await api.patch(`/admin/tags/${encodeURIComponent(tag)}`, { new_name: newName })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tags'] })
      qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
  })
}

export function useDeleteTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (tag: string) => {
      await api.delete(`/admin/tags/${encodeURIComponent(tag)}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tags'] })
      qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
  })
}
