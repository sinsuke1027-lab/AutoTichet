import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { endOfWeek, format, startOfWeek, subDays } from 'date-fns'
import api, {
  type AdminUser,
  type UserProfileUpdate,
  type WeeklyWorkSummary,
  getMyWeeklySummary,
  updateMyProfile,
} from '../lib/api'
import { useTasks } from './useTasks'

export function useMyProfile() {
  return useQuery<AdminUser>({
    queryKey: ['my-profile'],
    queryFn: async () => {
      const { data } = await api.get<AdminUser>('/users/me/profile')
      return data
    },
  })
}

export function useUpdateMyProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UserProfileUpdate) => updateMyProfile(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['my-profile'] })
    },
  })
}

export function useMyWeeklySummary() {
  return useQuery<WeeklyWorkSummary[]>({
    queryKey: ['my-weekly-summary'],
    queryFn: getMyWeeklySummary,
    staleTime: 5 * 60 * 1000,
  })
}

export function useMyWeeklyTasks() {
  const now = new Date()
  const weekStart = format(startOfWeek(now, { weekStartsOn: 1 }), 'yyyy-MM-dd')
  const weekEnd = format(endOfWeek(now, { weekStartsOn: 1 }), 'yyyy-MM-dd')
  return useTasks({
    my_tasks_only: true,
    due_date_gte: weekStart,
    due_date_lte: weekEnd,
    limit: 20,
  })
}

export function useMyOverdueTasks() {
  const yesterday = format(subDays(new Date(), 1), 'yyyy-MM-dd')
  return useTasks({
    my_tasks_only: true,
    due_date_lte: yesterday,
    limit: 10,
  })
}
