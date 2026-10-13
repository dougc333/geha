import { DemoComponent } from '../DemoContext'

export class ControlStrip extends DemoComponent {
  render() {
    const { status, ready, model, runId, countdown, error } = this.context
    const dot = status === 'error' ? 'bg-rose-400' : status === 'running' ? 'bg-amber-300 animate-pulse' : ready ? 'bg-emerald-400' : 'bg-slate-500'
    return (
      <section className="mx-auto max-w-[1600px] px-6 pt-6 lg:px-10">
        <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Backend" value={ready ? 'Ready' : 'API key needed'} indicator={dot} />
          <Metric label="Model" value={model} mono />
          <Metric label="Run ID" value={runId ?? 'Not started'} mono />
          <Metric label="Inspection pause" value={countdown ? `${countdown}s remaining` : '5 seconds / stage'} accent={countdown > 0} />
        </div>
        {error && <div className="mt-4 rounded-xl border border-rose-400/30 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">{error}</div>}
      </section>
    )
  }
}

class Metric extends DemoComponent<{ label: string; value: string; mono?: boolean; indicator?: string; accent?: boolean }> {
  render() {
    const { label, value, mono, indicator, accent } = this.props
    return (
      <div className="min-w-0 bg-slate-900/90 px-5 py-4">
        <div className="mb-1 text-[10px] font-bold uppercase tracking-[.2em] text-slate-500">{label}</div>
        <div className={`flex items-center gap-2 truncate text-sm ${mono ? 'font-mono' : 'font-semibold'} ${accent ? 'text-amber-200' : 'text-slate-200'}`}>
          {indicator && <span className={`size-2 shrink-0 rounded-full ${indicator}`} />}{value}
        </div>
      </div>
    )
  }
}
