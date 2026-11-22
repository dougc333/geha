import { useEffect, useState } from 'react';
import { z } from 'zod';

const headers = ['Preference', 'Requires Prior Auth', 'Drug Name', 'HCPCS Code', 'Description'];
const SpecSchema = z.object({ model: z.string(), headers: z.array(z.string()), rows: z.array(z.record(z.string())) });
const SpecReportSchema = z.object({ timings_ms: z.object({ pymupdf_evidence_ms: z.number(), llm_ms: z.number(), verification_ms: z.number(), total_ms: z.number() }), token_usage: z.object({ input: z.number(), output: z.number() }).nullable() });
const ValidationSchema = z.object({ source_checks_passed: z.number(), source_checks_total: z.number(), reference_cells_matched: z.number(), reference_cells_total: z.number(), reference_differences: z.array(z.unknown()), reference_review_status: z.string() });
const HtmlReportSchema = z.object({ status: z.string(), iterations: z.number(), html_total_ms: z.number(), prior_spec_total_ms: z.number(), ratio_html_to_spec: z.number(), reference_cells_matched: z.number().nullable(), review: z.object({ passed: z.boolean(), issues: z.array(z.string()) }).nullable(), steps: z.array(z.object({ stage: z.string(), ms: z.number(), iteration: z.number().optional(), input_tokens: z.number().optional(), output_tokens: z.number().optional() })) });

type Spec = z.infer<typeof SpecSchema>;
type SpecReport = z.infer<typeof SpecReportSchema>;
type Validation = z.infer<typeof ValidationSchema>;
type HtmlReport = z.infer<typeof HtmlReportSchema>;

