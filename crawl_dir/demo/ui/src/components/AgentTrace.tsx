import { DemoComponent } from '../DemoContext'
import type { AgentEvent } from '../types'

const titles: Record<string, string> = {
  agent_started: 'Run initialized',
  tool_selected: 'Tool selected',
  download_complete: 'Source acquired',
  source_ready: 'Source fixture ready',
  screenshot_tools_considered: 'Screenshot tools considered',
  screenshot_tool_selected: 'Screenshot tool selected',
  screenshot_rendered: 'Source screenshot rendered',
  layout_tools_considered: 'Extraction tools considered',
  layout_tool_selected: 'Extraction tool selected',
  figure_pages_detected: 'Figure pages routed visually',
  visual_pages_selected: 'All report pages routed visually',
  figure_segment_review: 'Figure crop reviewed',
  figure_segments_complete: 'Figure crop batch complete',
  page_segmented: 'Page segmented',
  split_complete: 'Pages classified',
  initial_generation_started: 'Vision reconstruction started',
  initial_generation_complete: 'Initial semantic HTML created',
  native_page_html_created: 'Native page HTML created',
  native_page_ready: 'Native comparison ready',
  html_render_started: 'HTML render tool called',
  html_rendered: 'HTML rendered for comparison',
  external_resources_sanitized: 'External resources removed',
  external_resource_recurrence_stopped: 'Repeated resource loop stopped',
  correction_stopped: 'Correction loop stopped',
  before_ready: 'Initial HTML ready',
  pause: 'Visual inspection pause',
  review: 'Vision review returned',
  after_ready: 'Corrected HTML ready',
  ingestion_complete: 'Candidate assembled',
  agent_finished: 'Run complete',
  agent_error: 'Run failed',
}

export class AgentTrace extends DemoComponent {
  render() {
    const { events, status } = this.context
    return (
      <aside className="rounded-2xl border border-white/10 bg-slate-900/70">
        <div className="border-b border-white/10 px-5 py-4">
          <div className="text-[10px] font-bold uppercase tracking-[.2em] text-violet-300">Agent trace</div>
          <div className="mt-1 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Tool decisions</h2>
            <span className="font-mono text-xs text-slate-500">{events.length} events</span>
          </div>
        </div>
        <div className="max-h-[714px] overflow-y-auto p-4">
          {events.length === 0 ? (
            <p className="rounded-xl border border-dashed border-white/10 px-4 py-10 text-center text-sm text-slate-500">The live trace will appear here.</p>
          ) : (
            <ol className="space-y-3">
              {events.map((event) => <TraceEvent key={event.seq} event={event} />)}
            </ol>
          )}
          {status === 'running' && <div className="mt-4 h-1 overflow-hidden rounded-full bg-slate-800"><div className="h-full w-1/3 animate-[scan_1.4s_ease-in-out_infinite] rounded-full bg-cyan-300" /></div>}
        </div>
      </aside>
    )
  }
}

