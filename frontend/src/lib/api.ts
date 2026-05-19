import axios from 'axios'
import { msalInstance, loginRequest } from './msal'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(async (config) => {
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
  visibility: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface TaskListResponse {
  items: Task[]
  total: number
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
