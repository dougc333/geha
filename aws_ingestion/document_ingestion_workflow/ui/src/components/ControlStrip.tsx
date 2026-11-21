import { DemoComponent } from '../DemoContext'

export class ControlStrip extends DemoComponent {
  render() {
    const { status, ready, provider, model, selectModel, layout, selectLayout, selectedDocument, buildRevision, runId, countdown, error } = this.context
    const dot = status === 'error' ? 'bg-rose-400' : status === 'running' ? 'bg-amber-300 animate-pulse' : ready ? 'bg-emerald-400' : 'bg-slate-500'
    return (
      <section className="mx-auto max-w-[1600px] px-6 pt-6 lg:px-10">
        <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label="Backend" value={ready ? 'Ready' : 'API key needed'} indicator={dot} />
          <Metric label="Docker build" value={buildRevision ?? 'development'} mono />
          <div className="min-w-0 bg-slate-900/90 px-5 py-4">
            <label htmlFor="vision-model" className="mb-1 block text-[10px] font-bold uppercase tracking-[.2em] text-slate-500">Vision model (when used)</label>
            <select
              id="vision-model"
              value={provider}
              disabled={status === 'starting' || status === 'running'}
              onChange={(event) => selectModel(event.target.value as 'anthropic' | 'nous')}
              aria-label="Vision model"
              className="w-full rounded-md border border-white/20 bg-slate-950 px-2 py-1 text-sm text-slate-200 focus:border-cyan-300 focus:outline-none disabled:opacity-60"
            >
              <option value="anthropic">Claude Sonnet 5.5 · Anthropic</option>
              <option value="nous">Qwen3-VL 235B · Nous</option>
            </select>
            <div className="mt-1 truncate font-mono text-[10px] text-slate-500" title={model}>{model}</div>
            <p className="mt-2 text-xs leading-5 text-amber-200/80">
              Bill-of-lading cell OCR uses Claude Opus 5.5 at medium effort; segment text review uses OpenAI, regardless of this selection.
            </p>
          </div>
          <div className="min-w-0 bg-slate-900/90 px-5 py-4">
            <label htmlFor="bol-layout" className="mb-1 block text-[10px] font-bold uppercase tracking-[.2em] text-slate-500">Bill of lading layout</label>
            <select id="bol-layout" value={layout}
              disabled={status === 'starting' || status === 'running' || selectedDocument !== 'forms/bill-of-lading.pdf'}
              onChange={(event) => selectLayout(event.target.value as 'gpt4o_only_8block_ocr.py' | 'refined_layout.py')}
              className="w-full rounded-md border border-white/20 bg-slate-950 px-2 py-1 text-sm text-slate-200 focus:border-cyan-300 focus:outline-none disabled:opacity-60">
              <option value="gpt4o_only_8block_ocr.py">gpt4o_only_8block_ocr.py</option>
              <option value="refined_layout.py">refined_layout.py</option>
            </select>
          </div>
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