function url(run: string, file: string): string { return `/api/artifact/${run}/${file}`; }
function duration(ms: number): string { return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(2)} ms`; }
async function read(urlValue: string): Promise<unknown> {
  const response = await fetch(urlValue, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}
function cellText(node: Node): string {
  if (node.nodeName === 'BR') return ' ';
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? '';
  return [...node.childNodes].map(cellText).join('');
}

function Table({ title, rows }: { title: string; rows: Record<string, string>[] }) {
  return <div className="min-w-0 overflow-hidden rounded-2xl border border-line bg-panel/90">
    <div className="border-b border-line px-5 py-4"><h3 className="font-semibold">{title}</h3><p className="mt-1 text-xs text-muted">{rows.length} rows · {headers.length} columns</p></div>
    <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-xs"><thead className="bg-[#182740]"><tr>{headers.map(header => <th key={header} className="px-3 py-3 text-muted">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-t border-line odd:bg-white/[.025]">{headers.map(header => <td key={header} className="px-3 py-3 align-top leading-5">{row[header] ?? '—'}</td>)}</tr>)}</tbody></table></div>
  </div>;
}

function StageList({ stages }: { stages: { label: string; ms: number; detail?: string }[] }) {
  const largest = Math.max(...stages.map(stage => stage.ms), 1);
  return <ol className="space-y-2">{stages.map((stage, index) => <li key={`${stage.label}-${index}`} className="rounded-xl border border-line bg-[#0c1729] px-3 py-2.5"><div className="flex items-start justify-between gap-3"><div><span className="font-mono text-xs text-slate-200">{stage.label}</span>{stage.detail && <p className="mt-1 text-xs text-muted">{stage.detail}</p>}</div><span className="shrink-0 font-mono text-xs font-semibold text-aqua">{duration(stage.ms)}</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#25354d]"><div className="h-full rounded-full bg-aqua" style={{ width: `${Math.max(2, stage.ms / largest * 100)}%` }} /></div></li>)}</ol>;
}

export default function TableBenchmark() {
  const [spec, setSpec] = useState<Spec | null>(null);
  const [specReport, setSpecReport] = useState<SpecReport | null>(null);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [htmlReport, setHtmlReport] = useState<HtmlReport | null>(null);
  const [htmlRows, setHtmlRows] = useState<Record<string, string>[]>([]);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [s, r, v] = await Promise.all([
          read(url('bendamustine-table-spec-poc', 'table-spec.json')),
          read(url('bendamustine-table-spec-poc', 'report.json')),
          read(url('bendamustine-table-spec-poc', 'validation.json')),
        ]);
        if (!active) return;
        setSpec(SpecSchema.parse(s)); setSpecReport(SpecReportSchema.parse(r)); setValidation(ValidationSchema.parse(v));
        setError('');
        try {
          const h = HtmlReportSchema.parse(await read(url('bendamustine-html-loop-poc', 'report.json')));
          if (!active) return;
          setHtmlReport(h);
          const page = await fetch(url('bendamustine-html-loop-poc', `iteration-${String(h.iterations).padStart(2, '0')}.html`), { cache: 'no-store' });
          if (page.ok) {
            const document = new DOMParser().parseFromString(await page.text(), 'text/html');
            const table = document.querySelector('table');
            const names = [...(table?.querySelectorAll('thead th') ?? [])].map(node => cellText(node).replace(/\s+/g, ' ').trim());
            const rows = [...(table?.querySelectorAll('tbody tr') ?? [])].map(tr => Object.fromEntries([...(tr.querySelectorAll('th,td'))].map((cell, i) => [names[i], cellText(cell).replace(/\s+/g, ' ').trim()])));
            if (active) setHtmlRows(rows);
          }
        } catch { if (active) { setHtmlReport(null); setHtmlRows([]); } }
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : 'Could not load table benchmark'); }
    })();
    return () => { active = false; };
  }, [refreshKey]);

  const specMs = specReport?.timings_ms.total_ms;
  const htmlMs = htmlReport?.html_total_ms;
  const specStages = specReport ? [
    { label: 'PyMuPDF evidence + crop', ms: specReport.timings_ms.pymupdf_evidence_ms },
    { label: 'Generate table spec · Claude', ms: specReport.timings_ms.llm_ms, detail: `${specReport.token_usage?.input ?? 0} input · ${specReport.token_usage?.output ?? 0} output tokens` },
    { label: 'Local validation', ms: specReport.timings_ms.verification_ms },
  ] : [];
  const htmlStages = htmlReport?.steps.map(step => ({ label: `${step.stage.replaceAll('_', ' ')}${step.iteration ? ` · pass ${step.iteration}` : ''}`, ms: step.ms, detail: step.input_tokens ? `${step.input_tokens} input · ${step.output_tokens} output tokens` : undefined })) ?? [];

  return <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_#15324d_0%,_#091020_43%,_#080e1b_100%)]">
    <header className="border-b border-line/80 bg-ink/60"><div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8"><div><p className="text-lg font-semibold">Bendamustine table benchmark</p><p className="text-xs text-muted">Page 1 · extractable PDF text · one five-row table</p></div><button onClick={() => setRefreshKey(value => value + 1)} className="rounded-lg border border-line bg-panel px-3 py-2 text-xs font-semibold hover:border-aqua">↻ Refresh results</button></div></header>
    <main className="mx-auto max-w-[1680px] px-5 pb-16 pt-9 sm:px-8">
      <p className="text-xs font-bold uppercase tracking-[.24em] text-aqua">Table reconstruction benchmark</p>
      <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">One PDF table. Two timed paths.</h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">Both paths start with PyMuPDF evidence. One asks Claude for structured cells; the other generates HTML, renders PNG, reviews it visually, and corrects it if needed.</p>
      {error && <p role="alert" className="mt-6 rounded-xl border border-rose-400/40 bg-rose-400/10 p-4 text-rose-200">{error}</p>}
      {!specReport && !error && <p className="mt-6 text-muted">Loading saved results…</p>}
      {specReport && <>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['Table spec creation', specMs === undefined ? '—' : duration(specMs), 'Includes model call'],
            ['HTML + PNG loop', htmlMs === undefined ? 'Awaiting run' : duration(htmlMs), htmlReport ? `${htmlReport.iterations} visual pass${htmlReport.iterations === 1 ? '' : 'es'}` : 'No saved result yet'],
            ['Measured ratio', htmlMs && specMs ? `${(htmlMs / specMs).toFixed(2)}×` : '—', 'HTML loop ÷ spec creation'],
            ['Cell agreement', validation ? `${validation.reference_cells_matched}/${validation.reference_cells_total}` : '—', htmlReport ? `HTML: ${htmlReport.reference_cells_matched ?? '—'}/25` : 'Spec vs saved table'],
          ].map(([label, value, detail]) => <div key={label} className="rounded-2xl border border-line bg-panel/90 px-5 py-4"><p className="text-[11px] font-bold uppercase tracking-[.18em] text-muted">{label}</p><p className="mt-2 text-3xl font-semibold text-aqua">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></div>)}
        </div>
        <div className="mt-7 grid gap-5 xl:grid-cols-2">
          <section className="rounded-2xl border border-line bg-panel/90 p-5 sm:p-6"><p className="text-xs font-bold uppercase tracking-widest text-mint">Path A</p><h2 className="mt-2 text-xl font-semibold">PyMuPDF → table spec</h2><p className="mt-2 text-sm text-muted">One model generation call · {validation?.source_checks_passed ?? '—'}/{validation?.source_checks_total ?? '—'} source checks</p><div className="mt-5"><StageList stages={specStages} /></div><a className="mt-5 inline-block text-xs font-semibold text-mint underline" href={url('bendamustine-table-spec-poc', 'table-spec.json')} target="_blank" rel="noreferrer">Open table spec JSON ↗</a></section>
          <section className="rounded-2xl border border-line bg-panel/90 p-5 sm:p-6"><p className="text-xs font-bold uppercase tracking-widest text-aqua">Path B</p><h2 className="mt-2 text-xl font-semibold">HTML → PNG review loop</h2><p className="mt-2 text-sm text-muted">{htmlReport ? `${htmlReport.status} · ${htmlReport.iterations} pass(es)` : 'Awaiting timed run'}</p>{htmlReport ? <><div className="mt-5"><StageList stages={htmlStages} /></div><a className="mt-5 inline-block text-xs font-semibold text-aqua underline" href={url('bendamustine-html-loop-poc', `iteration-${String(htmlReport.iterations).padStart(2, '0')}.html`)} target="_blank" rel="noreferrer">Open final HTML ↗</a></> : <p className="mt-6 rounded-xl border border-dashed border-line p-5 text-sm text-muted">The saved HTML loop result will appear here after the benchmark runs.</p>}</section>
        </div>
        <div className="mt-7 grid gap-5 xl:grid-cols-2">{spec && <Table title="Generated spec cells" rows={spec.rows} />}{htmlReport && <Table title="Final HTML cells" rows={htmlRows} />}</div>
        <section className="mt-7 rounded-2xl border border-line bg-panel/90 p-5 sm:p-6"><h2 className="text-lg font-semibold">Source crop and rendered HTML</h2><div className="mt-4 grid gap-5 lg:grid-cols-2"><figure><figcaption className="mb-2 text-xs text-muted">PDF table crop</figcaption><img className="w-full rounded-lg bg-white" src={url('bendamustine-table-spec-poc', 'table-crop.png')} alt="Bendamustine source table crop" /></figure>{htmlReport && <figure><figcaption className="mb-2 text-xs text-muted">Final HTML PNG</figcaption><img className="w-full rounded-lg bg-white" src={url('bendamustine-html-loop-poc', `iteration-${String(htmlReport.iterations).padStart(2, '0')}.png`)} alt="Rendered final table HTML" /></figure>}</div></section>
        <p className="mt-6 text-xs leading-5 text-muted">The spec and HTML measurements are separate runs on the same copied PDF table. The comparison table is marked {validation?.reference_review_status ?? 'unknown'}; matching it does not make it an approved gold standard. Model latency varies between calls.</p>
      </>}
    </main>
  </div>;
}
