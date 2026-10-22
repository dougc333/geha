import type { Run, RunStats } from './types'

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  return response.json() as Promise<T>
}

export const fetchRuns = () => fetch('/api/runs').then((r) => json<Run[]>(r))

/** Saved stats for a run, or null when none have been computed yet. */
export async function fetchStats(runId: string): Promise<RunStats | null> {
  const response = await fetch(`/api/stats?run=${encodeURIComponent(runId)}`)
  if (response.status === 204) return null
  return json<RunStats>(response)
}

/** Recompute stats on the server, which saves them under crawl_dir/stats/<run>. */
export const computeStats = (runId: string) =>
  fetch(`/api/stats?run=${encodeURIComponent(runId)}`, { method: 'POST' }).then((r) =>
    json<RunStats>(r),
  )
