import { useEffect, useMemo, useState } from 'react'
import { z } from 'zod'

const Status = z.enum(['discovered', 'missing_from_manifest', 'queued', 'downloading', 'downloaded', 'failed'])
const Asset = z.object({ id: z.string(), title: z.string(), summary: z.string(), url: z.string().url(), year: z.number(), status: Status.optional(), s3_key: z.string().optional(), sha256: z.string().optional(), bytes: z.number().optional(), error: z.string().optional() })
const Inventory = z.object({ rootUrl: z.string().url(), createdAt: z.string(), assets: z.array(Asset), storage: z.object({ bucket: z.string(), prefix: z.string() }).optional() })
type Asset = z.infer<typeof Asset>

const API = import.meta.env.VITE_API_BASE_URL ?? ''

async function getInventory() {
  const response = await fetch(`${API}/api/inventory`)
  if (!response.ok) throw new Error(await response.text())
  return Inventory.parse(await response.json())
}

function App() {
  const [inventory, setInventory] = useState<z.infer<typeof Inventory> | null>(null)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const refresh = () => getInventory().then(setInventory).catch((e) => setError(String(e)))
  useEffect(() => { refresh() }, [])

  const assets = useMemo(() => (inventory?.assets ?? []).filter((asset) => `${asset.title} ${asset.summary} ${asset.year}`.toLowerCase().includes(query.toLowerCase())), [inventory, query])
  const downloaded = inventory?.assets.filter((asset) => asset.status === 'downloaded').length ?? 0
  const failed = inventory?.assets.filter((asset) => asset.status === 'failed').length ?? 0

  async function download(asset: Asset) {
    setBusy(true); setMessage(`Queued ${asset.title}`); setError('')
    try { const response = await fetch(`${API}/api/download`, { method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({asset_id: asset.id}) }); if (!response.ok) throw new Error(await response.text()); await refresh() } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }

  async function downloadAll() {
    setBusy(true); setMessage('Starting the 141-document Step Functions download…'); setError('')
    try { const response = await fetch(`${API}/api/download-all`, { method: 'POST' }); if (!response.ok) throw new Error(await response.text()); const result = await response.json(); setMessage(`Started ${result.count} downloads`); await refresh() } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }

  return <main>
    <header><div><p className="eyebrow">GEHA / PRODUCTION CONTROLS</p><h1>S3 collection downloader</h1><p className="lead">A catalog of every PDF discovered from the GEHA forms-and-documents page, with durable AWS download state.</p></div><button className="primary" disabled={busy || !inventory} onClick={downloadAll}>Download all 141 PDFs</button></header>
    <section className="source"><span className="label">CATALOG ROOT</span><a href={inventory?.rootUrl} target="_blank" rel="noreferrer">{inventory?.rootUrl ?? 'Loading…'}</a><span className="storage">S3-backed · no local crawl directory</span></section>
    <section className="metrics"><div><span>Total assets</span><strong>{inventory?.assets.length ?? '—'}</strong></div><div><span>Downloaded to S3</span><strong>{downloaded}</strong></div><div><span>Failed</span><strong>{failed}</strong></div><div><span>Visible</span><strong>{assets.length}</strong></div></section>
    {message && <p className="message">{message}</p>}{error && <p className="error">{error}</p>}
    <div className="toolbar"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter documents…" /><button onClick={refresh} disabled={busy}>Refresh status</button></div>
    <section className="table-card"><table><thead><tr><th>Document</th><th>Year</th><th>Status</th><th>S3 object</th><th /></tr></thead><tbody>{assets.map((asset) => <tr key={asset.id}><td><strong>{asset.title}</strong><small>{asset.summary}</small></td><td>{asset.year || '—'}</td><td><span className={`badge ${asset.status ?? 'discovered'}`}>{asset.status ?? 'discovered'}</span>{asset.error && <small className="error">{asset.error}</small>}</td><td><code>{asset.s3_key ?? 'Not downloaded'}</code></td><td><button className="secondary" disabled={busy || asset.status === 'downloading' || asset.status === 'downloaded'} onClick={() => download(asset)}>{asset.status === 'downloaded' ? 'Downloaded' : 'Download'}</button></td></tr>)}</tbody></table></section>
  </main>
}

export default App
