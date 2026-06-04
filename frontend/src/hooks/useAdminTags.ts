import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export interface DepartmentTagResponse {
  name: string
  description: string | null
}

export function useAdminTags() {
  return useQuery<DepartmentTagResponse[]>({
    queryKey: ['admin-tags'],
    queryFn: async () => {
      const { data } = await api.get<DepartmentTagResponse[]>('/admin/tags')
      return data
    },
  })
}

export function useCreateTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description: string | null }) => {
      const { data } = await api.post<DepartmentTagResponse>('/admin/tags', body)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tags'] })
    },
  })
}

export function useUpdateTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      tag,
      newName,
      description,
    }: {
      tag: string
      newName?: string
      description: string | null
    }) => {
      await api.patch(`/admin/tags/${encodeURIComponent(tag)}`, {
        new_name: newName ?? null,
        description,
      })
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
