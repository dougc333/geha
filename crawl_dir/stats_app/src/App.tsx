import { ChunkTable } from './components/ChunkTable'
import { RunSelector } from './components/RunSelector'
import { StatusBar } from './components/StatusBar'
import { SummaryCards } from './components/SummaryCards'
import { StatsProvider } from './store'

export default function App() {
  return (
    <StatsProvider>
      <main className="mx-auto grid max-w-7xl gap-5 px-4 py-6 text-slate-900 sm:px-6">
        <header>
          <h1 className="text-2xl font-bold tracking-tight">Chunk stats</h1>
          <p className="mt-1 text-sm text-slate-600">
            Chunk length and noise flags for one processed run in crawl_dir/runs. Saved stats load from disk; recompute
            only when you ask.
          </p>
        </header>
        <section className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4">
          <RunSelector />
          <StatusBar />
        </section>
        <SummaryCards />
        <ChunkTable />
      </main>
    </StatsProvider>
  )
}
