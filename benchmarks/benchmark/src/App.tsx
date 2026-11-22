import { useCallback, useEffect, useMemo, useState } from 'react';
import { BatchSchema, RunListSchema, TimingsSchema, type BenchmarkResult, type RunInfo, type Timings } from './schema';
import TableBenchmark from './TableBenchmark';

function formatTime(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(2)} ms`;
}

function artifactUrl(runId: string, relativePath: string): string {
  return `/api/artifact/${encodeURIComponent(runId)}/${relativePath.split('/').map(encodeURIComponent).join('/')}`;
}

async function getJson(url: string): Promise<unknown> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function Metric({ label, value, detail, tone = 'aqua' }: { label: string; value: string; detail: string; tone?: 'aqua' | 'mint' | 'gold' }) {
  const color = tone === 'mint' ? 'text-mint' : tone === 'gold' ? 'text-gold' : 'text-aqua';
  return <div className="rounded-2xl border border-line bg-panel/90 px-5 py-4 shadow-lg shadow-black/10">
    <p className="text-[11px] font-bold uppercase tracking-[.18em] text-muted">{label}</p>
    <p className={`mt-2 text-3xl font-semibold tracking-tight sm:text-4xl ${color}`}>{value}</p>
    <p className="mt-1 text-xs text-muted">{detail}</p>
  </div>;
}

function DataTable({ result, extraHeaders = [] }: { result: BenchmarkResult; extraHeaders?: string[] }) {
  const table = result.table_records[0];
  if (!table) return <p className="text-sm text-muted">No table extracted.</p>;
  return <div className="overflow-x-auto rounded-xl border border-line scrollbar-thin">
    <table className="w-full min-w-[590px] text-left text-xs">
      <caption className="sr-only">{result.mode} extracted chart data</caption>
      <thead className="bg-[#182740] text-muted"><tr>{table.headers.map(header =>
        <th key={header} scope="col" className={`px-3 py-3 font-semibold ${extraHeaders.includes(header) ? 'text-gold' : ''}`}>{header}</th>
      )}</tr></thead>
      <tbody>{table.rows.map((row, index) =>
        <tr key={index} className="border-t border-line/80 odd:bg-white/[.025]">
          {table.headers.map(header => <td key={header} className={`px-3 py-3 align-top ${extraHeaders.includes(header) ? 'text-gold' : 'text-slate-200'}`}>{row[header] ?? '—'}</td>)}
        </tr>
      )}</tbody>
    </table>
  </div>;
}

function CallList({ result }: { result: BenchmarkResult }) {
  const largest = Math.max(...result.calls.filter(call => call.depth === 0).map(call => call.milliseconds), 1);
  return <ol className="space-y-2" aria-label={`${result.mode} function timings`}>
    {result.calls.map(call => {
      const percent = Math.max(2, Math.min(100, call.milliseconds / largest * 100));
      return <li key={call.call} className={`rounded-xl border border-line/70 bg-[#0c1729] px-3 py-2.5 ${call.depth ? 'ml-4 sm:ml-6' : ''}`}>
        <div className="flex items-start gap-2">
          <span className="w-6 shrink-0 font-mono text-[11px] text-slate-500">{String(call.call).padStart(2, '0')}</span>
          <span className="min-w-0 flex-1 break-words font-mono text-[11px] leading-5 text-slate-200">{call.function}</span>
          <span className={`shrink-0 font-mono text-xs font-semibold ${result.mode === 'html' ? 'text-aqua' : 'text-mint'}`}>{formatTime(call.milliseconds)}</span>
        </div>
        <div className="ml-8 mt-2 h-1.5 overflow-hidden rounded-full bg-[#25354d]">
          <div className={`h-full rounded-full ${result.mode === 'html' ? 'bg-aqua' : 'bg-mint'}`} style={{ width: `${percent}%` }} />
        </div>
        {call.error && <p className="ml-8 mt-1 text-xs text-rose-300">{call.error}</p>}
      </li>;
    })}
  </ol>;
}

