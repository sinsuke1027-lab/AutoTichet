import axios from 'axios'
import { msalInstance, loginRequest } from './msal'

const DEV_BYPASS = import.meta.env.VITE_DEV_BYPASS_AUTH === 'true'
const DEV_USER_KEY = 'autoticket_dev_user'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(async (config) => {
  if (DEV_BYPASS) {
    const raw = sessionStorage.getItem(DEV_USER_KEY)
    if (raw) config.headers['X-Dev-User'] = raw
    return config
  }
  const accounts = msalInstance.getAllAccounts()
  if (accounts.length > 0) {
    try {
      const result = await msalInstance.acquireTokenSilent({
        ...loginRequest,
        account: accounts[0],
      })
      config.headers.Authorization = `Bearer ${result.accessToken}`
    } catch {
      await msalInstance.loginRedirect(loginRequest)
    }
  }
  return config
})

export default api

export interface Task {
  id: string
  title: string
  description: string | null
  status: string
  priority: string
  assignee_id: string | null
  due_date: string | null
  start_date?: string | null
  visibility: string
  tags: string[]
  project_id?: string | null
  section_id?: string | null
  parent_task_id?: string | null
  subtask_count?: number
  subtask_done_count?: number
  created_at: string
  updated_at: string
  risk_level?: 'high' | 'medium' | null
  order_index?: number
  recurrence_rule?: 'daily' | 'weekly' | 'monthly' | null
  recurrence_end_date?: string | null
  recurrence_origin_id?: string | null
  assignee_name?: string | null
  project_name?: string | null
}

export interface TaskListResponse {
  items: Task[]
  total: number
}

export interface StaleTaskItem {
  id: string
  title: string
  assignee_id: string | null
  due_date: string | null
  updated_at: string
  days_stale: number
}

export interface HourEstimate {
  avg_actual_hours: number | null
  min_actual_hours: number | null
  max_actual_hours: number | null
  task_count: number
}

export interface Project {
  id: string
  name: string
  description: string | null
  status: string
  created_by: string
  created_at: string
}

export interface DashboardSummary {
  total_tasks: number
  not_started: number
  in_progress: number
  completed: number
  overdue: number
  completion_rate: number
}

export interface WorkloadItem {
  user_id: string
  display_name: string
  estimated_hours: number
  capacity_hours: number
  overload: boolean
}

export interface TodayTaskItem {
  id: string
  title: string
  status: string
  priority: string
  assignee_id: string | null
}

export interface OverdueTaskItem {
  id: string
  title: string
  status: string
  due_date: string | null
  assignee_id: string | null
}

export interface Section {
  id: string
  project_id: string
  name: string
  order_index: number
  created_at: string
  updated_at: string
}

export interface SectionCreate {
  name: string
  order_index?: number
}

export interface ImportPreviewResponse {
  file_name: string
  projects: Array<{ name: string; will_create: boolean }>
  sections: Array<{ project: string; name: string; task_count: number }>
  tasks: { total: number; completed: number; with_subtasks: number; with_dependencies: number }
  warnings: string[]
}

export interface ImportResult {
  created_tasks: number
  created_sections: number
  skipped_duplicates: number
  errors: string[]
}

export interface DependencyResponse {
  id: string
  depends_on_task_id: string
}

export interface UserProfile {
  user_id: string
  display_name: string
  email: string | null
  role: string
  capacity_hours_per_day: number
  department_tags: string[]
}

export interface RescheduleRequest {
  new_start_date?: string | null
  new_due_date: string
}

export interface RescheduleResponse {
  updated_tasks: Task[]
}

export interface AdminUser {
  user_id: string
  display_name: string
  email: string | null
  role: string
  department_tags: string[]
  capacity_hours_per_day: number
}

export interface AdminUserCreate {
  user_id: string
  display_name: string
  email?: string | null
  role: string
  department_tags: string[]
  capacity_hours_per_day: number
}

export interface AdminUserUpdate {
  display_name?: string | null
  email?: string | null
  role?: string | null
  department_tags?: string[] | null
  capacity_hours_per_day?: number | null
}

export interface SimilarTask {
  id: string
  title: string
  status: string
  score: number
}

export interface DailyWorkloadItem {
  date: string
  total_hours: number
  capacity_hours: number
  overload: boolean
  task_count: number
}

