import { DemoComponent } from '../DemoContext'
import type { AgentEvent } from '../types'

export class Summary extends DemoComponent {
  render() {
    const { events, after, status } = this.context
    const split = events.find((event) => event.type === 'split_complete')
    const reviews = events.filter((event) => event.type === 'review')
    const matches = reviews.filter((event) => event.verdict === 'match').length
    const finished = events.find((event) => event.type === 'agent_finished') as AgentEvent | undefined
    const qc = finished?.qc as Record<string, unknown> | undefined
    if (!split) return null
    return (
      <section className="mx-auto max-w-[1600px] px-6 pb-12 lg:px-10">
        <div className="grid gap-4 rounded-2xl border border-white/10 bg-gradient-to-r from-cyan-300/10 via-slate-900 to-emerald-300/10 p-5 sm:grid-cols-2 lg:grid-cols-5">
          <SummaryMetric label="Pages" value={String(split.page_count)} />
          <SummaryMetric label="Scanned pages" value={String((split.image_only_pages as number[]).length)} />
          <SummaryMetric label="Vision reviews" value={String(reviews.length)} />
          <SummaryMetric label="Verified pages" value={String(matches)} />
          <SummaryMetric label="Outcome" value={status === 'complete' ? String(qc?.status ?? 'candidate created') : after ? 'Correction visible' : 'In progress'} success={status === 'complete'} />
        </div>
      </section>
    )
  }
}

class SummaryMetric extends DemoComponent<{ label: string; value: string; success?: boolean }> {
  render() {
    return <div><div className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-500">{this.props.label}</div><div className={`mt-2 text-xl font-semibold ${this.props.success ? 'text-emerald-300' : 'text-white'}`}>{this.props.value}</div></div>
  }
}
