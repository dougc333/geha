import { useEffect, useMemo, useState } from 'react'

type Element = { element_id?: string; type?: string; text?: string; metadata?: Record<string, unknown> }
type DocumentInfo = { filename: string; size_bytes: number; page_count: number; source_url: string }
type Result = {
  elements: Element[]
  summary: { element_count: number; type_counts: Record<string, number>; elapsed_seconds: number; cached: boolean; strategy: string }
}

const formatBytes = (value: number) => `${(value / 1024 / 1024).toFixed(2)} MB`
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Unexpected error'

export function App() {
  const [document, setDocument] = useState<DocumentInfo | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [strategy, setStrategy] = useState('hi_res')
  const [force, setForce] = useState(false)
  const [filter, setFilter] = useState('All')
  const [query, setQuery] = useState('')
  const [showJson, setShowJson] = useState(false)

  useEffect(() => {
    fetch('/api/document')
      .then(async response => {
        if (!response.ok) throw new Error(await response.text())
        return response.json()
      })
      .then(setDocument)
      .catch(reason => setError(messageOf(reason)))
  }, [])

  const types = result ? ['All', ...Object.keys(result.summary.type_counts)] : ['All']
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (result?.elements ?? []).filter(element =>
      (filter === 'All' || element.type === filter) &&
      (!needle || (element.text ?? '').toLowerCase().includes(needle)),
    )
  }, [result, filter, query])

  async function extract() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/extract', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy, infer_table_structure: true, force }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail ?? `Extraction failed (${response.status})`)
      setResult(payload)
      setFilter('All')
    } catch (reason) {
      setError(messageOf(reason))
    } finally {
      setLoading(false)
    }
  }

  return <div className="shell">
    <header>
      <div><div className="eyebrow">UNSTRUCTURED CLOUD API · SINGLE-PAGE TEST</div><h1>Document extraction compare</h1><p>Source page and returned document elements, side by side.</p></div>
      <div className="secure"><i />API key stays server-side</div>
    </header>

    <section className="document-bar">
      <div className="document-id"><b>PDF</b><div><strong>{document?.filename ?? 'Loading source…'}</strong><small>{document ? `${document.page_count} page · ${formatBytes(document.size_bytes)}` : 'Checking file'}</small></div></div>
      <div className="controls">
        <label><span>Strategy</span><select value={strategy} onChange={event => setStrategy(event.target.value)} disabled={loading}><option>hi_res</option><option>fast</option><option>ocr_only</option><option>auto</option><option>vlm</option></select></label>
        <label className="check"><input type="checkbox" checked={force} onChange={event => setForce(event.target.checked)} />Call API again</label>
        <button className="primary" onClick={extract} disabled={loading || !document}>{loading ? 'Extracting…' : 'Extract this page'}</button>
      </div>
    </section>

    {error && <div className="error"><strong>Extraction unavailable</strong><span>{error}</span></div>}

    <main>
      <section className="panel">
        <div className="panel-head"><div><span>01</span><div><h2>Source PDF</h2><p>Original page sent to the API</p></div></div><a href="/api/source.pdf" target="_blank">Open PDF ↗</a></div>
        <div className="pdf-stage">{document && <iframe title="Source PDF" src={`${document.source_url}#page=1&zoom=page-width&toolbar=0&navpanes=0`} />}</div>
      </section>

      <section className="panel">
        <div className="panel-head"><div><span className="accent">02</span><div><h2>Extracted content</h2><p>Elements returned by Unstructured</p></div></div>{result && <em>{result.summary.cached ? 'Cached result' : 'Cloud response'}</em>}</div>

        {!result && !loading && <div className="empty"><div>⌁</div><h3>Ready to compare</h3><p>Send this one-page PDF to the managed API. Titles, narrative text, tables and metadata will appear here.</p><button className="primary" onClick={extract} disabled={!document}>Extract this page</button></div>}
        {loading && <div className="empty"><div className="scan"><i /></div><h3>Extracting document structure</h3><p>Uploading and processing the page with the {strategy} strategy.</p></div>}

        {result && !loading && <>
          <div className="metrics">
            <div><strong>{result.summary.element_count}</strong><span>Elements</span></div>
            <div><strong>{Object.keys(result.summary.type_counts).length}</strong><span>Types</span></div>
            <div><strong>{result.summary.elapsed_seconds.toFixed(2)}s</strong><span>{result.summary.cached ? 'Cache read' : 'API latency'}</span></div>
            <div><strong>{result.summary.strategy}</strong><span>Strategy</span></div>
          </div>
          <div className="tools">
            <div className="tabs">{types.map(type => <button key={type} className={filter === type ? 'active' : ''} onClick={() => setFilter(type)}>{type}{type !== 'All' && <small>{result.summary.type_counts[type]}</small>}</button>)}</div>
            <div className="search"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search extracted text" /><button className={showJson ? 'active' : ''} onClick={() => setShowJson(!showJson)}>JSON</button></div>
          </div>
          {showJson ? <pre className="json">{JSON.stringify(result.elements, null, 2)}</pre> : <div className="elements">
            {visible.map((element, index) => <article key={element.element_id ?? index}>
              <div className="meta"><b>{element.type ?? 'Unknown'}</b><span>Element {index + 1}</span>{typeof element.metadata?.page_number === 'number' && <span>Page {element.metadata.page_number}</span>}</div>
              <p>{element.text || <i>No text returned</i>}</p>
              {element.metadata && <details><summary>Metadata</summary><pre>{JSON.stringify(element.metadata, null, 2)}</pre></details>}
            </article>)}
            {!visible.length && <div className="none">No elements match this filter.</div>}
          </div>}
        </>}
      </section>
    </main>
  </div>
}
