import { createContext, useContext } from 'react'
import type { Flag, Run, RunStats } from './types'

export type Status = 'loading' | 'computing' | 'ready' | 'error'
export type Source = 'disk' | 'computed'

export type State = {
  runs: Run[]
  runId: string | null
  stats: RunStats | null
  source: Source | null
  status: Status
  error: string | null
  flagFilter: Flag | 'all'
}

export type Store = State & {
  selectRun: (runId: string) => void
  recompute: () => void
  setFlagFilter: (flag: Flag | 'all') => void
}

export const StoreContext = createContext<Store | null>(null)

/** Read the stats store from any component under <StatsProvider>. */
export function useStats(): Store {
  const store = useContext(StoreContext)
  if (!store) throw new Error('useStats must be used inside <StatsProvider>')
  return store
}
