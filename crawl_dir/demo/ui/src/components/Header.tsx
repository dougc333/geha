import { DemoComponent } from '../DemoContext'

export class Header extends DemoComponent {
  render() {
    const { status, ready, startRun, documents, selectedDocument } = this.context
    const running = status === 'starting' || status === 'running'
    const title = documents.find((item) => item.document === selectedDocument)?.title ?? 'Coverage policy'
    return (
      <header className="border-b border-white/10 bg-slate-950/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-6 px-6 py-5 lg:px-10">
          <div className="flex items-center gap-4">
            <div className="grid size-11 place-items-center rounded-2xl bg-cyan-300 text-slate-950 shadow-[0_0_28px_rgba(103,232,249,.28)]">
              <span className="text-xl font-black">D</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display text-lg font-semibold tracking-tight text-white">Document Reconstruction Agent</h1>
                <span className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[.18em] text-cyan-200">Live</span>
              </div>
              <p className="text-sm text-slate-400">{title} coverage policy · public document workflow</p>
            </div>
          </div>
          <button
            onClick={() => void startRun()}
            disabled={!ready || running}
            className="group rounded-xl bg-cyan-300 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {running ? 'Agent running…' : status === 'complete' ? 'Run again' : 'Start live run'}
            <span className="ml-2 inline-block transition group-hover:translate-x-0.5">→</span>
          </button>
        </div>
      </header>
    )
  }
}
