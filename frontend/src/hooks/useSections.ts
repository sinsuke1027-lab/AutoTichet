import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { type Section, type SectionCreate } from '../lib/api'

export function useSections(projectId: string | undefined) {
  return useQuery<Section[]>({
    queryKey: ['sections', projectId],
    queryFn: () =>
      api.get(`/projects/${projectId}/sections`).then((r) => r.data),
    enabled: !!projectId,
  })
}

export function useCreateSection(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SectionCreate) =>
      api.post(`/projects/${projectId}/sections`, body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sections', projectId] }),
  })
}

export function useDeleteSection(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sectionId: string) =>
      api.delete(`/projects/${projectId}/sections/${sectionId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sections', projectId] }),
  })
}
