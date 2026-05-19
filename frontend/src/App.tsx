import { useMsal, useIsAuthenticated } from '@azure/msal-react'
import { Navigate, Route, Routes, useNavigate, useLocation } from 'react-router-dom'
import { Button, Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  CheckSquareOutlined,
  ProjectOutlined,
  CalendarOutlined,
  TeamOutlined,
  UploadOutlined,
  AppstoreOutlined,
  ScheduleOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { loginRequest } from './lib/msal'
import Dashboard from './pages/Dashboard'
import TaskList from './pages/Tasks'
import TaskDetail from './pages/Tasks/TaskDetail'
import Schedule from './pages/Schedule'
import Workload from './pages/Workload'
import ProjectList from './pages/Projects/List'
import ProjectDetail from './pages/Projects'
import ImportPage from './pages/Import'
import Board from './pages/Board'
import CalendarView from './pages/Calendar'
import GanttView from './pages/Gantt'

const { Header, Content, Sider } = Layout

function LoginPage() {
  const { instance } = useMsal()
  return (
    <div style={{ textAlign: 'center', paddingTop: 100 }}>
      <Typography.Title>AutoTicket</Typography.Title>
      <Button type="primary" size="large" onClick={() => instance.loginRedirect(loginRequest)}>
        Microsoft アカウントでログイン
      </Button>
    </div>
  )
}

const NAV_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'ダッシュボード' },
  { key: '/tasks', icon: <CheckSquareOutlined />, label: 'タスク一覧' },
  { key: '/projects', icon: <ProjectOutlined />, label: 'プロジェクト' },
  { key: '/board', icon: <AppstoreOutlined />, label: 'カンバン' },
  { key: '/calendar', icon: <ScheduleOutlined />, label: 'カレンダー' },
  { key: '/gantt', icon: <BarChartOutlined />, label: 'ガント' },
  { key: '/schedule', icon: <CalendarOutlined />, label: 'スケジュール' },
  { key: '/workload', icon: <TeamOutlined />, label: 'ワークロード' },
  { key: '/import', icon: <UploadOutlined />, label: 'データインポート' },
]

function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedKey =
    NAV_ITEMS.find((item) => item.key !== '/' && location.pathname.startsWith(item.key))?.key ??
    '/'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ color: 'white', fontSize: 18, padding: '0 24px' }}>AutoTicket</Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            style={{ height: '100%', borderRight: 0 }}
            items={NAV_ITEMS}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tasks" element={<TaskList />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/projects" element={<ProjectList />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/board" element={<Board />} />
            <Route path="/calendar" element={<CalendarView />} />
            <Route path="/gantt" element={<GanttView />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/workload" element={<Workload />} />
            <Route path="/import" element={<ImportPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

export default function App() {
  const isAuthenticated = useIsAuthenticated()
  if (!isAuthenticated) return <LoginPage />
  return <AppLayout />
}
