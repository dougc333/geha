import { useCallback, useEffect, useMemo, useReducer, useRef } from 'react'
import type { ReactNode } from 'react'
import { computeStats, fetchRuns, fetchStats } from './api'
import type { Flag, Run, RunStats } from './types'
import { StoreContext } from './useStats'
import type { Source, State } from './useStats'

type Action =
  | { type: 'runs'; runs: Run[]; runId: string | null }
  | { type: 'select'; runId: string }
  | { type: 'computing' }
  | { type: 'stats'; stats: RunStats; source: Source }
  | { type: 'error'; error: string }
  | { type: 'filter'; flag: Flag | 'all' }

const initialState: State = {
  runs: [],
  runId: null,
  stats: null,
  source: null,
  status: 'loading',
  error: null,
  flagFilter: 'all',
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'runs':
      return { ...state, runs: action.runs, runId: action.runId, status: action.runId ? 'loading' : 'ready' }
    case 'select':
      return { ...state, runId: action.runId, stats: null, source: null, status: 'loading', error: null }
    case 'computing':
      return { ...state, status: 'computing', error: null }
    case 'stats':
      return {
        ...state,
        stats: action.stats,
        source: action.source,
        status: 'ready',
        runs: state.runs.map((run) => (run.id === action.stats.run ? { ...run, has_stats: true } : run)),
      }
    case 'error':
      return { ...state, status: 'error', error: action.error }
    case 'filter':
      return { ...state, flagFilter: action.flag }
  }
}

/** The EY/LIMRA research report is the default run when the URL names none. */
function defaultRun(runs: Run[]): string | null {
  const requested = new URLSearchParams(window.location.search).get('run')
  if (requested && runs.some((run) => run.id === requested)) return requested
  const ey = runs.find((run) => run.family === 'research' && run.document_id.startsWith('ey-limra'))
  return ey?.id ?? runs[0]?.id ?? null
}

export function StatsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  // Ignore responses for a run that is no longer selected.
  const latest = useRef<string | null>(null)

  const load = useCallback(async (runId: string, force: boolean) => {
    latest.current = runId
    try {
      let stats = force ? null : await fetchStats(runId)
      let source: Source = 'disk'
      if (!stats) {
        if (latest.current === runId) dispatch({ type: 'computing' })
        stats = await computeStats(runId)
        source = 'computed'
      }
      if (latest.current === runId) dispatch({ type: 'stats', stats, source })
    } catch (error) {
      if (latest.current === runId) dispatch({ type: 'error', error: String(error) })
    }
  }, [])

  useEffect(() => {
    // StrictMode mounts twice in development; only the surviving mount loads stats.
    let active = true
    fetchRuns()
      .then((runs) => {
        if (!active) return
        const runId = defaultRun(runs)
        dispatch({ type: 'runs', runs, runId })
        if (runId) void load(runId, false)
      })
      .catch((error) => active && dispatch({ type: 'error', error: String(error) }))
    return () => {
      active = false
    }
  }, [load])

  const selectRun = useCallback(
    (runId: string) => {
      dispatch({ type: 'select', runId })
      const url = new URL(window.location.href)
      url.searchParams.set('run', runId)
      window.history.replaceState(null, '', url)
      void load(runId, false)
    },
    [load],
  )

  const recompute = useCallback(() => {
    if (state.runId) void load(state.runId, true)
  }, [load, state.runId])

  const setFlagFilter = useCallback((flag: Flag | 'all') => dispatch({ type: 'filter', flag }), [])

  const value = useMemo(
    () => ({ ...state, selectRun, recompute, setFlagFilter }),
    [state, selectRun, recompute, setFlagFilter],
  )
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}