export const getEstimateHours = async (tags: string[]): Promise<HourEstimate> => {
  const params = new URLSearchParams()
  tags.forEach(t => params.append('tags', t))
  const { data } = await api.get<HourEstimate>(`/tasks/estimate-hours?${params.toString()}`)
  return data
}

export interface ExtractedTask {
  is_task: boolean
  title: string
  assignee_name: string | null
  deadline: string | null
  priority: 'high' | 'medium' | 'low'
  category: string
  visibility: 'private' | 'team' | 'all'
  confidence_score: number
  source_type: string
}

export interface ExtractResult {
  tasks: ExtractedTask[]
  skipped_reason?: string
}

export const extractTasksFromText = async (
  text: string,
  sourceType: string,
): Promise<ExtractResult> => {
  const { data } = await api.post<ExtractResult>('/tasks/extract', {
    text,
    source_type: sourceType,
  })
  return data
}

export interface HandoverResponse {
  document: string
}

export const generateHandover = async (assigneeId?: string): Promise<HandoverResponse> => {
  const { data } = await api.post<HandoverResponse>('/tasks/generate-handover', {
    assignee_id: assigneeId ?? null,
  })
  return data
}

export async function archiveProject(id: string): Promise<Project> {
  const { data } = await api.patch<Project>(`/projects/${id}/archive`)
  return data
}

export async function unarchiveProject(id: string): Promise<Project> {
  const { data } = await api.patch<Project>(`/projects/${id}/unarchive`)
  return data
}

export async function deleteRecurrence(taskId: string): Promise<void> {
  await api.delete(`/tasks/${taskId}/recurrence`)
}

export interface UserProfileUpdate {
  display_name?: string | null
  capacity_hours_per_day?: number | null
  department_tags?: string[] | null
}

export interface WeeklyWorkSummary {
  week_start: string
  planned_hours: number
  actual_hours: number
  task_count: number
  completed_count: number
  overdue_count: number
}

export async function updateMyProfile(body: UserProfileUpdate): Promise<AdminUser> {
  const { data } = await api.patch<AdminUser>('/users/me', body)
  return data
}

export async function getMyWeeklySummary(): Promise<WeeklyWorkSummary[]> {
  const { data } = await api.get<WeeklyWorkSummary[]>('/dashboard/my-weekly-summary')
  return data
}

export interface TaskBulkUpdate {
  task_ids: string[]
  status?: string | null
  assignee_id?: string | null
}

export async function bulkUpdateTasks(body: TaskBulkUpdate): Promise<{ updated_count: number }> {
  const { data } = await api.patch<{ updated_count: number }>('/tasks/bulk', body)
  return data
}

// --- Milestone ---

export interface Milestone {
  id: string
  project_id: string
  title: string
  due_date: string        // "YYYY-MM-DD"
  completed: boolean
  completed_at: string | null
  created_at: string
}

export interface MilestoneCreate {
  title: string
  due_date: string
}

export interface MilestoneUpdate {
  title?: string
  due_date?: string
}

export async function getMilestones(projectId: string): Promise<Milestone[]> {
  const { data } = await api.get<Milestone[]>(`/projects/${projectId}/milestones`)
  return data
}

export async function createMilestone(projectId: string, body: MilestoneCreate): Promise<Milestone> {
  const { data } = await api.post<Milestone>(`/projects/${projectId}/milestones`, body)
  return data
}

export async function updateMilestone(
  projectId: string,
  milestoneId: string,
  body: MilestoneUpdate,
): Promise<Milestone> {
  const { data } = await api.put<Milestone>(
    `/projects/${projectId}/milestones/${milestoneId}`,
    body,
  )
  return data
}

export async function toggleMilestoneComplete(
  projectId: string,
  milestoneId: string,
): Promise<Milestone> {
  const { data } = await api.patch<Milestone>(
    `/projects/${projectId}/milestones/${milestoneId}/complete`,
  )
  return data
}

export async function deleteMilestone(projectId: string, milestoneId: string): Promise<void> {
  await api.delete(`/projects/${projectId}/milestones/${milestoneId}`)
}

// --- Search ---

export interface SearchResultItem {
  task_id: string
  project_id: string
  project_name: string
  title: string
  snippet: string
  match_type: 'title' | 'description' | 'comment'
}

export interface SearchResponse {
  items: SearchResultItem[]
  total: number
}

export async function searchAll(q: string, limit = 20): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>('/search', { params: { q, limit } })
  return data
}
