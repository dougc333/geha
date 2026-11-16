import { useEffect, useMemo, useState } from "react";
import type { CollectionScan, ExtractionStatus, PdfScan, ScanState } from "./types";

const number = (value: number | null) => value ?? "—";

function StatusPill({ status }: { status: PdfScan["status"] }) {
  return <span className={`status status--${status}`}>{status.replace("_", " ")}</span>;
}

function ExtractionPill({ status }: { status: ExtractionStatus }) {
  return <span className={`status extraction extraction--${status}`}>{status.replace("_", " ")}</span>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PdfRow({
  pdf,
  extractionBusy,
  onExtract,
}: {
  pdf: PdfScan;
  extractionBusy: boolean;
  onExtract: (pdf: PdfScan) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const multipage = (pdf.pageCount ?? 2) > 1;
  return (
    <article className={`pdf ${open ? "pdf--open" : ""}`}>
      <div className="pdf__top">
        <button className="pdf__summary" onClick={() => setOpen((value) => !value)}>
          <span className="pdf__chevron">{open ? "−" : "+"}</span>
          <span className="pdf__identity">
            <strong>{pdf.name}</strong>
            <small>{pdf.path}</small>
          </span>
          <StatusPill status={pdf.status} />
          <span className="pdf__compact-metrics">
            <span><b>{number(pdf.figureCount)}</b> figures</span>
            <span><b>{number(pdf.chartCount)}</b> charts</span>
            <span><b>{number(pdf.tableCount)}</b> tables</span>
            <span><b>{number(pdf.formCount)}</b> forms</span>
          </span>
        </button>
        <div className="pdf__extract-action">
          <ExtractionPill status={pdf.extractionStatus} />
          <button
            className="button button--extract"
            disabled={!multipage || extractionBusy || pdf.extractionStatus === "extracting"}
            onClick={() => void onExtract(pdf)}
          >
            {pdf.extractionStatus === "extracting" ? "Extracting…" :
              pdf.extractionStatus === "completed" ? "Extract again" : "Extract + chunk"}
          </button>
        </div>
      </div>
      {open && (
        <div className="pdf__detail">
          <div className="metric-grid">
            <Metric label="Pages" value={number(pdf.pageCount)} />
            <Metric label="Native text pages" value={number(pdf.nativeTextPages)} />
            <Metric label="Native labels" value={pdf.nativeLabels == null ? "—" : pdf.nativeLabels ? "Yes" : "No"} />
            <Metric label="Native label words" value={number(pdf.nativeLabelCount)} />
            <Metric label="Figures" value={number(pdf.figureCount)} />
            <Metric label="Charts" value={number(pdf.chartCount)} />
            <Metric label="Tables" value={number(pdf.tableCount)} />
            <Metric label="Form-like pages" value={number(pdf.formCount)} />
            <Metric label="Interactive fields" value={number(pdf.formFieldCount)} />
            <Metric label="Scan time" value={pdf.scanSeconds == null ? "—" : `${pdf.scanSeconds.toFixed(1)}s`} />
          </div>
          <dl className="page-lists">
            <div><dt>Figure pages</dt><dd>{pdf.figurePages.join(", ") || "None"}</dd></div>
            <div><dt>Chart pages</dt><dd>{pdf.chartPages.join(", ") || "None"}</dd></div>
            <div><dt>Table pages</dt><dd>{pdf.tablePages.join(", ") || "None"}</dd></div>
            <div><dt>Form pages</dt><dd>{pdf.formPages.join(", ") || "None"}</dd></div>
            <div><dt>Blank-text pages</dt><dd>{pdf.blankTextPages.join(", ") || "None"}</dd></div>
          </dl>
          <div className="classification">
            <div><span>Visual classification</span><strong>{pdf.figureDescription}</strong></div>
            <div><span>Recommendation</span><strong>{pdf.recommendation}</strong></div>
            <div><span>Workflow</span><strong>{pdf.recommendedWorkflow}</strong></div>
          </div>
          <div className="extraction-output">
            <div>
              <span>Multipage Markdown</span>
              <code>{pdf.markdownPath ?? `candidate/${pdf.name.replace(/\.pdf$/i, "")}.md`}</code>
            </div>
            <div>
              <span>Hybrid chunks</span>
              <code>{pdf.chunksPath ?? "candidate/chunks.jsonl"}</code>
            </div>
            <div>
              <span>Page artifacts</span>
              <strong>{pdf.pageHtmlCount} HTML · {pdf.figureSpecCount} specs · {pdf.logicalTableCount} logical tables</strong>
            </div>
            <div>
              <span>Run directory</span>
              <code>{pdf.extractionRunPath ?? "Created under this collection's runs directory"}</code>
            </div>
          </div>
          {pdf.error && <p className="error-message">{pdf.error}</p>}
          {pdf.extractionError && <p className="error-message">Extraction: {pdf.extractionError}</p>}
        </div>
      )}
    </article>
  );
}

function CollectionCard({
  collection,
  extractionBusy,
  onExtract,
}: {
  collection: CollectionScan;
  extractionBusy: boolean;
  onExtract: (pdf: PdfScan) => Promise<void>;
}) {
  const [open, setOpen] = useState(true);
  const percent = collection.total ? Math.round((collection.completed / collection.total) * 100) : 0;
  const totals = useMemo(
    () => collection.pdfs.reduce(
      (acc, pdf) => ({
        figures: acc.figures + (pdf.figureCount ?? 0),
        charts: acc.charts + (pdf.chartCount ?? 0),
        tables: acc.tables + (pdf.tableCount ?? 0),
        forms: acc.forms + (pdf.formCount ?? 0),
      }),
      { figures: 0, charts: 0, tables: 0, forms: 0 },
    ),
    [collection.pdfs],
  );

  return (
    <section className="collection">
      <button className="collection__header" onClick={() => setOpen((value) => !value)}>
        <span>
          <small>COLLECTION</small>
          <strong>{collection.key}</strong>
          <code>{collection.path}</code>
          <em>{collection.recommendation}</em>
        </span>
        <span className="collection__stats">
          <b>{collection.completed}/{collection.total}</b>
          <span>scanned</span>
          <StatusPill status={collection.status} />
          <i>{open ? "−" : "+"}</i>
        </span>
      </button>
      <div className="progress"><span style={{ width: `${percent}%` }} /></div>
      <div className="collection__totals">
        <Metric label="Figures" value={totals.figures} />
        <Metric label="Charts" value={totals.charts} />
        <Metric label="Tables" value={totals.tables} />
        <Metric label="Form pages" value={totals.forms} />
      </div>
      {open && <div className="pdf-list">{collection.pdfs.map((pdf) => (
        <PdfRow
          key={pdf.id}
          pdf={pdf}
          extractionBusy={extractionBusy}
          onExtract={onExtract}
        />
      ))}</div>}
    </section>
  );
}

export default function App() {
  const [state, setState] = useState<ScanState | null>(null);
  const [message, setMessage] = useState("");

  async function refresh() {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error(`State request failed: ${response.status}`);
    setState(await response.json());
  }

  useEffect(() => {
    refresh().catch((error) => setMessage(String(error)));
  }, []);

  useEffect(() => {
    if (!state?.running && !state?.activeExtraction) return;
    const timer = window.setInterval(() => refresh().catch((error) => setMessage(String(error))), 1000);
    return () => window.clearInterval(timer);
  }, [state?.running, state?.activeExtraction]);

  async function startScan(force: boolean) {
    setMessage("");
    const response = await fetch(`/api/scan${force ? "?force=1" : ""}`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      setMessage(payload.error ?? "Could not start scan");
      return;
    }
    setMessage(force ? "Full rescan started." : "Scan started; completed PDFs will be reused.");
    await refresh();
  }

  async function startExtraction(pdf: PdfScan) {
    setMessage("");
    const response = await fetch(`/api/extract/${pdf.id}`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      setMessage(payload.error ?? "Could not start extraction");
      return;
    }
    setMessage(`Docling extraction started for ${pdf.name}.`);
    await refresh();
  }

  if (!state) return <main className="loading">Loading scanner state…</main>;

  const total = state.collections.reduce((sum, collection) => sum + collection.total, 0);
  const completed = state.collections.reduce((sum, collection) => sum + collection.completed, 0);
  const errors = state.collections.reduce((sum, collection) => sum + collection.errors, 0);

  return (
    <main>
      <header className="hero">
        <div className="hero__eyebrow"><span /> DOCUMENT INTELLIGENCE</div>
        <div className="hero__body">
          <div>
            <h1>PDF collection scanner</h1>
            <p>Inspect native labels, figures, charts, tables and form structure across four hardcoded ingestion collections.</p>
          </div>
          <div className="hero__actions">
            <button className="button button--primary" disabled={state.running} onClick={() => startScan(false)}>
              {state.running ? "Scanning…" : "Start scan"}
            </button>
            <button className="button button--secondary" disabled={state.running} onClick={() => startScan(true)}>Rescan all</button>
          </div>
        </div>
        <div className="overview">
          <Metric label="PDFs discovered" value={total} />
          <Metric label="Scans completed" value={completed} />
          <Metric label="Errors" value={errors} />
          <Metric label="Current file" value={state.activePdf ? state.activePdf.split("/").at(-1) ?? "—" : "—"} />
        </div>
      </header>

      {message && <p className="notice">{message}</p>}
      <section className="method-note">
        <strong>Detection method</strong>
        <span>Native PyMuPDF words · substantial raster/vector regions · numeric chart geometry · canonical ingestion table counts · form widgets and form-like pages</span>
      </section>
      <section className="root-panel">
        <div className="root-panel__heading">
          <strong>Four configured run roots</strong>
          <span>Each root is scanned independently; extraction creates a new immutable child run.</span>
        </div>
        <div className="root-grid">
          {state.collections.map((collection) => (
            <div className="root-card" key={collection.key}>
              <span>{collection.key}</span>
              <code>{collection.path}</code>
              <strong>{collection.pdfs.length} PDFs</strong>
              <ul>{collection.pdfs.map((pdf) => <li key={pdf.id}>{pdf.name}</li>)}</ul>
            </div>
          ))}
        </div>
      </section>
      <div className="collections">
        {state.collections.map((collection) => (
          <CollectionCard
            key={collection.key}
            collection={collection}
            extractionBusy={state.running || Boolean(state.activeExtraction)}
            onExtract={startExtraction}
          />
        ))}
      </div>
    </main>
  );
}
