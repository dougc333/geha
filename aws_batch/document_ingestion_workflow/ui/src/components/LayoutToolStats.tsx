import { DemoComponent } from '../DemoContext'

interface LayoutToolProfile {
  id: string
  name: string
  estimated_latency: string
  incremental_cost: string
  strength: string
  available?: boolean
  program?: string
  runs?: string
}

const DEFAULT_TOOLS: LayoutToolProfile[] = [
  {
    id: 'native_pdf_text_structure',
    name: 'Native PDF text + structure',
    estimated_latency: 'local parsing; no generation call',
    incremental_cost: '$0 model cost',
    strength: 'Uses embedded PDF text plus deterministic table extraction',
  },
  {
    id: 'whole_page_semantic_html',
    name: 'Whole-page semantic HTML',
    estimated_latency: 'HTML generation + bounded visual correction loop',
    incremental_cost: 'vision generation/review/correction calls',
    strength: 'Preserves complete page composition, charts, tables, and reading order',
  },
  {
    id: 'chart_figure_crop_html_correction',
    name: 'Chart/figure crop HTML correction (figure_segmentation)',
    estimated_latency: 'bounding boxes + up to 6 correction passes per visual',
    incremental_cost: 'vision segmentation, generation, review, and correction calls',
    strength: 'Auditable crop PNGs and per-figure attempts/errors before page assembly',
  },
  {
    id: 'bill_of_lading_named_cell_ocr',
    name: 'Bill of Lading named-cell OCR',
    estimated_latency: '8 structured OCR calls + deterministic build',
    incremental_cost: '8 vision OCR calls; no layout-generation call',
    strength: 'Literal named-cell records drive deterministic HTML assembly',
  },
  {
    id: 'authored_figure_spec_html',
    name: 'Authored figure specs (no model)',
    estimated_latency: 'local render + native-text verification',
    incremental_cost: '$0 model cost',
    strength: 'Spec values/labels checked against PDF text; deterministic semantic HTML',
  },
]

export class LayoutToolStats extends DemoComponent {
  render() {
    const { events, artifactUrl } = this.context
    const considered = events.find((event) => event.type === 'layout_tools_considered')
    const selected = events.find((event) => event.type === 'layout_tool_selected')
    const segmented = events.find((event) => event.type === 'page_segmented')
    const tools = (considered?.tools as LayoutToolProfile[] | undefined) ?? DEFAULT_TOOLS
    return (
      <section className="mx-auto max-w-[1600px] px-6 pt-3 lg:px-10">
        <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 lg:grid-cols-[190px_repeat(5,minmax(0,1fr))]">
          <div className="bg-slate-900/90 px-5 py-4">
            <div className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-300">Extraction tool router</div>
            <div className="mt-1 flex items-center justify-between gap-3">
              <div className="truncate text-sm font-semibold text-slate-200">{considered ? `Layout: ${String(considered.observed_layout)}` : 'Awaiting inspection'}</div>
              {considered && <span className="shrink-0 rounded-full bg-violet-300 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-950">Detected</span>}
            </div>
          </div>
          {tools.map((tool) => {
            const chosen = selected?.tool === tool.id
            return (
              <div key={tool.id} className={`min-w-0 px-5 py-4 ${chosen ? 'bg-cyan-300/10' : 'bg-slate-900/90'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="truncate text-sm font-semibold text-slate-200">{tool.name}</div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${chosen ? 'bg-cyan-300 text-slate-950' : 'bg-slate-800 text-slate-500'}`}>{chosen ? 'Selected' : considered ? tool.available === false ? 'Not applicable' : 'Available' : 'Awaiting run'}</span>
                </div>
                <div className="mt-1 flex min-w-0 flex-wrap gap-x-4 gap-y-1 font-mono text-[10px]">
                  <span className="text-slate-300">{tool.estimated_latency}</span>
                  <span className="text-slate-500">{tool.incremental_cost}</span>
                  <span className="truncate text-slate-500">{tool.strength}</span>
                  {tool.runs && <span className="basis-full truncate text-violet-300">runs: {tool.runs}</span>}
                  {segmented && tool.id === segmented.tool && (
                    <span className="flex gap-2 text-cyan-300">
                      <span>{String(segmented.region_count)} boxes · {String(segmented.latency_ms)} ms</span>
                      <a className="underline" href={artifactUrl(String(segmented.overlay))} target="_blank">Overlay</a>
                      <a className="underline" href={artifactUrl(String(segmented.regions_json))} target="_blank">JSON</a>
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </section>
    )
  }
}
