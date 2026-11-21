import { DemoComponent } from '../DemoContext'

interface ToolProfile {
  id: string
  name: string
  estimated_latency_ms: string
  cost_usd_per_page: number
  strength: string
  available: boolean
}

const DEFAULT_TOOLS: ToolProfile[] = [
  {
    id: 'pymupdf',
    name: 'PyMuPDF page rasterizer',
    estimated_latency_ms: '50–300',
    cost_usd_per_page: 0,
    strength: 'Exact page-only pixels; no browser controls',
    available: true,
  },
  {
    id: 'playwright_chromium',
    name: 'Playwright + Google Chrome',
    estimated_latency_ms: '1,000–4,000',
    cost_usd_per_page: 0,
    strength: 'Captures Chrome PDF-viewer behavior',
    available: true,
  },
]

export class ScreenshotToolStats extends DemoComponent {
  render() {
    const { events } = this.context
    const considered = events.find((event) => event.type === 'screenshot_tools_considered')
    const selected = events.find((event) => event.type === 'screenshot_tool_selected')
    const renders = events.filter((event) => event.type === 'screenshot_rendered')
    const tools = (considered?.tools as ToolProfile[] | undefined) ?? DEFAULT_TOOLS
    return (
      <section className="mx-auto max-w-[1600px] px-6 pt-6 lg:px-10">
        <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 lg:grid-cols-[220px_1fr_1fr]">
          <div className="bg-slate-900/90 px-5 py-4">
            <div className="text-[10px] font-bold uppercase tracking-[.2em] text-amber-300">Screenshot tool router</div>
            <div className="mt-1 text-sm font-semibold text-slate-200">{selected ? 'Renderer selected' : 'Awaiting run'}</div>
          </div>
          {tools.map((tool) => {
            const chosen = selected?.tool === tool.id
            const actual = renders.filter((event) => event.tool === tool.id)
            const total = actual.reduce((sum, event) => sum + Number(event.latency_ms), 0)
            return (
              <div key={tool.id} className={`min-w-0 px-5 py-4 ${chosen ? 'bg-emerald-400/10' : 'bg-slate-900/90'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="truncate text-sm font-semibold text-slate-200">{tool.name}</div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${chosen ? 'bg-emerald-300 text-slate-950' : 'bg-slate-800 text-slate-500'}`}>{chosen ? 'Selected' : considered ? tool.available ? 'Available' : 'Unavailable' : 'Awaiting run'}</span>
                </div>
                <div className="mt-1 flex min-w-0 flex-wrap gap-x-4 gap-y-1 font-mono text-[10px]">
                  <span className="text-slate-300">{actual.length ? `${total.toFixed(1)} ms actual` : `${tool.estimated_latency_ms} ms est.`}</span>
                  <span className="text-slate-500">${tool.cost_usd_per_page.toFixed(2)} / page</span>
                  <span className="truncate text-slate-500">{tool.strength}</span>
                </div>
              </div>
            )
          })}
        </div>
      </section>
    )
  }
}
