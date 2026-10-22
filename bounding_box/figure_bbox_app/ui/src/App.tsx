import { Component, type ChangeEvent, type PointerEvent as ReactPointerEvent } from 'react'

const COORDINATE_MAX = 1000

type RegionKind = 'figure' | 'chart' | 'table' | 'image' | 'other'

type BoundingBox = {
  id: string
  kind: RegionKind
  label: string
  x1: number
  y1: number
  x2: number
  y2: number
}

type AnnotationFile = {
  schema_version: number
  document_id: string
  source_pdf: string
  page_count: number
  coordinate_system: string
  updated_at: string
  pages: Record<string, BoundingBox[]>
}

type DocumentInfo = {
  document_id: string
  title: string
  source_pdf: string
  page_count: number
  page_aspect_ratio: number
  annotation_path: string
  prompt_path: string
  specs_path: string
}

type SpecPageState = {
  page: number
  state: 'boxed' | 'extracting' | 'evidence_extracted' | 'generating' | 'validating' | 'saved' | 'skipped_existing' | 'failed'
  attempt: number
  region_count: number
  message: string
  spec_path?: string | null
  errors?: Array<Record<string, unknown>>
}

type SpecStatus = {
  schema_version: number
  document_id: string
  running: boolean
  updated_at: string
  existing_spec_count: number
  boxed_page_count: number
  error?: string
  pages: Record<string, SpecPageState>
}

type PromptEvidence = {
  text: string
  lines: string[]
  fonts: string[]
  percentages: string[]
  years: string[]
  numeric_tokens: string[]
  chart_structure: {
    status: 'mapped' | 'ambiguous'
    orientation: 'vertical' | 'horizontal' | null
    bars: Array<Record<string, unknown>>
    percentage_tokens: Array<Record<string, unknown>>
    unmapped_percentage_tokens: Array<Record<string, unknown>>
  }
}

type ReconstructionPrompt = {
  region_id: string
  label: string
  kind: RegionKind
  method: 'user_approved' | 'deterministic_from_native_evidence'
  prompt_file: string
  prompt: string
  evidence: PromptEvidence
}

type PromptFile = {
  schema_version: number
  document_id: string
  generated_at?: string
  region_count: number
  pages: Record<string, ReconstructionPrompt[]>
}

type Point = { x: number; y: number }

type CanvasProps = {
  page: number
  boxes: BoundingBox[]
  selectedId: string | null
  onCreate: (box: Omit<BoundingBox, 'id' | 'label' | 'kind'>) => void
  onSelect: (id: string | null) => void
}

type CanvasState = {
  start: Point | null
  current: Point | null
  imageLoaded: boolean
}

class PageCanvas extends Component<CanvasProps, CanvasState> {
  state: CanvasState = { start: null, current: null, imageLoaded: false }
  private surface: HTMLDivElement | null = null

  componentDidUpdate(previous: CanvasProps): void {
    if (previous.page !== this.props.page) {
      this.setState({ start: null, current: null, imageLoaded: false })
    }
  }

