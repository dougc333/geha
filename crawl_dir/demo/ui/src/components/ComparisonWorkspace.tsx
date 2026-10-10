import { DemoComponent } from '../DemoContext'

export class ComparisonWorkspace extends DemoComponent {
  render() {
    const {
      before, after, activeView, selectView, artifactUrl, countdown,
      pageComparisons, previousPageComparisons, previousRunId, runView, selectRunView,
      selectedComparisonPage, selectComparisonPage, status,
    } = this.context
    const artifact = activeView === 'before' ? before : after
    const native = artifact?.mode === 'native'
    const waiting = !artifact
    const comparisons = runView === 'previous' ? previousPageComparisons : pageComparisons
    const pages = Object.entries(comparisons)
      .filter(([, comparison]) => comparison.before && comparison.after)
      .map(([page]) => Number(page))
      .sort((a, b) => a - b)
    const pageIndex = selectedComparisonPage === undefined
      ? -1
      : pages.indexOf(selectedComparisonPage)
    return (
      <section className="min-w-0 rounded-2xl border border-white/10 bg-slate-900/70 shadow-2xl shadow-black/20">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 px-5 py-4">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-300">Visual diff</div>
            <div className="mt-1 flex items-center gap-3">
              <h2 className="text-lg font-semibold text-white">Source PDF ↔ semantic HTML</h2>
              {artifact && <span className="rounded-md bg-white/5 px-2 py-1 font-mono text-[10px] text-cyan-200">Page {artifact.page}</span>}
            </div>
          </div>
          {artifact && pages.length > 0 && (
            <div className="flex items-center gap-2 rounded-xl bg-slate-950 p-1">
              <button type="button" disabled={pageIndex <= 0}
                onClick={() => selectComparisonPage(pages[pageIndex - 1])}
                aria-label="Previous completed page" title="Previous page"
                className="grid size-8 place-items-center rounded-lg text-lg font-bold text-slate-300 hover:bg-white/5 hover:text-white disabled:opacity-30">←</button>
              <select value={selectedComparisonPage}
                onChange={(event) => selectComparisonPage(Number(event.target.value))}
                className="rounded-lg border border-white/10 bg-slate-900 px-3 py-2 font-mono text-xs text-cyan-200">
                {pages.map((page) => <option key={page} value={page}>Page {page} of {pages.length}</option>)}
              </select>
              <button type="button" disabled={pageIndex < 0 || pageIndex >= pages.length - 1}
                onClick={() => selectComparisonPage(pages[pageIndex + 1])}
                aria-label="Next completed page" title="Next page"
                className="grid size-8 place-items-center rounded-lg text-lg font-bold text-slate-300 hover:bg-white/5 hover:text-white disabled:opacity-30">→</button>
            </div>
          )}
          {(previousRunId || runView === 'previous') && (
            <select value={runView} onChange={(event) => selectRunView(event.target.value as 'current' | 'previous')}
              className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-300">
              <option value="current">Current run</option>
              <option value="previous">Previous run · {previousRunId}</option>
            </select>
          )}
          {native ? (
            <div className="rounded-xl bg-emerald-300/10 px-4 py-2 text-xs font-bold text-emerald-200">Local extraction · no correction loop</div>
          ) : artifact ? <div className="flex rounded-xl bg-slate-950 p-1">
            <button onClick={() => selectView('before')} disabled={!before}
              className={`rounded-lg px-4 py-2 text-xs font-bold transition ${activeView === 'before' ? 'bg-white text-slate-950' : 'text-slate-400 hover:text-white'} disabled:opacity-40`}>
              Before correction
            </button>
            <button onClick={() => selectView('after')} disabled={!after}
              className={`rounded-lg px-4 py-2 text-xs font-bold transition ${activeView === 'after' ? 'bg-emerald-300 text-slate-950' : 'text-slate-400 hover:text-white'} disabled:opacity-40`}>
              After correction
            </button>
          </div> : null}
        </div>
        {waiting ? <EmptyWorkspace collected={pages.length} running={status === 'running' || status === 'starting'} /> : (
          <div className="grid min-h-[640px] lg:grid-cols-2">
            <ArtifactPanel label="Authoritative source" kind="PDF page" url={artifactUrl(artifact.source_pdf)} />
            <ArtifactPanel label={native ? 'Native semantic extraction' : activeView === 'before' ? 'Initial vision reconstruction' : 'Verified candidate'} kind="Semantic HTML" toolId={artifact.tool_id} url={artifactUrl(artifact.html)} html />
          </div>
        )}
        {countdown > 0 && artifact && (
          <div className="flex items-center gap-3 border-t border-amber-300/20 bg-amber-300/10 px-5 py-3 text-sm text-amber-100">
            <span className="grid size-7 place-items-center rounded-full bg-amber-300 font-mono font-black text-slate-950">{countdown}</span>
            Holding this comparison on screen before the agent continues.
          </div>
        )}
      </section>
    )
  }
}

class ArtifactPanel extends DemoComponent<{ label: string; kind: string; url: string; html?: boolean; toolId?: string }> {
  render() {
    const { label, kind, url, html, toolId } = this.props
    return (
      <article className="min-w-0 border-white/10 first:border-b lg:first:border-b-0 lg:first:border-r">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="text-xs font-semibold text-slate-200">{label}</span>
            {toolId && <span className="truncate rounded-md bg-cyan-300/10 px-2 py-1 font-mono text-[9px] text-cyan-200">tool_id: {toolId}</span>}
          </div>
          <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{kind}</span>
        </div>
        <div className="h-[590px] bg-[#e8eaec] p-2">
          <iframe title={label} src={url} sandbox={html ? '' : undefined} className="h-full w-full rounded bg-white" />
        </div>
      </article>
    )
  }
}

class EmptyWorkspace extends DemoComponent<{ collected: number; running: boolean }> {
  render() {
    const { collected, running } = this.props
    return (
      <div className="grid min-h-[640px] place-items-center px-8 text-center">
        <div className="max-w-md">
          <div className="mx-auto mb-6 grid size-20 place-items-center rounded-3xl border border-dashed border-cyan-300/30 bg-cyan-300/5 text-3xl text-cyan-200">⌁</div>
          <h3 className="text-xl font-semibold text-white">{running ? 'Processing document pages' : 'Waiting for page artifacts'}</h3>
          <p className="mt-3 text-sm leading-6 text-slate-400">{running ? `${collected} page${collected === 1 ? '' : 's'} ready. Navigation expands as each page finishes.` : 'Start the run to display the source page beside its native or vision-generated semantic HTML.'}</p>
        </div>
      </div>
    )
  }
}
