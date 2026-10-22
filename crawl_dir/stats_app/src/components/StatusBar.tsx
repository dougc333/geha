import { useStats } from '../useStats'

export function StatusBar() {
  const { stats, source, status, error, recompute, runId } = useStats()

  let message = 'Loading saved stats…'
  if (status === 'computing') message = 'No saved stats for this run. Computing and saving…'
  if (status === 'error') message = error ?? 'Something went wrong'
  if (status === 'ready' && stats) {
    const when = new Date(stats.computed_at).toLocaleString()
    message =
      source === 'disk'
        ? `Loaded from disk · computed ${when}`
        : `Computed now and saved · ${when}`
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className={`min-w-0 flex-1 text-sm ${status === 'error' ? 'text-red-700' : 'text-slate-600'}`}>
        {message}
        {runId && status === 'ready' && (
          <span className="mt-0.5 block truncate font-mono text-xs text-slate-400">
            crawl_dir/stats/{runId}/chunk-noise.json
          </span>
        )}
      </p>
      <button
        type="button"
        onClick={recompute}
        disabled={!runId || status === 'loading' || status === 'computing'}
        className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {status === 'computing' ? 'Computing…' : 'Recompute'}
      </button>
    </div>
  )
}