class TraceEvent extends DemoComponent<{ event: AgentEvent }> {
  private detail(event: AgentEvent): string {
    if (event.type === 'tool_selected') return `${event.tool} — ${event.reason}`
    if (event.type === 'split_complete') {
      const imageOnly = event.image_only_pages as number[]
      return `${event.page_count} pages · image-only: ${imageOnly.length ? imageOnly.join(', ') : 'none'} · split cache: ${event.split_cache_hit ? 'reused' : 'created'}`
    }
    if (event.type === 'initial_generation_started') return `Page ${event.page} · generating semantic HTML with ${event.model}`
    if (event.type === 'initial_generation_complete') return `Page ${event.page} · ${event.html_chars} HTML characters`
    if (event.type === 'native_page_html_created') return `Page ${event.page} · ${event.html_chars} HTML characters · $${Number(event.cost_usd).toFixed(2)}`
    if (event.type === 'native_page_ready') return `Page ${event.page} · source PDF and local semantic HTML ready · no correction loop`
    if (event.type === 'html_render_started') return `${event.page ? `Page ${event.page}` : `Segment ${event.segment}`} · pass ${Number(event.iteration) + 1} · ${event.tool} · ${event.browser}`
    if (event.type === 'html_rendered') return `${event.page ? `Page ${event.page}` : `Segment ${event.segment}`} · pass ${Number(event.iteration) + 1} · ${event.latency_ms} ms · $${Number(event.cost_usd).toFixed(2)} · ${event.output}`
    if (event.type === 'external_resources_sanitized') {
      if (event.mode === 'links_to_plain_text') return `Page ${event.page} · ${event.stage} · ${event.removed_count} external references converted to plain text · report: ${event.report}`
      return `Page ${event.page} · ${event.stage} · unsafe output preserved for audit; processing continued`
    }
    if (event.type === 'external_resource_recurrence_stopped') return `Page ${event.page} · pass ${event.iteration} · deterministic sanitation retained; one final review allowed`
    if (event.type === 'correction_stopped') return `Page ${event.page} · ${event.reason}`
    if (event.type === 'review') return `Page ${event.page} · pass ${Number(event.iteration) + 1} · ${event.verdict} · ${(event.errors as unknown[]).length} findings`
    if (event.type === 'pause') return `${event.seconds}s · ${event.reason}`
    if (event.type === 'download_complete') return String(event.status ?? 'Downloaded and verified')
    if (event.type === 'source_ready') return String(event.destination)
    if (event.type === 'screenshot_tools_considered') return `${(event.tools as unknown[]).length} local tools · requirement: ${event.requirement}`
    if (event.type === 'screenshot_tool_selected') return `${event.tool} — ${event.reason}`
    if (event.type === 'screenshot_rendered') return `Page ${event.page} · ${event.tool} · ${event.latency_ms} ms · $${Number(event.cost_usd).toFixed(2)}`
    if (event.type === 'layout_tools_considered') return `${(event.tools as unknown[]).length} extraction tools · observed layout: ${event.observed_layout}`
    if (event.type === 'layout_tool_selected') return `${event.tool} — ${event.reason}`
    if (event.type === 'figure_pages_detected') return `${event.count} pages · ${(event.pages as number[]).join(', ')} · ${event.method}`
    if (event.type === 'visual_pages_selected') return `${event.count} pages · ${event.method}`
    if (event.type === 'figure_segment_review') return `${event.title} · pass ${event.iteration} · ${event.verdict} · ${(event.errors as unknown[]).length} findings`
    if (event.type === 'figure_segments_complete') return `${event.figure_count} figures · ${event.iterations} total attempts · ${event.status} · ${event.batch}`
    if (event.type === 'page_segmented') return `Page ${event.page} · ${event.region_count} regions · ${event.latency_ms} ms · ${event.reason}`
    if (event.type === 'before_ready') return `Page ${event.page} · raw extraction captured`
    if (event.type === 'after_ready') return `Page ${event.page} · ${event.iterations} reviews · ${event.markdown_chars} Markdown chars`
    if (event.type === 'agent_error') return String(event.message)
    return event.type.replaceAll('_', ' ')
  }

  render() {
    const { event } = this.props
    const failed = event.type === 'agent_error' || event.verdict === 'mismatch'
    const passed = event.type === 'agent_finished' || event.verdict === 'match'
    return (
      <li className="relative rounded-xl border border-white/10 bg-slate-950/60 p-3.5 pl-4">
        <span className={`absolute -left-1 top-4 size-2 rounded-full ${failed ? 'bg-amber-300' : passed ? 'bg-emerald-400' : 'bg-cyan-300'}`} />
        <div className="flex items-start justify-between gap-3">
          <span className="text-xs font-bold text-slate-200">{titles[event.type] ?? event.type}</span>
          <span className="font-mono text-[9px] text-slate-600">#{event.seq}</span>
        </div>
        <p className="mt-1.5 break-words text-[11px] leading-5 text-slate-400">{this.detail(event)}</p>
      </li>
    )
  }
}
