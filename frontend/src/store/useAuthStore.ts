import { create } from 'zustand'

const DEV_USER_KEY = 'autoticket_dev_user'

interface AuthState {
  userId: string | null
  displayName: string | null
  email: string | null
  roles: string[]
  setUser: (user: { userId: string; displayName: string; email: string; roles: string[] }) => void
  clearUser: () => void
}

function loadDevUser(): Partial<AuthState> {
  try {
    const raw = sessionStorage.getItem(DEV_USER_KEY)
    if (!raw) return {}
    const u = JSON.parse(raw) as { userId: string; displayName: string; email: string; role: string }
    return { userId: u.userId, displayName: u.displayName, email: u.email, roles: [u.role] }
  } catch {
    return {}
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  userId: null,
  displayName: null,
  email: null,
  roles: [],
  ...loadDevUser(),
  setUser: (user) => set(user),
  clearUser: () => set({ userId: null, displayName: null, email: null, roles: [] }),
}))