  private pointFromEvent = (event: ReactPointerEvent<HTMLDivElement>): Point => {
    const bounds = event.currentTarget.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(COORDINATE_MAX, ((event.clientX - bounds.left) / bounds.width) * COORDINATE_MAX)),
      y: Math.max(0, Math.min(COORDINATE_MAX, ((event.clientY - bounds.top) / bounds.height) * COORDINATE_MAX)),
    }
  }

  private handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>): void => {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = this.pointFromEvent(event)
    this.props.onSelect(null)
    this.setState({ start: point, current: point })
  }

  private handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>): void => {
    if (!this.state.start || !event.currentTarget.hasPointerCapture(event.pointerId)) return
    this.setState({ current: this.pointFromEvent(event) })
  }

  private finishDrawing = (event: ReactPointerEvent<HTMLDivElement>): void => {
    const { start } = this.state
    if (!start) return
    const end = this.pointFromEvent(event)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    this.setState({ start: null, current: null })
    const box = {
      x1: Math.min(start.x, end.x),
      y1: Math.min(start.y, end.y),
      x2: Math.max(start.x, end.x),
      y2: Math.max(start.y, end.y),
    }
    if (box.x2 - box.x1 >= 6 && box.y2 - box.y1 >= 6) this.props.onCreate(box)
  }

  render(): React.ReactNode {
    const { page, boxes, selectedId, onSelect } = this.props
    const { start, current, imageLoaded } = this.state
    const draft = start && current
      ? {
          x1: Math.min(start.x, current.x), y1: Math.min(start.y, current.y),
          x2: Math.max(start.x, current.x), y2: Math.max(start.y, current.y),
        }
      : null

    return (
      <div className="viewer-shell">
        {!imageLoaded && <div className="viewer-loading"><span className="spinner" />Rendering PDF page {page}…</div>}
        <div
          ref={(node) => { this.surface = node }}
          className={`page-surface ${imageLoaded ? 'ready' : ''}`}
          onPointerDown={this.handlePointerDown}
          onPointerMove={this.handlePointerMove}
          onPointerUp={this.finishDrawing}
          onPointerCancel={this.finishDrawing}
          role="application"
          aria-label={`PDF page ${page}. Drag to draw a bounding box.`}
        >
          <img
            src={`/api/pages/${page}.png`}
            alt={`Rendered PDF page ${page}`}
            draggable={false}
            onLoad={() => this.setState({ imageLoaded: true })}
          />
          <svg className="box-layer" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">
            {boxes.map((box, index) => (
              <g key={box.id} className={box.id === selectedId ? 'box selected' : 'box'} onPointerDown={(event) => {
                event.stopPropagation()
                onSelect(box.id)
              }}>
                <rect x={box.x1} y={box.y1} width={box.x2 - box.x1} height={box.y2 - box.y1} />
                <text x={box.x1 + 9} y={Math.max(24, box.y1 + 25)}>{index + 1}</text>
              </g>
            ))}
            {draft && <rect className="draft-box" x={draft.x1} y={draft.y1} width={draft.x2 - draft.x1} height={draft.y2 - draft.y1} />}
          </svg>
        </div>
      </div>
    )
  }
}

type AppState = {
  info: DocumentInfo | null
  annotations: AnnotationFile | null
  prompts: PromptFile | null
  specs: SpecStatus | null
  page: number
  selectedId: string | null
  copiedPromptId: string | null
  status: 'loading' | 'saved' | 'saving' | 'error'
  error: string | null
}

export class App extends Component<Record<string, never>, AppState> {
  private saveQueue: Promise<void> = Promise.resolve()
  private saveVersion = 0
  private specTimer: number | null = null

  state: AppState = {
    info: null,
    annotations: null,
    prompts: null,
    specs: null,
    page: 1,
    selectedId: null,
    copiedPromptId: null,
    status: 'loading',
    error: null,
  }

  componentDidMount(): void {
    void this.load()
    window.addEventListener('keydown', this.handleKeyDown)
  }

  componentWillUnmount(): void {
    window.removeEventListener('keydown', this.handleKeyDown)
    if (this.specTimer !== null) window.clearTimeout(this.specTimer)
  }

  private load = async (): Promise<void> => {
    try {
      const [infoResponse, annotationResponse, promptResponse, specResponse] = await Promise.all([
        fetch('/api/document'),
        fetch('/api/annotations'),
        fetch('/api/prompts'),
        fetch('/api/specs'),
      ])
      if (!infoResponse.ok || !annotationResponse.ok || !promptResponse.ok || !specResponse.ok) throw new Error('Unable to load document workspace')
      const info = await infoResponse.json() as DocumentInfo
      const annotations = await annotationResponse.json() as AnnotationFile
      const prompts = await promptResponse.json() as PromptFile
      const specs = await specResponse.json() as SpecStatus
      this.setState({ info, annotations, prompts, specs, status: 'saved', error: null }, this.scheduleSpecRefresh)
    } catch (error) {
      this.setState({ status: 'error', error: error instanceof Error ? error.message : String(error) })
    }
  }

  private scheduleSpecRefresh = (): void => {
    if (this.specTimer !== null) window.clearTimeout(this.specTimer)
    if (!this.state.specs?.running) {
      this.specTimer = null
      return
    }
    this.specTimer = window.setTimeout(() => void this.refreshSpecs(), 850)
  }

  private refreshSpecs = async (): Promise<void> => {
    try {
      const response = await fetch('/api/specs', { cache: 'no-store' })
      if (!response.ok) throw new Error(await response.text())
      const specs = await response.json() as SpecStatus
      this.setState({ specs, error: specs.error ?? null }, this.scheduleSpecRefresh)
    } catch (error) {
      this.setState({ error: error instanceof Error ? error.message : String(error) })
    }
  }

