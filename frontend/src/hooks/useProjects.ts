import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { type Project, archiveProject, unarchiveProject } from '../lib/api'

export function useProjects(params: { includeArchived?: boolean; scope?: 'mine' | 'all' } = {}) {
  const { includeArchived = false, scope = 'mine' } = params
  return useQuery<Project[]>({
    queryKey: ['projects', { includeArchived, scope }],
    queryFn: async () => {
      const { data } = await api.get('/projects', {
        params: {
          ...(includeArchived ? { include_archived: true } : {}),
          scope,
        },
      })
      return data
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const { data } = await api.post('/projects', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useArchiveProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => archiveProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useUnarchiveProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => unarchiveProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
