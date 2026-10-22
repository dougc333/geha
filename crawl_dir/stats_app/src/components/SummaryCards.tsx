import { useStats } from '../useStats'
import { FLAGS } from '../types'

const percent = (count: number, total: number) => (total ? `${((100 * count) / total).toFixed(1)}%` : '–')

export function SummaryCards() {
  const { stats, flagFilter, setFlagFilter } = useStats()
  if (!stats) return null
  const { summary } = stats

  const facts = [
    ['Pages', summary.pages],
    ['Chunks', summary.chunks],
    ['Median words', summary.median_words],
    ['P90 words', summary.p90_words],
  ] as const

  return (
    <div className="grid gap-3">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {facts.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter chunks by flag">
        <FilterChip active={flagFilter === 'all'} onClick={() => setFlagFilter('all')}>
          All · {summary.chunks}
        </FilterChip>
        {FLAGS.map((flag) => (
          <FilterChip key={flag} active={flagFilter === flag} onClick={() => setFlagFilter(flag)}>
            {flag} · {summary[flag]} ({percent(summary[flag], summary.chunks)})
          </FilterChip>
        ))}
      </div>
    </div>
  )
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-sm tabular-nums ${
        active ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
      }`}
    >
      {children}
    </button>
  )
}
