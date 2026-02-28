import { create } from 'zustand'

interface ModelState {
  currentModel: string
  currentMode: string
  ramUsage: number
  diskIO: number
  tps: number
  kvCache: number
  status: string
  updateMetrics: (metrics: Partial<ModelState>) => void
}

export const useStore = create<ModelState>((set) => ({
  currentModel: 'llama3:8b',
  currentMode: 'fullram',
  ramUsage: 0,
  diskIO: 0,
  tps: 0,
  kvCache: 0,
  status: 'idle',
  updateMetrics: (metrics) => set((state) => ({ ...state, ...metrics }))
}))