function ResultPanel({ result, runId, extraHeaders }: { result: BenchmarkResult | undefined; runId: string; extraHeaders?: string[] }) {
  if (!result) return <section className="rounded-2xl border border-dashed border-line bg-panel/40 p-6 text-muted">This run did not include this path.</section>;
  const html = result.mode === 'html';
  return <section className="min-w-0 overflow-hidden rounded-2xl border border-line bg-panel/90 shadow-xl shadow-black/15">
    <div className={`h-1 ${html ? 'bg-aqua' : 'bg-mint'}`} />
    <div className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-[11px] font-bold uppercase tracking-[.2em] ${html ? 'text-aqua' : 'text-mint'}`}>{html ? 'Path A · model assisted' : 'Path B · deterministic'}</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl">{html ? 'HTML + PNG correction' : 'Existing figure spec'}</h2>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${result.status === 'passed' ? 'bg-emerald-400/10 text-mint' : 'bg-rose-400/10 text-rose-300'}`}>{result.status}</span>
      </div>
      <p className="mt-5 font-mono text-4xl font-semibold tracking-tight text-white">{formatTime(result.total_ms)}</p>
      <p className="mt-2 text-sm leading-6 text-muted">{html ? `${result.iterations} visual iteration${result.iterations === 1 ? '' : 's'} · ${result.model ?? 'model'} · PNG comparison` : 'Native PDF verification · no model calls · no PNG correction loop'}</p>
      <div className="mt-6 border-t border-line pt-5">
        <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold">Function call breakdown</h3><span className="text-xs text-muted">{result.calls.length} timed calls</span></div>
        <CallList result={result} />
        {html && <p className="mt-3 text-xs leading-5 text-muted">Indented calls are included in the correction loop’s parent time. Do not sum every row.</p>}
      </div>
      <div className="mt-6 border-t border-line pt-5">
        <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">Extracted table</h3><span className="text-xs text-muted">{result.table_records[0]?.rows.length ?? 0} rows</span></div>
        <DataTable result={result} extraHeaders={extraHeaders} />
      </div>
      {result.html && <a className={`mt-5 inline-flex rounded-lg border px-3 py-2 text-xs font-semibold hover:bg-white/10 ${html ? 'border-aqua/40 text-aqua' : 'border-mint/40 text-mint'}`} href={artifactUrl(runId, `${result.mode}/${result.html}`)} target="_blank" rel="noreferrer">Open generated HTML ↗</a>}
    </div>
  </section>;
}