  private generateSpecs = async (): Promise<void> => {
    try {
      const response = await fetch('/api/specs/generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!response.ok) throw new Error(await response.text())
      await this.refreshSpecs()
    } catch (error) {
      this.setState({ error: error instanceof Error ? error.message : String(error) })
    }
  }

  private persist = (annotations: AnnotationFile): Promise<void> => {
    const version = ++this.saveVersion
    this.setState({ status: 'saving', error: null })
    this.saveQueue = this.saveQueue.then(async () => {
      try {
        const response = await fetch('/api/annotations', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(annotations),
        })
        if (!response.ok) throw new Error(await response.text())
        const saved = await response.json() as AnnotationFile
        if (version === this.saveVersion) this.setState({ annotations: saved, status: 'saved' })
      } catch (error) {
        if (version === this.saveVersion) {
          this.setState({ status: 'error', error: error instanceof Error ? error.message : String(error) })
        }
      }
    })
    return this.saveQueue
  }

  private updateBoxes = (boxes: BoundingBox[]): void => {
    const annotations = this.state.annotations
    if (!annotations) return
    const pages = { ...annotations.pages }
    if (boxes.length) pages[String(this.state.page)] = boxes
    else delete pages[String(this.state.page)]
    const next = { ...annotations, pages }
    this.setState({ annotations: next })
    void this.persist(next)
  }

  private currentBoxes = (): BoundingBox[] => this.state.annotations?.pages[String(this.state.page)] ?? []

  private createBox = (coords: Omit<BoundingBox, 'id' | 'label' | 'kind'>): void => {
    const pageBoxes = this.currentBoxes()
    const sequence = pageBoxes.length + 1
    const id = `page-${String(this.state.page).padStart(3, '0')}-region-${crypto.randomUUID().slice(0, 8)}`
    const box: BoundingBox = {
      id,
      kind: 'figure',
      label: `Figure ${sequence}`,
      ...coords,
    }
    this.setState({ selectedId: id })
    this.updateBoxes([...pageBoxes, box])
  }

  private updateSelected = (changes: Partial<Pick<BoundingBox, 'label' | 'kind'>>): void => {
    const selectedId = this.state.selectedId
    if (!selectedId) return
    this.updateBoxes(this.currentBoxes().map((box) => box.id === selectedId ? { ...box, ...changes } : box))
  }

  private deleteSelected = (): void => {
    const selectedId = this.state.selectedId
    if (!selectedId) return
    this.setState({ selectedId: null })
    this.updateBoxes(this.currentBoxes().filter((box) => box.id !== selectedId))
  }

  private clearPage = (): void => {
    if (!this.currentBoxes().length || !window.confirm(`Remove all boxes from page ${this.state.page}?`)) return
    this.setState({ selectedId: null })
    this.updateBoxes([])
  }

  private goToPage = (page: number): void => {
    const count = this.state.info?.page_count ?? 29
    this.setState({ page: Math.max(1, Math.min(count, page)), selectedId: null })
  }

  private saveNow = (): void => {
    if (this.state.annotations) void this.persist(this.state.annotations)
  }

  private copyPrompt = async (record: ReconstructionPrompt): Promise<void> => {
    try {
      await navigator.clipboard.writeText(record.prompt)
      this.setState({ copiedPromptId: record.region_id })
      window.setTimeout(() => {
        if (this.state.copiedPromptId === record.region_id) this.setState({ copiedPromptId: null })
      }, 1600)
    } catch (error) {
      this.setState({ status: 'error', error: error instanceof Error ? error.message : String(error) })
    }
  }

