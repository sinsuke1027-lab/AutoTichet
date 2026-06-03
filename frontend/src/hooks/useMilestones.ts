import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  type Milestone,
  type MilestoneCreate,
  type MilestoneUpdate,
  createMilestone,
  deleteMilestone,
  getMilestones,
  toggleMilestoneComplete,
  updateMilestone,
} from '../lib/api'

export function useMilestones(projectId: string) {
  return useQuery<Milestone[]>({
    queryKey: ['milestones', projectId],
    queryFn: () => getMilestones(projectId),
    enabled: !!projectId,
  })
}

export function useCreateMilestone(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MilestoneCreate) => createMilestone(projectId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}

export function useUpdateMilestone(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ milestoneId, body }: { milestoneId: string; body: MilestoneUpdate }) =>
      updateMilestone(projectId, milestoneId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}

export function useToggleComplete(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (milestoneId: string) => toggleMilestoneComplete(projectId, milestoneId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}

export function useDeleteMilestone(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (milestoneId: string) => deleteMilestone(projectId, milestoneId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] })
    },
  })
}
