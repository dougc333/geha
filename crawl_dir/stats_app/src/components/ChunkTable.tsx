import { useMemo } from 'react'
import { useStats } from '../useStats'
import { FLAGS } from '../types'

const FLAG_STYLES: Record<string, string> = {
  toc: 'bg-amber-100 text-amber-800',
  form: 'bg-purple-100 text-purple-800',
  tiny: 'bg-red-100 text-red-800',
  boilerplate: 'bg-slate-200 text-slate-700',
  table: 'bg-blue-100 text-blue-800',
}

export function ChunkTable() {
  const { stats, flagFilter } = useStats()
  const rows = useMemo(
    () => (stats ? stats.chunks.filter((row) => flagFilter === 'all' || row[flagFilter]) : []),
    [stats, flagFilter],
  )
  if (!stats) return null

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="sticky top-0 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Pages</th>
            <th className="px-3 py-2">Section</th>
            <th className="px-3 py-2 text-right">Words</th>
            <th className="px-3 py-2">Flags</th>
            <th className="px-3 py-2">Preview</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.chunk_id} className="align-top hover:bg-slate-50">
              <td className="px-3 py-2 font-mono text-xs text-slate-400">{row.chunk_id.split('-').pop()}</td>
              <td className="px-3 py-2 tabular-nums">{row.pages.join(', ')}</td>
              <td className="max-w-48 px-3 py-2 text-slate-700">{row.section}</td>
              <td className="px-3 py-2 text-right tabular-nums">{row.words}</td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  {FLAGS.filter((flag) => row[flag]).map((flag) => (
                    <span key={flag} className={`rounded px-1.5 py-0.5 text-xs font-medium ${FLAG_STYLES[flag]}`}>
                      {flag}
                    </span>
                  ))}
                </div>
              </td>
              <td className="px-3 py-2 text-slate-600">{row.preview}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="px-3 py-6 text-center text-sm text-slate-500">No chunks with this flag.</p>}
    </div>
  )
}