function FigureBenchmark() {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<Timings | null>(null);
  const [images, setImages] = useState<{ source: string; rendered: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = RunListSchema.parse(await getJson('/api/runs'));
      setRuns(list);
      setRunId(current => list.some(run => run.id === current) ? current : (list.find(run => run.modes.includes('html') && run.modes.includes('spec'))?.id ?? list[0]?.id ?? ''));
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load runs');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!runId) { setData(null); return; }
    let active = true;
    setLoading(true);
    void (async () => {
      try {
        const parsed = TimingsSchema.parse(await getJson(artifactUrl(runId, 'timings.json')));
        if (!active) return;
        setData(parsed);
        setError('');
        const html = parsed.results.find(result => result.mode === 'html');
        if (html?.batch) {
          const batch = BatchSchema.parse(await getJson(artifactUrl(runId, `html/${html.batch}`)));
          const figure = batch.figures[0];
          if (active && figure) {
            const base = `html/pages/page-004/segments/`;
            setImages({ source: artifactUrl(runId, base + figure.source_png), rendered: artifactUrl(runId, base + figure.final_rendered_png) });
          }
        } else setImages(null);
      } catch (cause) {
        if (active) { setData(null); setImages(null); setError(cause instanceof Error ? cause.message : 'Could not load run'); }
      } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [runId]);

  const htmlResult = useMemo(() => data?.results.find(result => result.mode === 'html'), [data]);
  const specResult = useMemo(() => data?.results.find(result => result.mode === 'spec'), [data]);
  const ratio = data?.comparison?.ratio_html_to_spec ?? (htmlResult && specResult ? htmlResult.total_ms / specResult.total_ms : null);

  return <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_#15324d_0%,_#091020_43%,_#080e1b_100%)]">
    <header className="border-b border-line/80 bg-ink/60 backdrop-blur">
      <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-aqua font-black text-ink">B</div><div><p className="text-lg font-semibold tracking-tight">Document benchmark</p><p className="text-xs text-muted">EY figure · page 004 · local inputs</p></div></div>
        <div className="flex items-center gap-2"><span className="hidden rounded-full border border-mint/30 bg-mint/10 px-3 py-1 text-xs font-semibold text-mint sm:inline-flex">LOCAL · SELF-CONTAINED</span><button onClick={() => void refresh()} className="rounded-lg border border-line bg-panel px-3 py-2 text-xs font-semibold text-slate-200 hover:border-aqua/60 hover:text-aqua">↻ Refresh runs</button></div>
      </div>
    </header>
    <main className="mx-auto max-w-[1680px] px-5 pb-16 pt-9 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div><p className="text-xs font-bold uppercase tracking-[.24em] text-aqua">Figure reconstruction benchmark</p><h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">Same PDF figure. Two extraction paths.</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-muted">Compare model reviewed HTML and PNG reconstruction with reuse of an authored figure spec. Both paths end with semantic table extraction.</p></div>
        <label className="flex min-w-[270px] flex-col gap-2 text-xs font-semibold text-muted">Saved run
          <select value={runId} onChange={event => setRunId(event.target.value)} className="rounded-xl border border-line bg-panel px-4 py-3 text-sm text-white outline-none focus:border-aqua">
            {runs.map(run => <option key={run.id} value={run.id}>{run.id} · {run.modes.join(' + ')}</option>)}
          </select>
        </label>
      </div>
      {error && <div role="alert" className="mt-6 rounded-xl border border-rose-400/40 bg-rose-400/10 p-4 text-sm text-rose-200">{error}</div>}
      {!data && !error && <div className="mt-8 rounded-2xl border border-line bg-panel p-8 text-muted">{loading ? 'Loading saved benchmark…' : 'No saved benchmark runs yet.'}</div>}
      {data && <>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="HTML + PNG path" value={htmlResult ? formatTime(htmlResult.total_ms) : '—'} detail={htmlResult ? `${htmlResult.iterations} iteration${htmlResult.iterations === 1 ? '' : 's'}` : 'Not in this run'} />
          <Metric label="Existing spec path" value={specResult ? formatTime(specResult.total_ms) : '—'} detail="PDF text check + table extraction" tone="mint" />
          <Metric label="Measured ratio" value={ratio ? `${Math.round(ratio).toLocaleString()}×` : '—'} detail="Existing spec reuse vs HTML loop" tone="gold" />
          <Metric label="Shared table values" value={data.comparison ? (data.comparison.shared_rows_equal ? 'Match' : 'Differ') : '—'} detail={data.comparison ? `${data.comparison.shared_headers.length} shared columns` : 'Requires both paths'} tone="mint" />
        </div>
        <div className="mt-7 grid gap-5 xl:grid-cols-2">
          <ResultPanel result={htmlResult} runId={runId} extraHeaders={data.comparison?.html_only_headers} />
          <ResultPanel result={specResult} runId={runId} extraHeaders={data.comparison?.spec_only_headers} />
        </div>
        {images && <section className="mt-7 rounded-2xl border border-line bg-panel/90 p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><p className="text-[11px] font-bold uppercase tracking-[.18em] text-aqua">Visual evidence</p><h2 className="mt-1 text-lg font-semibold">Source crop ↔ selected HTML render</h2></div><span className="text-xs text-muted">Saved correction-loop artifacts</span></div>
          <div className="grid gap-4 lg:grid-cols-2"><figure><figcaption className="mb-2 text-xs font-semibold text-muted">Authoritative PDF crop</figcaption><img className="w-full rounded-lg bg-white" src={images.source} alt="Authoritative Figure 1 crop from the PDF" /></figure><figure><figcaption className="mb-2 text-xs font-semibold text-muted">Selected HTML render</figcaption><img className="w-full rounded-lg bg-white" src={images.rendered} alt="Selected semantic HTML figure render" /></figure></div>
        </section>}
        <section className="mt-7 grid gap-4 rounded-2xl border border-line bg-panel/70 p-5 text-sm leading-6 text-muted sm:p-6 lg:grid-cols-[1fr_auto]">
          <div><h2 className="font-semibold text-white">What this ratio includes</h2><p className="mt-1">The HTML path includes page rasterization, model generation, browser rendering, review and any correction. The spec path checks the existing spec against native PDF text and extracts its table without a PNG or model loop. Historical spec authoring time is excluded.</p>{data.comparison?.html_only_headers.length ? <p className="mt-2 text-gold">HTML-only columns: {data.comparison.html_only_headers.join(', ')}.</p> : null}</div>
          <div className="self-end rounded-xl border border-line bg-ink/70 px-4 py-3 font-mono text-xs text-slate-300">cd /Users/dc/geha/benchmarks<br />.venv/bin/python src/benchmark.py both</div>
        </section>
      </>}
    </main>
  </div>;
}

export default function App() {
  const [view, setView] = useState<'figure' | 'table'>(() => new URLSearchParams(window.location.search).get('view') === 'table' ? 'table' : 'figure');
  const choose = (next: 'figure' | 'table') => {
    setView(next);
    const search = new URLSearchParams(window.location.search);
    if (next === 'table') search.set('view', 'table'); else search.delete('view');
    window.history.replaceState(null, '', `${window.location.pathname}${search.toString() ? `?${search}` : ''}`);
  };
  return <>
    <nav className="flex gap-2 border-b border-line bg-ink px-5 py-3 sm:px-8" aria-label="Benchmark views">
      <button onClick={() => choose('figure')} className={`rounded-lg px-4 py-2 text-sm font-semibold ${view === 'figure' ? 'bg-aqua text-ink' : 'bg-panel text-muted hover:text-white'}`}>EY figure</button>
      <button onClick={() => choose('table')} className={`rounded-lg px-4 py-2 text-sm font-semibold ${view === 'table' ? 'bg-aqua text-ink' : 'bg-panel text-muted hover:text-white'}`}>Bendamustine table</button>
    </nav>
    {view === 'table' ? <TableBenchmark /> : <FigureBenchmark />}
  </>;
}
