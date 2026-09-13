import type { Claim } from '../../shared/types'
export function ClaimList({
  claims,
  selected,
  disabled,
  onSelect,
}: {
  claims: Claim[]
  selected: string
  disabled: boolean
  onSelect: (id: string) => void
}) {
  return (
    <div className="space-y-2">
      {claims.map((c) => (
        <button
          key={c.id}
          disabled={disabled}
          aria-pressed={selected === c.id}
          onClick={() => onSelect(c.id)}
          className={`w-full text-left rounded-xl border p-4 transition-colors ${selected === c.id ? 'border-teal-700 bg-teal-50 shadow-sm' : 'border-slate-200 bg-white hover:border-teal-400'}`}
        >
          <span className="font-semibold">{c.id}</span>
          <span className="block text-sm text-slate-500 mt-1">{c.member}</span>
          <span className="inline-block mt-2 text-xs font-medium tracking-wide text-slate-600">
            {c.status.replaceAll('_', ' ')}
          </span>
        </button>
      ))}
    </div>
  )
}
