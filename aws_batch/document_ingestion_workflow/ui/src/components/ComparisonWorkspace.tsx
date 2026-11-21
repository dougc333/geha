import React from 'react'
import { DemoComponent } from '../DemoContext'

export class ComparisonWorkspace extends DemoComponent<Record<string, never>, { sourceWidth: number; sourceMinimized: boolean }> {
  state = { sourceWidth: 50, sourceMinimized: false }
  private readonly splitRef = React.createRef<HTMLDivElement>()

  private resizePanels = (clientX: number): void => {
    const bounds = this.splitRef.current?.getBoundingClientRect()
    if (!bounds || bounds.width === 0) return
    const sourceWidth = Math.max(20, Math.min(80, Math.round((clientX - bounds.left) / bounds.width * 100)))
    if (sourceWidth !== this.state.sourceWidth) this.setState({ sourceWidth })
  }

  private onDividerPointerDown = (event: React.PointerEvent<HTMLDivElement>): void => {
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    this.resizePanels(event.clientX)
  }

  private onDividerPointerMove = (event: React.PointerEvent<HTMLDivElement>): void => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) this.resizePanels(event.clientX)
  }

  private onDividerKeyDown = (event: React.KeyboardEvent<HTMLDivElement>): void => {
    const width = this.state.sourceWidth
    const next = event.key === 'ArrowLeft' ? width - 5
      : event.key === 'ArrowRight' ? width + 5
      : event.key === 'Home' ? 20
      : event.key === 'End' ? 80 : width
    if (next !== width) {
      event.preventDefault()
      this.setState({ sourceWidth: Math.max(20, Math.min(80, next)) })
    }
  }

  render() {
    const {
      before, after, activeView, selectView, artifactUrl, countdown,
      pageComparisons, savedRuns, runView, selectRunView,
      selectedComparisonPage, selectComparisonPage, status,
    } = this.context
    const artifact = activeView === 'before' ? before : after
    const native = artifact?.mode === 'native'
    const waiting = !artifact
    const comparisons = runView === 'current'
      ? pageComparisons
      : savedRuns.find((run) => run.run_id === runView)?.pages ?? {}
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
          {savedRuns.length > 0 && (
            <select value={runView} onChange={(event) => selectRunView(event.target.value)}
              className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-300">
              <option value="current">Current run</option>
              {savedRuns.map((run) => <option key={run.run_id} value={run.run_id}>Saved run · {run.run_id}</option>)}
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
          {artifact && <button type="button"
            onClick={() => this.setState({ sourceMinimized: !this.state.sourceMinimized })}
            aria-pressed={this.state.sourceMinimized}
            className="rounded-lg border border-cyan-300/30 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-300/10">
            {this.state.sourceMinimized ? 'Show source' : 'Minimize source'}
          </button>}
        </div>
        {waiting ? <EmptyWorkspace collected={pages.length} running={status === 'running' || status === 'starting'} /> : (
          <div ref={this.splitRef} className={this.state.sourceMinimized ? 'min-h-[640px]' : 'comparison-split min-h-[640px]'}
            style={{ '--pdf-pane-width': `${this.state.sourceWidth}%` } as React.CSSProperties}>
            {!this.state.sourceMinimized && <>
              <ArtifactPanel label="Authoritative source" kind="PDF page" url={artifactUrl(artifact.source_pdf)} />
              <div role="separator" aria-label="Resize PDF and HTML panes" aria-orientation="vertical"
                aria-valuemin={20} aria-valuemax={80} aria-valuenow={this.state.sourceWidth}
                tabIndex={0} title="Drag to resize PDF and HTML panes"
                onPointerDown={this.onDividerPointerDown} onPointerMove={this.onDividerPointerMove}
                onPointerUp={(event) => {
                  this.resizePanels(event.clientX)
                  if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
                }}
                onKeyDown={this.onDividerKeyDown}
                className="comparison-divider" />
            </>}
            <ArtifactPanel label={native ? 'Native semantic extraction' : activeView === 'before' ? 'Initial vision reconstruction' : 'Candidate HTML'} kind="Semantic HTML" toolId={artifact.tool_id} url={artifactUrl(artifact.html)} html />
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

class ArtifactPanel extends DemoComponent<{ label: string; kind: string; url: string; html?: boolean; toolId?: string }, { fitScale: number; zoom: number; contentHeight: number; htmlWidth: number }> {
  state = { fitScale: 1, zoom: 1, contentHeight: 2000, htmlWidth: 1020 }
  private readonly panelRef = React.createRef<HTMLDivElement>()
  private readonly frameRef = React.createRef<HTMLIFrameElement>()
  private resizeObserver?: ResizeObserver
  private static readonly defaultHtmlWidth = 1020

  componentDidMount(): void {
    if (!this.props.html || !this.panelRef.current) return
    this.resizeObserver = new ResizeObserver(() => {
      const width = this.panelRef.current?.clientWidth ?? this.state.htmlWidth
      const fitScale = Math.min(1, width / this.state.htmlWidth)
      if (Math.abs(fitScale - this.state.fitScale) > 0.001) this.setState({ fitScale })
    })
    this.resizeObserver.observe(this.panelRef.current)
  }

  componentWillUnmount(): void {
    this.resizeObserver?.disconnect()
  }

  componentDidUpdate(previousProps: Readonly<typeof this.props>): void {
    if (previousProps.url !== this.props.url && this.props.html && this.state.zoom !== 1) {
      this.setState({ zoom: 1 })
    }
  }

  private measureHtml = (): void => {
    if (!this.props.html) return
    // The artifact is served from this origin and sandboxed without scripts.
    const doc = this.frameRef.current?.contentDocument
    const height = Math.max(doc?.body?.scrollHeight ?? 0, doc?.documentElement?.scrollHeight ?? 0)
    if (height && height !== this.state.contentHeight) this.setState({ contentHeight: height })
  }

  private updateHtmlLayout = (): void => {
    const doc = this.frameRef.current?.contentDocument
    if (!doc) return
    const widths: number[] = []
    for (const sheet of Array.from(doc.styleSheets)) {
      try {
        for (const rule of Array.from(sheet.cssRules)) {
          const styleRule = rule as CSSStyleRule
          if (!styleRule.selectorText?.split(',').some((selector) => selector.trim() === '.page')) continue
          for (const value of [styleRule.style.width, styleRule.style.maxWidth]) {
            const match = /^(\d+(?:\.\d+)?)px$/.exec(value)
            if (match) widths.push(Number(match[1]))
          }
        }
      } catch {
        // A stylesheet outside this artifact cannot determine its page width.
      }
    }
    const declaredWidth = widths.length ? Math.max(...widths) : ArtifactPanel.defaultHtmlWidth
    const htmlWidth = Math.max(600, Math.min(2000, declaredWidth))
    const panelWidth = this.panelRef.current?.clientWidth ?? htmlWidth
    const fitScale = Math.min(1, panelWidth / htmlWidth)
    this.setState({ htmlWidth, fitScale }, () => requestAnimationFrame(this.measureHtml))
  }

  private changeZoom = (step: number): void => {
    this.setState((state) => ({ zoom: Math.max(0.5, Math.min(2, Math.round((state.zoom + step) * 4) / 4)) }))
  }

  render() {
    const { label, kind, url, html, toolId } = this.props
    const { fitScale, zoom, contentHeight, htmlWidth } = this.state
    const scale = fitScale * zoom
    return (
      <article className="min-w-0 border-white/10 first:border-b lg:first:border-b-0 lg:first:border-r">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="text-xs font-semibold text-slate-200">{label}</span>
            {toolId && <span className="truncate rounded-md bg-cyan-300/10 px-2 py-1 font-mono text-[9px] text-cyan-200">tool_id: {toolId}</span>}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {html && <div role="group" aria-label="Semantic HTML zoom" className="flex items-center rounded-lg border border-white/10 bg-slate-950">
              <button type="button" onClick={() => this.changeZoom(-0.25)} disabled={zoom <= 0.5}
                aria-label="Zoom out semantic HTML" title="Zoom out"
                className="px-2 py-1 text-sm font-bold text-cyan-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40">−</button>
              <button type="button" onClick={() => this.setState({ zoom: 1 })}
                aria-label="Reset semantic HTML zoom to fit" title="Reset to fit"
                className="min-w-12 px-1 py-1 font-mono text-[10px] text-slate-300 hover:bg-white/10">{Math.round(zoom * 100)}%</button>
              <button type="button" onClick={() => this.changeZoom(0.25)} disabled={zoom >= 2}
                aria-label="Zoom in semantic HTML" title="Zoom in"
                className="px-2 py-1 text-sm font-bold text-cyan-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40">+</button>
            </div>}
            {html && <a href={url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-cyan-200 underline">Open full size</a>}
            <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{kind}</span>
          </div>
        </div>
        <div className="h-[590px] bg-[#e8eaec] p-2">
          {html ? (
            <div ref={this.panelRef} className="h-full overflow-auto rounded bg-white">
              <div className="relative mx-auto" style={{ width: htmlWidth * scale, height: contentHeight * scale }}>
                <iframe ref={this.frameRef} title={label} src={url} sandbox="allow-same-origin"
                  onLoad={this.updateHtmlLayout}
                  className="absolute left-0 top-0 border-0 bg-white"
                  style={{ width: htmlWidth, height: contentHeight, transform: `scale(${scale})`, transformOrigin: 'top left' }} />
              </div>
            </div>
          ) : <iframe title={label} src={url} className="h-full w-full rounded bg-white" />}
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