  private handleKeyDown = (event: KeyboardEvent): void => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
      event.preventDefault()
      this.saveNow()
      return
    }
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return
    if (event.key === 'ArrowLeft') this.goToPage(this.state.page - 1)
    if (event.key === 'ArrowRight') this.goToPage(this.state.page + 1)
    if ((event.key === 'Backspace' || event.key === 'Delete') && this.state.selectedId) {
      event.preventDefault()
      this.deleteSelected()
    }
    if (event.key === 'Escape') this.setState({ selectedId: null })
  }

  render(): React.ReactNode {
    const { info, annotations, prompts, specs, page, selectedId, copiedPromptId, status, error } = this.state
    if (!info || !annotations || !prompts || !specs) {
      return <main className="loading-screen"><span className="spinner" /><h1>Loading figure annotator</h1>{error && <p>{error}</p>}</main>
    }
    const boxes = this.currentBoxes()
    const selected = boxes.find((box) => box.id === selectedId) ?? null
    const annotatedPages = Object.keys(annotations.pages).length
    const totalBoxes = Object.values(annotations.pages).reduce((sum, pageBoxes) => sum + pageBoxes.length, 0)
    const pagePrompts = prompts.pages[String(page)] ?? []
    const activePrompt = pagePrompts.find((record) => record.region_id === selectedId) ?? pagePrompts[0] ?? null
    const pageSpec = specs.pages[String(page)]
    const specStages = [
      ['boxed', 'Boxed'], ['evidence_extracted', 'Crawl data loaded'], ['generating', 'Spec assembled'],
      ['validating', 'Validating'], ['saved', 'Spec saved'],
    ] as const
    const stageOrder: Record<string, number> = { boxed: 0, extracting: 0, evidence_extracted: 1, generating: 2,
      validating: 3, saved: 4, skipped_existing: 4, failed: -1 }

    return (
      <main className="app-shell">
        <header className="topbar">
          <div>
            <p className="eyebrow">MANUAL FIGURE ANNOTATION</p>
            <h1>{info.title}</h1>
            <p className="subtitle">Drag around every figure, chart, table, or image. Coordinates autosave to normalized JSON.</p>
          </div>
          <div className="save-cluster">
            <button className="save-button" disabled={status === 'saving'} onClick={this.saveNow}>
              <span>✓</span> Save bounding boxes
            </button>
            <span className={`save-state ${status}`}><i />{status === 'saving' ? 'Saving…' : status === 'error' ? 'Save failed' : 'All changes saved'}</span>
            <span className="counter"><strong>{annotatedPages}</strong> / {info.page_count} pages</span>
            <span className="counter"><strong>{totalBoxes}</strong> regions</span>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        <section className="workspace">
          <div className="canvas-column">
            <nav className="page-nav" aria-label="PDF page navigation">
              <button className="arrow-button" disabled={page === 1} onClick={() => this.goToPage(page - 1)} aria-label="Previous page">←</button>
              <label>
                <span>Page</span>
                <select value={page} onChange={(event: ChangeEvent<HTMLSelectElement>) => this.goToPage(Number(event.target.value))}>
                  {Array.from({ length: info.page_count }, (_, index) => index + 1).map((number) => (
                    <option key={number} value={number}>{number} {annotations.pages[String(number)]?.length ? `· ${annotations.pages[String(number)].length} regions` : ''}</option>
                  ))}
                </select>
                <span>of {info.page_count}</span>
              </label>
              <button className="arrow-button" disabled={page === info.page_count} onClick={() => this.goToPage(page + 1)} aria-label="Next page">→</button>
            </nav>
            <PageCanvas page={page} boxes={boxes} selectedId={selectedId} onCreate={this.createBox} onSelect={(id) => this.setState({ selectedId: id })} />
          </div>

          <aside className="sidebar">
            <div className="sidebar-header">
              <div>
                <p className="eyebrow">PAGE {page}</p>
                <h2>Regions</h2>
              </div>
              <span className="page-count">{boxes.length}</span>
            </div>
            <p className="instruction">Click and drag on the PDF. Select a box to name or delete it.</p>

            <div className="region-list">
              {boxes.length === 0 && <div className="empty-state"><div className="draw-icon">⌗</div><strong>No regions yet</strong><span>Draw a rectangle around the first figure.</span></div>}
              {boxes.map((box, index) => (
                <button key={box.id} className={`region-card ${selectedId === box.id ? 'active' : ''}`} onClick={() => this.setState({ selectedId: box.id })}>
                  <span className="region-number">{index + 1}</span>
                  <span><strong>{box.label || `Region ${index + 1}`}</strong><small>{box.kind} · {Math.round(box.x2 - box.x1)} × {Math.round(box.y2 - box.y1)}</small></span>
                </button>
              ))}
            </div>

            {selected && (
              <div className="editor-panel">
                <label>Label<input value={selected.label} maxLength={160} onChange={(event) => this.updateSelected({ label: event.target.value })} /></label>
                <label>Type<select value={selected.kind} onChange={(event) => this.updateSelected({ kind: event.target.value as RegionKind })}>
                  <option value="figure">Figure</option><option value="chart">Chart</option><option value="table">Table</option><option value="image">Image</option><option value="other">Other</option>
                </select></label>
                <div className="coordinate-grid"><span>x {selected.x1.toFixed(1)}</span><span>y {selected.y1.toFixed(1)}</span><span>w {(selected.x2 - selected.x1).toFixed(1)}</span><span>h {(selected.y2 - selected.y1).toFixed(1)}</span></div>
                <button className="delete-button" onClick={this.deleteSelected}>Delete selected region</button>
              </div>
            )}

            <section className="spec-panel" aria-labelledby="spec-panel-title">
              <div className="spec-panel-header">
                <div>
                  <p className="eyebrow">EVIDENCE-GROUNDED</p>
                  <h2 id="spec-panel-title">Figure specifications</h2>
                </div>
                <button className="generate-button" disabled={specs.running} onClick={() => void this.generateSpecs()}>
                  {specs.running ? <><span className="mini-spinner" />Generating…</> : 'Generate specs'}
                </button>
              </div>
              <p className="spec-summary"><strong>{specs.existing_spec_count}</strong> saved of <strong>{specs.boxed_page_count}</strong> boxed pages. Existing reviewed specs are preserved.</p>
              {pageSpec ? (
                <div className={`spec-progress ${pageSpec.state}`}>
                  <header><strong>Page {page}</strong><span>{pageSpec.message}</span></header>
                  <ol>
                    {specStages.map(([key, label], index) => {
                      const current = stageOrder[pageSpec.state] ?? 0
                      const complete = index <= current
                      const active = (key === pageSpec.state) || (pageSpec.state === 'extracting' && key === 'boxed') ||
                        (pageSpec.state === 'skipped_existing' && key === 'saved')
                      return <li key={key} className={`${complete ? 'complete' : ''} ${active ? 'active' : ''}`}><i />{label}</li>
                    })}
                  </ol>
                  {pageSpec.spec_path && <code title={pageSpec.spec_path}>{pageSpec.spec_path.split('/').at(-1)}</code>}
                </div>
              ) : <div className="prompt-empty">Draw and save a box on this page before generating a spec.</div>}
            </section>

            <section className="prompt-panel" aria-labelledby="prompt-panel-title">
              <div className="prompt-panel-header">
                <div>
                  <p className="eyebrow">PAGE {page}</p>
                  <h2 id="prompt-panel-title">Reconstruction prompts</h2>
                </div>
                <span className="page-count">{pagePrompts.length}</span>
              </div>
              {pagePrompts.length === 0 ? (
                <div className="prompt-empty">No recorded figure prompt on this page.</div>
              ) : (
                <div className="prompt-list">
                  <div className="prompt-selectors" aria-label="Prompts on this page">
                    {pagePrompts.map((record, index) => (
                      <button
                        key={record.region_id}
                        className={activePrompt?.region_id === record.region_id ? 'active' : ''}
                        onClick={() => this.setState({ selectedId: record.region_id })}
                      >
                        <span>{index + 1}</span>
                        <span><strong>{record.label}</strong><small>{record.method === 'user_approved' ? 'User-approved method' : record.evidence.chart_structure?.status === 'mapped' ? 'Geometry mapped' : 'Needs visual mapping'}</small></span>
                      </button>
                    ))}
                  </div>
                  {activePrompt && (
                    <article className="prompt-document">
                      <header><strong>{activePrompt.label}</strong><small>{activePrompt.evidence.lines.slice(1, 3).join(' ') || 'Recorded reconstruction strategy'}</small></header>
                      <div className="evidence-chips">
                        <span className={activePrompt.evidence.chart_structure?.status === 'mapped' ? 'mapped' : 'ambiguous'}>
                          {activePrompt.evidence.chart_structure?.status === 'mapped'
                            ? `Geometry mapped · ${activePrompt.evidence.chart_structure.orientation ?? 'chart'} · ${activePrompt.evidence.chart_structure.bars.length} groups`
                            : `Needs visual mapping · ${activePrompt.evidence.chart_structure?.percentage_tokens.length ?? 0} positioned percentage tokens`}
                        </span>
                        {activePrompt.evidence.years.map((value) => <span key={`${activePrompt.region_id}-${value}`}>{value}</span>)}
                      </div>
                      <pre>{activePrompt.prompt}</pre>
                      <div className="prompt-actions">
                        <button onClick={() => void this.copyPrompt(activePrompt)}>{copiedPromptId === activePrompt.region_id ? 'Copied' : 'Copy prompt'}</button>
                        <code title={activePrompt.prompt_file}>{activePrompt.prompt_file.split('/').at(-1)}</code>
                      </div>
                    </article>
                  )}
                </div>
              )}
            </section>

            <div className="sidebar-footer">
              <button className="clear-button" disabled={!boxes.length} onClick={this.clearPage}>Clear page</button>
              <p>Boxes<br/><code>{info.annotation_path}</code></p>
              <p>Prompts<br/><code>{info.prompt_path}</code></p>
              <p>Specs<br/><code>{info.specs_path}</code></p>
            </div>
          </aside>
        </section>
      </main>
    )
  }
}
