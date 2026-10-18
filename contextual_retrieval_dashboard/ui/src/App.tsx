import { useEffect, useMemo, useRef, useState } from 'react'
import type { CacheTestResult, ChunkPair, ChunkResponse, DocumentProgress, Health, HistoricalRun, HistoryResponse, PromptContract, RunEvent } from './types'

const todayBatch = 'batch-20261016-contextual'

function shortName(source: string): string {
  return source.split('/').at(-1)?.replace(/\.pdf$/i, '') ?? source
}

function eventLabel(event: RunEvent): string {
  const source = event.source ? ` · ${shortName(event.source)}` : ''
  if (event.type === 'contextual_chunk_ready') {
    return `Claude context ${event.index}/${event.total} · ${event.chunk_id}`
  }
  return `${event.type.replaceAll('_', ' ')}${source}`
}

export function App() {
  const [health, setHealth] = useState<Health>()
  const [prompt, setPrompt] = useState<PromptContract>()
  const [promptOpen, setPromptOpen] = useState(true)
  const [cacheTest, setCacheTest] = useState<CacheTestResult>()
  const [cacheTesting, setCacheTesting] = useState(false)
  const [batchId, setBatchId] = useState(todayBatch)
  const [version, setVersion] = useState('2026')
  const [planYear, setPlanYear] = useState(2026)
  const [batchDocument, setBatchDocument] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [status, setStatus] = useState<'loading' | 'idle' | 'starting' | 'running' | 'complete' | 'error'>('loading')
  const [error, setError] = useState<string>()
  const [events, setEvents] = useState<RunEvent[]>([])
  const [history, setHistory] = useState<HistoricalRun[]>([])
  const [selectedHistoryRun, setSelectedHistoryRun] = useState('')
  const [documents, setDocuments] = useState<Record<string, DocumentProgress>>({})
  const [selectedSource, setSelectedSource] = useState<string>()
  const [chunkData, setChunkData] = useState<ChunkResponse>()
  const [selectedChunk, setSelectedChunk] = useState(0)
  const sourceRef = useRef<EventSource | undefined>(undefined)

  useEffect(() => {
    Promise.all([
      fetch('/api/health').then(async response => {
        if (!response.ok) throw new Error(await response.text())
        return response.json() as Promise<Health>
      }),
      fetch('/api/prompt').then(async response => {
        if (!response.ok) throw new Error(await response.text())
        return response.json() as Promise<PromptContract>
      }),
      fetch('/api/history').then(async response => {
        if (!response.ok) throw new Error(await response.text())
        return response.json() as Promise<HistoryResponse>
      }),
    ]).then(([value, promptContract, historyResponse]) => {
      setHealth(value)
      setPrompt(promptContract)
      setHistory(historyResponse.runs)
      setBatchDocument(value.recommended_document)
      const restored = Object.fromEntries(value.documents.map(source => [source, {
        source, canonical: 'queued', contextual: 'queued', chunksDone: 0, chunksTotal: 0,
      }])) as Record<string, DocumentProgress>
      for (const run of historyResponse.runs) {
        if (restored[run.source] && !restored[run.source].run) {
          restored[run.source] = {
            ...restored[run.source],
            run: run.run,
            canonical: 'complete',
            contextual: run.complete ? 'complete' : 'running',
            chunksDone: run.completed_chunks,
            chunksTotal: run.total_chunks,
            markdownVerified: true,
            markdownChars: run.whole_document_chars,
            savedAt: run.updated_at,
            batchId: run.run_id,
          }
        }
      }
      setDocuments(restored)
      const latest = historyResponse.runs[0]
      if (latest) {
        setSelectedHistoryRun(latest.run)
        setSelectedSource(latest.source)
        void fetch(`/api/chunks?run=${encodeURIComponent(latest.run)}`)
          .then(response => response.json() as Promise<ChunkResponse>)
          .then(setChunkData)
      }
      setStatus('idle')
      void fetch('/api/prompt-cache-test')
        .then(response => response.json() as Promise<CacheTestResult>)
        .then(result => { if (result.available !== false) setCacheTest(result) })
    }).catch(reason => {
      setError(String(reason)); setStatus('error')
    })
    return () => sourceRef.current?.close()
  }, [])

  const completed = useMemo(
    () => Object.values(documents).filter(document => document.contextual === 'complete').length,
    [documents],
  )
  const failed = useMemo(
    () => Object.values(documents).filter(document => document.canonical === 'failed' || document.contextual === 'failed').length,
    [documents],
  )
  const chunksDone = useMemo(
    () => Object.values(documents).reduce((sum, document) => sum + document.chunksDone, 0),
    [documents],
  )

  const updateFromEvent = (event: RunEvent) => {
    setEvents(current => [...current, event])
    if (event.source) {
      setDocuments(current => {
        const previous = current[event.source!] ?? {
          source: event.source!, canonical: 'queued', contextual: 'queued',
          chunksDone: 0, chunksTotal: 0,
        }
        const next = { ...previous }
        if (event.type === 'canonical_document_started') next.canonical = 'running'
        if (event.type === 'canonical_document_finished') {
          next.canonical = event.status === 'failed' ? 'failed' : 'complete'
          next.run = event.run
          next.pages = Number(event.pages ?? 0)
          next.tables = Number(event.tables ?? 0)
          next.chunksTotal = Number(event.chunks ?? 0)
          next.error = event.error as string | undefined
        }
        if (event.type === 'contextual_document_started') {
          next.contextual = 'running'; next.run = event.run
        }
        if (event.type === 'canonical_markdown_verified') {
          next.markdownVerified = true
          next.markdownChars = Number(event.markdown_chars ?? 0)
          next.run = event.run
        }
        if (event.type === 'contextual_document_finished') {
          next.contextual = 'complete'; next.run = event.run
          next.chunksDone = Number(event.chunks ?? next.chunksDone)
          next.chunksTotal = Number(event.chunks ?? next.chunksTotal)
        }
        if (event.type === 'contextual_document_failed') {
          next.contextual = 'failed'; next.error = event.error; next.run = event.run
        }
        return { ...current, [event.source!]: next }
      })
    }
    if (event.type === 'contextual_chunk_ready') {
      setDocuments(current => {
        const key = Object.keys(current).find(source => current[source].run === event.run)
        if (!key) return current
        return { ...current, [key]: {
          ...current[key], contextual: 'running',
          chunksDone: Number(event.index ?? 0), chunksTotal: Number(event.total ?? 0),
        }}
      })
    }
    if (event.type === 'batch_failed') {
      setError(String(event.error)); setStatus('error')
    }
  }

  const start = async (scope: 'one' | 'all') => {
    sourceRef.current?.close()
    setStatus('starting'); setError(undefined); setEvents([]); setChunkData(undefined)
    try {
      const response = await fetch('/api/batches', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          batch_id: batchId, document_version: version, plan_year: planYear,
          confirm_contextualization_cost: confirmed,
          document: scope === 'one' ? batchDocument : null,
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error ?? `Start failed (${response.status})`)
      const stream = new EventSource(payload.events)
      sourceRef.current = stream
      setStatus('running')
      stream.onmessage = message => updateFromEvent(JSON.parse(message.data))
      stream.addEventListener('end', () => {
        stream.close(); setStatus(current => current === 'error' ? current : 'complete')
        void fetch('/api/history')
          .then(response => response.json() as Promise<HistoryResponse>)
          .then(result => setHistory(result.runs))
      })
      stream.onerror = () => {
        if (stream.readyState === EventSource.CLOSED) {
          setError('The event stream closed unexpectedly.'); setStatus('error')
        }
      }
    } catch (reason) {
      setError((reason as Error).message); setStatus('error')
    }
  }

  const startVisual = async () => {
    sourceRef.current?.close()
    setStatus('starting'); setError(undefined); setEvents([]); setChunkData(undefined)
    try {
      const response = await fetch('/api/visual-batches', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm_contextualization_cost: confirmed }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error ?? `Start failed (${response.status})`)
      const stream = new EventSource(payload.events)
      sourceRef.current = stream
      setStatus('running')
      stream.onmessage = message => updateFromEvent(JSON.parse(message.data))
      stream.addEventListener('end', () => {
        stream.close(); setStatus(current => current === 'error' ? current : 'complete')
        setSelectedHistoryRun(payload.run)
        setSelectedSource(health?.visual_run?.source)
        void Promise.all([
          fetch('/api/history').then(response => response.json() as Promise<HistoryResponse>),
          fetch(`/api/chunks?run=${encodeURIComponent(payload.run)}`).then(response => response.json() as Promise<ChunkResponse>),
        ]).then(([historyResult, chunksResult]) => {
          setHistory(historyResult.runs)
          setSelectedChunk(0)
          setChunkData(chunksResult)
        })
      })
      stream.onerror = () => {
        if (stream.readyState === EventSource.CLOSED) {
          setError('The event stream closed unexpectedly.'); setStatus('error')
        }
      }
    } catch (reason) {
      setError((reason as Error).message); setStatus('error')
    }
  }

  const selectDocument = async (source: string) => {
    setSelectedSource(source); setSelectedChunk(0); setChunkData(undefined)
    const run = documents[source]?.run
    if (!run) return
    const response = await fetch(`/api/chunks?run=${encodeURIComponent(run)}`)
    if (!response.ok) { setError(await response.text()); return }
    setChunkData(await response.json())
  }

  const selectPastRun = async (runPath: string) => {
    setSelectedHistoryRun(runPath); setSelectedChunk(0); setChunkData(undefined)
    const saved = history.find(run => run.run === runPath)
    if (!saved) return
    setSelectedSource(saved.source)
    const response = await fetch(`/api/chunks?run=${encodeURIComponent(saved.run)}`)
    if (!response.ok) { setError(await response.text()); return }
    setChunkData(await response.json())
  }

  const runCacheTest = async () => {
    setCacheTesting(true); setCacheTest(undefined); setError(undefined)
    try {
      const response = await fetch('/api/prompt-cache-test', { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error ?? `Cache test failed (${response.status})`)
      setCacheTest(payload)
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setCacheTesting(false)
    }
  }

  const pair: ChunkPair | undefined = chunkData?.chunks[selectedChunk]

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">CANONICAL CORPUS INGESTION</p>
          <h1>Contextual Retrieval Workbench</h1>
          <p className="lede">Run contextual retrieval for canonical policy text or saved page-and-figure artifacts, then inspect the exact evidence sent to Claude beside its retrieval context.</p>
        </div>
        <div className="hero-actions">
          <button className="prompt-toggle" onClick={() => setPromptOpen(true)}>Prompt + cache</button>
          <div className={`health ${health?.ready ? 'ready' : 'blocked'}`}>
            <span className="health-dot" />
            <div><b>{health?.ready ? 'Claude ready' : 'Credentials required'}</b><small>{health?.model ?? 'checking backend'}</small></div>
          </div>
        </div>
      </header>

      <aside className="notice">
        <b>Two different ingestion systems</b>
        <span>Coverage policies use deterministic Docling text chunks. The EY visual mode reads an existing agent run and pairs each <code>page-NNN/source.pdf</code> with the highest numbered <code>segments/figure-NN/iteration-NN.png</code>.</span>
      </aside>

      <section className="control-card">
        <div className="field batch-field"><label>Batch ID</label><input value={batchId} onChange={event => setBatchId(event.target.value)} /></div>
        <div className="field version-field"><label>Document version</label><input value={version} onChange={event => setVersion(event.target.value)} /></div>
        <div className="field year-field"><label>Plan year</label><input type="number" value={planYear} onChange={event => setPlanYear(Number(event.target.value))} /></div>
        <div className="field document-picker"><label>One-document test · canonical Markdown required</label><select value={batchDocument} onChange={event => setBatchDocument(event.target.value)}>{health?.documents.map(document => { const readiness = health.document_readiness[document]; return <option key={document} value={document} disabled={!readiness?.batch_markdown_available}>{shortName(document)} · {readiness?.react_converted_source ? 'ReAct-converted source · ' : ''}{readiness?.batch_markdown_available ? 'MD ready' : 'no batch MD'} · ~{health.estimated_context_calls_by_document[document] ?? 0} calls</option> })}</select></div>
        <label className="confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>I understand contextual retrieval makes <b>one Claude call per chunk</b>.</span></label>
        <div className="run-actions"><button className="secondary-run" onClick={() => void start('one')} disabled={!health?.ready || !confirmed || !batchDocument || status === 'running' || status === 'starting'}>{status === 'running' ? 'Running…' : `Run 1 document · ~${health?.estimated_context_calls_by_document[batchDocument] ?? 0} calls`}</button><button onClick={() => void start('all')} disabled={!health?.ready || !confirmed || status === 'running' || status === 'starting'}>{status === 'running' ? 'Running…' : `Run all 35 · ~${health?.estimated_context_calls ?? 0} calls`}</button><button className="visual-run" onClick={() => void startVisual()} disabled={!health?.ready || !health?.visual_run?.available || !confirmed || status === 'running' || status === 'starting'}>{status === 'running' ? 'Running…' : `Run EY figures · ~${health?.visual_run?.estimated_context_calls ?? 0} calls`}</button></div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="stats">
        <article><span>Source PDFs</span><strong>{health?.source_documents ?? '—'}</strong></article>
        <article><span>Contextualized docs</span><strong>{completed}/{health?.source_documents ?? 0}</strong></article>
        <article><span>Chunks completed</span><strong>{chunksDone}</strong></article>
        <article><span>Failures</span><strong className={failed ? 'danger' : ''}>{failed}</strong></article>
      </section>

      <main className="workspace">
        <section className="documents-panel panel">
          <div className="panel-heading"><div><p className="eyebrow">RUNS + LIVE PROGRESS</p><h2>Coverage policies</h2></div><span className="status-pill">{history.length} saved · {status}</span></div>
          <div className="history-picker"><label>Past contextual runs</label><select value={selectedHistoryRun} onChange={event => void selectPastRun(event.target.value)}><option value="">Select a saved run…</option>{history.map(run => <option key={run.run} value={run.run}>{run.artifact_mode === 'visual' ? 'VISUAL · ' : ''}{shortName(run.source)} · {run.completed_chunks}/{run.total_chunks} chunks · {new Date(run.updated_at).toLocaleString()}</option>)}</select></div>
          <div className="document-list">
            {Object.values(documents).map(document => (
              <button className={`document-row ${selectedSource === document.source ? 'selected' : ''}`} key={document.source} onClick={() => void selectDocument(document.source)} disabled={!document.run}>
                <span className={`state ${document.contextual === 'complete' ? 'done' : document.contextual === 'failed' || document.canonical === 'failed' ? 'failed' : document.contextual === 'running' || document.canonical === 'running' ? 'active' : ''}`} />
                <span className="document-name"><b>{shortName(document.source)}</b><small>{document.savedAt ? `Saved ${new Date(document.savedAt).toLocaleString()} · ${document.batchId}` : document.markdownVerified ? `MD verified · ${document.markdownChars?.toLocaleString()} chars` : health?.document_readiness[document.source]?.react_converted_source ? 'ReAct-converted source · batch MD preflight ready' : document.pages ? `${document.pages} pages · ${document.tables} tables` : 'batch MD preflight ready'}</small></span>
                <span className="progress-copy">{document.chunksTotal ? `${document.chunksDone}/${document.chunksTotal}` : document.canonical}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="viewer panel">
          <div className="panel-heading">
            <div><p className="eyebrow">CHUNK INSPECTOR</p><h2>{selectedSource ? shortName(selectedSource) : 'Select a completed document'}</h2></div>
            {chunkData && <select value={selectedChunk} onChange={event => setSelectedChunk(Number(event.target.value))}>{chunkData.chunks.map((chunk, index) => <option key={chunk.chunk_id} value={index}>{index + 1}. {chunk.section} · p. {chunk.pages.join(', ')}</option>)}</select>}
          </div>
          {!pair && <div className="empty-state"><div className="empty-mark">Aa</div><h3>Original and contextual chunks appear here</h3><p>Choose a document after its canonical run starts. Refresh by selecting it again while contextualization is active.</p></div>}
          {pair && <>
            <div className="chunk-meta"><code>{pair.chunk_id}</code><span>pages {pair.pages.join(', ')}</span><span>{pair.section}</span></div>
            <div className="compare-grid">
              <article className="chunk-card original"><header><span>01</span><div><b>{pair.artifact_kind === 'visual' ? 'Original page PDF' : 'Canonical Docling chunk'}</b><small>{pair.artifact_kind === 'visual' ? pair.source_pdf_path : 'Preserved evidence text'}</small></div></header>{pair.artifact_kind === 'visual' && pair.source_pdf_url ? <iframe className="artifact-pdf" title={`Source PDF for ${pair.chunk_id}`} src={pair.source_pdf_url} /> : <><pre>{pair.text}</pre><details><summary>Deterministic provenance string</summary><pre>{pair.deterministic_contextualized_text}</pre></details></>}</article>
              <article className="chunk-card contextual"><header><span>02</span><div><b>{pair.artifact_kind === 'visual' ? 'Latest figure iteration + Claude context' : 'Claude contextual annotation'}</b><small>{pair.artifact_kind === 'visual' ? pair.chunk_image_path : 'Generated from the entire document'}</small></div></header>{pair.artifact_kind === 'visual' && pair.chunk_image_url && <img className="artifact-image" src={pair.chunk_image_url} alt={`Figure chunk ${pair.chunk_id}`} />}<div className="annotation">{pair.retrieval_context ?? 'Context is still being generated.'}</div><details open><summary>Text used for contextual BM25 + embeddings</summary><pre>{pair.contextual_retrieval_text ?? pair.text}</pre></details></article>
            </div>
          </>}
        </section>
      </main>

      <section className="events panel">
        <div className="panel-heading"><div><p className="eyebrow">AUDIT TRAIL</p><h2>Recent events</h2></div><span>{events.length} events</span></div>
        <div className="event-strip">{events.slice(-12).reverse().map(event => <div key={event.seq}><time>{new Date(event.at).toLocaleTimeString()}</time><span>{eventLabel(event)}</span></div>)}</div>
      </section>

      {promptOpen && <>
        <button className="drawer-scrim" aria-label="Close prompt sidebar" onClick={() => setPromptOpen(false)} />
        <aside className="prompt-drawer">
          <header><div><p className="eyebrow">PROMPT INSPECTOR</p><h2>Whole-document cache</h2></div><button onClick={() => setPromptOpen(false)}>×</button></header>
          <div className="cache-contract"><span className="cache-badge">CACHE BREAKPOINT</span><b>The complete document block is cached</b><p>{prompt?.cache_scope}</p><code>cache_control: {JSON.stringify(prompt?.document_cache_control ?? { type: 'ephemeral' })}</code></div>
          <div className="cache-widget">
            <div className="widget-heading"><div><b>Live cache verification</b><small>Two Claude calls using the same full document</small></div><button disabled={cacheTesting || !health?.ready} onClick={() => void runCacheTest()}>{cacheTesting ? 'Testing…' : 'Run 2-call test'}</button></div>
            {!cacheTest && <p className="muted">A pass requires the second API response to report <code>cache_read_input_tokens &gt; 0</code>.</p>}
            {cacheTest && <div className={`cache-result ${cacheTest.passed ? 'pass' : 'fail'}`}>
              <strong>{cacheTest.passed ? 'PASS · cache read verified' : 'FAIL · no cache read reported'}</strong>
              <small>{cacheTest.document} · {cacheTest.document_chars.toLocaleString()} characters</small>
              {cacheTest.tested_at && <small>Verified {new Date(cacheTest.tested_at).toLocaleString()}</small>}
              <div className="cache-metrics"><span>First call<b>{cacheTest.first.cache_creation_input_tokens.toLocaleString()} created</b><em>{cacheTest.first.cache_read_input_tokens.toLocaleString()} read</em></span><span>Second call<b>{cacheTest.second.cache_creation_input_tokens.toLocaleString()} created</b><em>{cacheTest.second.cache_read_input_tokens.toLocaleString()} read</em></span></div>
            </div>}
          </div>
          <section className="prompt-section"><div className="prompt-label"><b>System block 1</b><span>instructions</span></div><pre>{pair?.artifact_kind === 'visual' ? prompt?.visual_system_prompt : prompt?.system_prompt}</pre></section>
          <section className="prompt-section cached"><div className="prompt-label"><b>{pair?.artifact_kind === 'visual' ? 'PDF document block' : 'System block 2'}</b><span>cached · entire document</span></div><pre>{pair?.artifact_kind === 'visual' ? prompt?.visual_document_block?.replace('{{PAGE_SOURCE_PDF}}', pair.source_pdf_path ?? '{{PAGE_SOURCE_PDF}}') : prompt?.document_block ?? '<document>\n{{WHOLE_DOCUMENT}}\n</document>'}</pre></section>
          <section className="prompt-section"><div className="prompt-label"><b>User message</b><span>changes per chunk</span></div><pre>{pair?.artifact_kind === 'visual' ? prompt?.visual_user_template?.replace('{{LATEST_ITERATION_IMAGE}}', pair.chunk_image_path ?? '{{LATEST_ITERATION_IMAGE}}') : prompt?.user_template.replace('{chunk}', pair?.text ?? '{{CHUNK_CONTENT}}')}</pre></section>
          {pair?.prompt_cache && <section className="selected-cache"><b>Selected chunk telemetry</b><span>{pair.prompt_cache.cache_creation_input_tokens.toLocaleString()} cache-write tokens</span><span>{pair.prompt_cache.cache_read_input_tokens.toLocaleString()} cache-read tokens</span></section>}
        </aside>
      </>}
    </div>
  )
}
