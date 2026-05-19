import { create } from 'zustand'

interface AuthState {
  userId: string | null
  displayName: string | null
  email: string | null
  roles: string[]
  setUser: (user: { userId: string; displayName: string; email: string; roles: string[] }) => void
  clearUser: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  userId: null,
  displayName: null,
  email: null,
  roles: [],
  setUser: (user) => set(user),
  clearUser: () => set({ userId: null, displayName: null, email: null, roles: [] }),
}))
