import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SettingsState {
  workloadThresholdPct: number
  browserNotifyEnabled: boolean
  setWorkloadThreshold: (pct: number) => void
  setBrowserNotify: (enabled: boolean) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      workloadThresholdPct: 100,
      browserNotifyEnabled: false,
      setWorkloadThreshold: (pct) => set({ workloadThresholdPct: pct }),
      setBrowserNotify: (enabled) => set({ browserNotifyEnabled: enabled }),
    }),
    { name: 'autoticket-settings' },
  ),
)
