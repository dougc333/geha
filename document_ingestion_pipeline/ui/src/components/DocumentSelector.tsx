import { DemoComponent } from '../DemoContext'

export class DocumentSelector extends DemoComponent {
  render() {
    const { documents, selectedDocument, selectDocument, status } = this.context
    const running = status === 'starting' || status === 'running'
    return (
      <section className="mx-auto max-w-[1600px] px-6 pt-6 lg:px-10">
        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-300">Source document</div>
              <h2 className="mt-1 text-lg font-semibold text-white">Choose a source document</h2>
            </div>
            <span className="text-xs text-slate-500">Manifest-pinned public PDFs</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
            {documents.map((item) => {
              const selected = item.document === selectedDocument
              return (
                <button
                  key={item.document}
                  type="button"
                  disabled={running}
                  onClick={() => selectDocument(item.document)}
                  className={`min-w-0 rounded-xl border p-4 text-left transition ${selected ? 'border-cyan-300/70 bg-cyan-300/10 shadow-[0_0_24px_rgba(103,232,249,.08)]' : 'border-white/10 bg-slate-950/60 hover:border-white/25'} disabled:cursor-not-allowed ${running ? 'disabled:opacity-60' : ''}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className={`font-semibold ${selected ? 'text-cyan-100' : 'text-slate-200'}`}>{item.title}</div>
                      <div className="mt-1 break-words font-mono text-[10px] leading-4 text-slate-500">{item.filename}</div>
                    </div>
                    <span className={`mt-1 size-3 shrink-0 rounded-full border ${selected ? 'border-cyan-200 bg-cyan-300' : 'border-slate-600'}`} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-slate-400">
                    <span className="rounded-md bg-white/5 px-2 py-1">{item.page_count} pages</span>
                    <span className="rounded-md bg-white/5 px-2 py-1">image-only: {item.image_only_pages.length ? item.image_only_pages.join(', ') : 'none'}</span>
                    {!!item.visual_reconstruction_pages?.length && <span className="rounded-md bg-cyan-300/10 px-2 py-1 text-cyan-200">visual HTML: {item.visual_reconstruction_pages.join(', ')}</span>}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </section>
    )
  }
}
