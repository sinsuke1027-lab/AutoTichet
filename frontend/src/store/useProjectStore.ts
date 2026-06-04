import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ProjectStore {
  activeProjectIds: string[]
  activeDeptTag: string | null
  setActiveProjects: (ids: string[]) => void
  setActiveDeptTag: (tag: string | null) => void
}

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set) => ({
      activeProjectIds: [],
      activeDeptTag: null,
      setActiveProjects: (ids) => set({ activeProjectIds: ids }),
      setActiveDeptTag: (tag) => set({ activeDeptTag: tag }),
    }),
    { name: 'autoticket-project-store' }
  )
)
