import { useMemo } from 'react'
import { useStats } from '../useStats'
import type { Run } from '../types'

export function RunSelector() {
  const { runs, runId, selectRun, status } = useStats()

  // One option group per family/document, newest run first.
  const groups = useMemo(() => {
    const byDocument = new Map<string, Run[]>()
    for (const run of runs) {
      const key = `${run.family} / ${run.document_id}`
      byDocument.set(key, [...(byDocument.get(key) ?? []), run])
    }
    return [...byDocument.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [runs])

  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
      Run
      <select
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none disabled:opacity-60"
        value={runId ?? ''}
        disabled={!runs.length || status === 'computing'}
        onChange={(event) => selectRun(event.target.value)}
      >
        {groups.map(([label, documentRuns]) => (
          <optgroup key={label} label={label}>
            {documentRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.run_id}
                {run.created_at ? ` · ${run.created_at.slice(0, 16).replace('T', ' ')}` : ''}
                {run.has_stats ? ' · saved' : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  )
}
