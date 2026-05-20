import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import type { AdminUser, AdminUserCreate, AdminUserUpdate } from '../lib/api'

export function useAdminUsers() {
  return useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const { data } = await api.get<AdminUser[]>('/admin/users')
      return data
    },
  })
}

export function useCreateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: AdminUserCreate) => {
      const { data } = await api.post<AdminUser>('/admin/users', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
}

export function useUpdateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, body }: { userId: string; body: AdminUserUpdate }) => {
      const { data } = await api.patch<AdminUser>(`/admin/users/${userId}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
}

export function useDeleteAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) => {
      await api.delete(`/admin/users/${userId}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
}
