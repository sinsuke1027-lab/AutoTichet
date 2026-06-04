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
  SettingOutlined,
  FileTextOutlined,
  UserOutlined,
  SearchOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { loginRequest } from './lib/msal'
import { useAuthStore } from './store/useAuthStore'
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
import AdminPage from './pages/Admin'
import TemplatesPage from './pages/Templates'
import MyPage from './pages/MyPage'
import HelpPage from './pages/Help'
import WorkloadAlertBadge from './components/WorkloadAlertBadge'
import CommandPalette from './components/CommandPalette'
import HelpDrawer from './components/HelpDrawer'
import ProjectContextSelector from './components/ProjectContextSelector'
import { useSearchStore } from './store/useSearchStore'
import DevLogin, { DEV_USER_KEY } from './pages/DevLogin'

const { Header, Content, Sider } = Layout

const DEV_BYPASS = import.meta.env.VITE_DEV_BYPASS_AUTH === 'true'

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
  { key: '/mypage', icon: <UserOutlined />, label: 'マイページ' },
  { key: '/tasks', icon: <CheckSquareOutlined />, label: 'タスク一覧' },
  { key: '/projects', icon: <ProjectOutlined />, label: 'プロジェクト' },
  { key: '/board', icon: <AppstoreOutlined />, label: 'カンバン' },
  { key: '/calendar', icon: <ScheduleOutlined />, label: 'カレンダー' },
  { key: '/gantt', icon: <BarChartOutlined />, label: 'ガント' },
  { key: '/schedule', icon: <CalendarOutlined />, label: 'スケジュール' },
  { key: '/workload', icon: <TeamOutlined />, label: 'ワークロード' },
  { key: '/templates', icon: <FileTextOutlined />, label: 'テンプレート' },
  { key: '/import', icon: <UploadOutlined />, label: 'データインポート' },
  { key: '/help', icon: <QuestionCircleOutlined />, label: 'ヘルプ' },
]

const PAGE_HELP_KEY: Record<string, string> = {
  '/': 'dashboard',
  '/mypage': 'mypage',
  '/tasks': 'tasks',
  '/projects': 'projects',
  '/board': 'board',
  '/calendar': 'calendar',
  '/gantt': 'gantt',
  '/schedule': 'schedule',
  '/workload': 'workload',
  '/templates': 'templates',
  '/import': 'import',
  '/admin': 'admin',
}

function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const roles = useAuthStore((s) => s.roles)
  const displayName = useAuthStore((s) => s.displayName)
  const clearUser = useAuthStore((s) => s.clearUser)
  const navItemsWithAdmin = [
    ...NAV_ITEMS,
    ...(roles.includes('admin')
      ? [{ key: '/admin', icon: <SettingOutlined />, label: '管理設定' }]
      : []),
  ]

  const selectedKey =
    navItemsWithAdmin.find((item) => item.key !== '/' && location.pathname.startsWith(item.key))
      ?.key ?? '/'

  const helpPageKey = PAGE_HELP_KEY[selectedKey] ?? PAGE_HELP_KEY[location.pathname] ?? ''

  const { setOpen: openSearch } = useSearchStore()

  function handleDevLogout() {
    sessionStorage.removeItem(DEV_USER_KEY)
    clearUser()
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          color: 'white',
          fontSize: 18,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span>AutoTicket</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {DEV_BYPASS && (
            <>
              <span style={{ color: 'rgba(255,255,255,0.65)', fontSize: 13 }}>
                [DEV] {displayName}
              </span>
              <Button
                size="small"
                onClick={handleDevLogout}
                style={{ color: 'white', borderColor: 'rgba(255,255,255,0.4)', background: 'transparent' }}
              >
                ログアウト
              </Button>
            </>
          )}
          <Button
            icon={<SearchOutlined />}
            type="text"
            style={{ color: 'white' }}
            title="検索 (Ctrl+K)"
            onClick={() => openSearch(true)}
          />
          <WorkloadAlertBadge />
        </div>
      </Header>
      <Layout>
        <Sider width={220} theme="light">
          <ProjectContextSelector />
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            style={{ height: '100%', borderRight: 0 }}
            items={navItemsWithAdmin}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mypage" element={<MyPage />} />
            <Route path="/tasks" element={<TaskList />} />
            <Route path="/tasks/:id" element={<TaskDetail />} />
            <Route path="/projects" element={<ProjectList />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/board" element={<Board />} />
            <Route path="/calendar" element={<CalendarView />} />
            <Route path="/gantt" element={<GanttView />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/workload" element={<Workload />} />
            <Route path="/templates" element={<TemplatesPage />} />
            <Route path="/import" element={<ImportPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/help" element={<HelpPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Content>
      </Layout>
      <CommandPalette />
      {helpPageKey && location.pathname !== '/help' && <HelpDrawer pageKey={helpPageKey} />}
    </Layout>
  )
}

function MsalGuard() {
  const isAuthenticated = useIsAuthenticated()
  if (!isAuthenticated) return <LoginPage />
  return <AppLayout />
}

function DevGuard() {
  const userId = useAuthStore((s) => s.userId)
  if (!userId) return <DevLogin />
  return <AppLayout />
}

export default function App() {
  if (DEV_BYPASS) return <DevGuard />
  return <MsalGuard />
}
