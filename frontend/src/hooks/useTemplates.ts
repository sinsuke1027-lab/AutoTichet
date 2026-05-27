import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface TemplateSubtask {
  title: string
  description?: string | null
  priority?: string
  due_date_offset_days?: number
}

export interface TemplateData {
  title: string
  description?: string | null
  priority?: string
  visibility?: string
  tags?: string[]
  estimated_hours?: number | null
  due_date_offset_days?: number
  subtasks?: TemplateSubtask[]
}

export interface TemplateResponse {
  id: string
  name: string
  description: string | null
  template_data: TemplateData
  created_by: string
  created_at: string
  updated_at: string
}

export interface TemplateCreate {
  name: string
  description?: string | null
  template_data: TemplateData
}

export interface TemplateApplyRequest {
  base_date?: string | null
  project_id?: string | null
  section_id?: string | null
  assignee_id?: string | null
}

export interface TemplateApplyResponse {
  task_id: string
  subtask_ids: string[]
}

export function useTemplates() {
  return useQuery<TemplateResponse[]>({
    queryKey: ['templates'],
    queryFn: async () => {
      const { data } = await api.get('/templates')
      return data
    },
  })
}

export function useCreateTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: TemplateCreate) => {
      const { data } = await api.post<TemplateResponse>('/templates', body)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export function useUpdateTemplate(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<TemplateCreate>) => {
      const { data } = await api.put<TemplateResponse>(`/templates/${id}`, body)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/templates/${id}`)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export function useApplyTemplate() {
  return useMutation<
    TemplateApplyResponse,
    Error,
    { id: string; body: TemplateApplyRequest }
  >({
    mutationFn: async ({ id, body }) => {
      const { data } = await api.post<TemplateApplyResponse>(
        `/templates/${id}/apply`,
        body
      )
      return data
    },
  })
}
