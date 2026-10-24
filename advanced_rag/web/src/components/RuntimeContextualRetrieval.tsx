import { Check, Database, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ingestionApi, type RuntimeIndexRecord } from "../api";

export function RuntimeContextualRetrieval() {
  const [records, setRecords] = useState<RuntimeIndexRecord[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    ingestionApi.runtimeIndexes()
      .then((items) => {
        if (cancelled) return;
        setRecords(items);
        setSelectedId((current) => current || items[0]?.document_id || "");
        setError(null);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load runtime indexes");
      });
    return () => { cancelled = true; };
  }, []);

  const selected = useMemo(
    () => records.find((record) => record.document_id === selectedId) ?? records[0],
    [records, selectedId],
  );
  const approved = records.filter((record) => record.review_status === "approved").length;

  return (
    <section className="cr-workbench">
      <header className="cr-hero">
        <div>
          <p className="cr-eyebrow">PRECOMPUTED ON MAC · SERVED FROM S3</p>
          <h1>Contextual Retrieval Workbench</h1>
          <p className="cr-lede">Inspect the exact source evidence and contextual text used by the AWS retrieval service. No Docling, OCR, contextualization, or judging runs in ECS.</p>
        </div>
        <div className="cr-health ready"><span className="cr-health-dot" /><div><b>Read-only runtime ready</b><small>BAAI/bge-small-en-v1.5 · 384 dimensions</small></div></div>
      </header>

      {error && <div className="cr-error"><span>{error}</span></div>}

      <section className="cr-stats">
        <article><span>Contextual indexes</span><strong>{records.length}</strong></article>
        <article><span>Retrieval units</span><strong>{records.length}</strong></article>
        <article><span>Embedding dimensions</span><strong>{selected?.embedding_dimensions ?? 0}</strong></article>
        <article><span>Approved records</span><strong>{approved}/{records.length}</strong></article>
      </section>

      <main className="cr-workspace">
        <section className="cr-panel cr-documents-panel">
          <div className="cr-panel-heading"><div><p className="cr-eyebrow">S3 INDEX INVENTORY</p><h2>Whole-document artifacts</h2></div><span className="cr-status-pill">{records.length} sources</span></div>
          <div className="cr-document-list">
            {records.map((record) => (
              <button className={`cr-document-row ${record.document_id === selected?.document_id ? "selected" : ""}`} type="button" key={record.document_id} onClick={() => setSelectedId(record.document_id)}>
                <span className="cr-document-state indexed" />
                <span className="cr-document-name"><b>{record.filename}</b><small>{record.pages.length || "whole document"} source pages · 1 unsplit retrieval unit</small></span>
                <span className="cr-row-status">indexed</span>
              </button>
            ))}
          </div>
        </section>

        <section className="cr-panel cr-viewer">
          <div className="cr-panel-heading"><div><p className="cr-eyebrow">CONTEXT INSPECTOR</p><h2>{selected?.filename ?? "Select a document"}</h2></div><span className="cr-status-pill">one unsplit form</span></div>
          {selected && <>
            <div className="cr-chunk-meta"><code>{selected.chunk_id}</code><span>{selected.cluster ?? "forms_directory"}</span><span>{selected.embedding_dimensions} dimensions</span></div>
            <div className="cr-judge-banner pass"><ShieldCheck size={15} /><b>Precomputed artifact</b><span>{selected.review_status === "approved" ? "Approved for retrieval" : "Pending human review · demo override enabled"}</span></div>
            <div className="cr-compare-grid">
              <article className="cr-chunk-card judge-clean"><header><span>01</span><div><b>Complete extracted form</b><small>Preserved source evidence</small></div><em className="cr-quality-badge clean">source</em></header><pre>{selected.text}</pre></article>
              <article className="cr-chunk-card cr-contextual judge-grounded"><header><span>02</span><div><b>Retrieval context</b><small>Generated on Mac from the complete document</small></div><em className="cr-quality-badge grounded">stored</em></header><div className="cr-annotation">{selected.retrieval_context}</div><details open><summary>Text used for contextual embedding</summary><pre>{selected.contextual_retrieval_text}</pre></details></article>
            </div>
          </>}
        </section>
      </main>

      <section className="cr-panel cr-audit">
        <div className="cr-panel-heading"><div><p className="cr-eyebrow">RETRIEVAL STORAGE</p><h2>Immutable serving artifacts</h2></div><Database size={18} /></div>
        <div className="cr-audit-grid">
          <article><span>Processing location</span><strong>Mac</strong></article>
          <article><span>AWS processing</span><strong>Disabled</strong></article>
          <article><span>Vector database</span><code>S3 indexes/ + in-memory rank fusion</code></article>
          <article><span>Job history</span><code>DynamoDB query runs</code></article>
        </div>
        <div className="cr-page-grid">{records.map((record, index) => <button type="button" key={record.document_id} onClick={() => setSelectedId(record.document_id)} className={`${record.document_id === selected?.document_id ? "selected" : ""} complete judge-pass`} title={record.filename}><span>{index + 1}</span><Check size={9} /></button>)}</div>
      </section>
    </section>
  );
}
