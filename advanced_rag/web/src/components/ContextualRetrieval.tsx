import { Check, Database, ExternalLink, Play, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ingestionApi,
  type ContextualJudgeStatus,
  type ContextualJudgment,
  type ContextualPageResult,
  type ContextualRetrievalStatus,
  type FormVectorRecord,
} from "../api";
import {
  useIngestionActions,
  useIngestionState,
  useSelectedDocument,
} from "../store/ingestion";

export function ContextualRetrieval() {
  const state = useIngestionState();
  const selected = useSelectedDocument();
  const selectedId = selected?.id;
  const actions = useIngestionActions();
  const documents = useMemo(
    () => state.order.map((id) => state.documents[id]).filter(Boolean),
    [state.documents, state.order],
  );
  const forms = useMemo(
    () => documents.filter((document) => document.route === "whole_document_context"),
    [documents],
  );
  const [status, setStatus] = useState<ContextualRetrievalStatus | null>(null);
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [pageResult, setPageResult] = useState<ContextualPageResult | null>(null);
  const [judgeStatus, setJudgeStatus] = useState<ContextualJudgeStatus | null>(null);
  const [judgment, setJudgment] = useState<ContextualJudgment | null>(null);
  const [sourceText, setSourceText] = useState<string | null>(null);
  const [loadingSource, setLoadingSource] = useState(false);
  const [loadingPage, setLoadingPage] = useState(false);
  const [starting, setStarting] = useState(false);
  const [judgeStarting, setJudgeStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formVectors, setFormVectors] = useState<FormVectorRecord[]>([]);
  const isWholeForm = selected?.route === "whole_document_context"
    || status?.storage_strategy === "whole_document";

  const refresh = useCallback(async () => {
    if (!selectedId) return;
    try {
      const [next, nextJudge, vectors] = await Promise.all([
        ingestionApi.contextualStatus(selectedId),
        ingestionApi.contextualJudgeStatus(selectedId),
        ingestionApi.formVectorRecords(),
      ]);
      setStatus(next);
      setJudgeStatus(nextJudge);
      setFormVectors(vectors);
      setError(null);
      setSelectedPage((current) => {
        if (current && next.pages.some((page) => page.page === current)) return current;
        return next.current_page
          ?? next.pages.find((page) => page.status === "complete")?.page
          ?? next.pages[0]?.page
          ?? null;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load contextual retrieval status");
    }
  }, [selectedId]);

  useEffect(() => {
    setStatus(null);
    setPageResult(null);
    setJudgeStatus(null);
    setJudgment(null);
    setSourceText(null);
    setSelectedPage(null);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (status?.status !== "running" && judgeStatus?.status !== "running") return;
    const timer = window.setInterval(refresh, 1500);
    return () => window.clearInterval(timer);
  }, [judgeStatus?.status, refresh, status?.status]);

  useEffect(() => {
    const page = status?.pages.find((item) => item.page === selectedPage);
    if (!selectedId || !selectedPage || page?.status !== "complete") {
      setPageResult(null);
      setLoadingPage(false);
      return;
    }
    let cancelled = false;
    setLoadingPage(true);
    ingestionApi.contextualPage(selectedId, selectedPage)
      .then((result) => {
        if (!cancelled) setPageResult(result);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load page context");
      })
      .finally(() => {
        if (!cancelled) setLoadingPage(false);
      });
    return () => { cancelled = true; };
  }, [selectedId, selectedPage, status?.completed_pages]);

  useEffect(() => {
    const page = judgeStatus?.pages.find((item) => item.page === selectedPage);
    if (!selectedId || !selectedPage || page?.status !== "complete") {
      setJudgment(null);
      return;
    }
    let cancelled = false;
    ingestionApi.contextualJudgment(selectedId, selectedPage)
      .then((result) => {
        if (!cancelled) setJudgment(result);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load page judgment");
      });
    return () => { cancelled = true; };
  }, [judgeStatus?.completed_pages, selectedId, selectedPage]);

  const selectedSourceMarkdown = status?.pages.find(
    (page) => page.page === selectedPage,
  )?.source_markdown;

  useEffect(() => {
    if (!selectedId || !selectedPage || !selectedSourceMarkdown || isWholeForm) {
      setSourceText(null);
      setLoadingSource(false);
      return;
    }
    let cancelled = false;
    setLoadingSource(true);
    ingestionApi.contextualPageSource(selectedId, selectedPage)
      .then((text) => {
        if (!cancelled) setSourceText(text);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Unable to load extracted page chunk");
      })
      .finally(() => {
        if (!cancelled) setLoadingSource(false);
      });
    return () => { cancelled = true; };
  }, [isWholeForm, selectedId, selectedPage, selectedSourceMarkdown]);

  const run = async () => {
    if (!selectedId) return;
    setStarting(true);
    setError(null);
    try {
      await ingestionApi.runContextual(selectedId);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start contextual retrieval");
    } finally {
      setStarting(false);
    }
  };

  const runJudge = async () => {
    if (!selectedId) return;
    setJudgeStarting(true);
    setError(null);
    try {
      await ingestionApi.runContextualJudge(selectedId);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start the page judge");
    } finally {
      setJudgeStarting(false);
    }
  };

  const progress = status?.total_pages
    ? Math.round((status.completed_pages / status.total_pages) * 100)
    : 0;
  const selectedPageStatus = status?.pages.find((page) => page.page === selectedPage);
  const selectedJudgeStatus = judgeStatus?.pages.find((page) => page.page === selectedPage);
  const judgeProgress = judgeStatus?.total_pages
    ? Math.round((judgeStatus.completed_pages / judgeStatus.total_pages) * 100)
    : 0;
  const indexedFormIds = new Set(formVectors.map((record) => record.document_id));
  // Keep the legacy "annotated" value readable for runs saved before the state
  // was correctly named "contextualized".
  const contextualizedStates = new Set(["annotated", "contextualized", "judged", "summarized_and_embedded"]);
  const contextualizedDocuments = documents.filter((document) => (
    contextualizedStates.has(document.contextStatus ?? "") || indexedFormIds.has(document.id)
  )).length;
  const failedDocuments = documents.filter((document) => document.contextStatus === "failed").length;
  const completedUnits = documents.reduce((total, document) => (
    total + (contextualizedStates.has(document.contextStatus ?? "") || indexedFormIds.has(document.id)
      ? (document.retrievalUnits ?? (document.route === "whole_document_context" ? 1 : document.pages) ?? 0)
      : 0)
  ), 0);

  return (
    <section className="cr-workbench">
      <header className="cr-hero">
        <div>
          <p className="cr-eyebrow">CANONICAL CORPUS INGESTION</p>
          <h1>Contextual Retrieval Workbench</h1>
          <p className="cr-lede">Add whole-document context to extracted evidence, then inspect the exact source text beside the Claude retrieval context.</p>
        </div>
        <div className={`cr-health ${state.backendConnected ? "ready" : "blocked"}`}>
          <span className="cr-health-dot" />
          <div><b>{state.backendConnected ? "Backend ready" : "Backend unavailable"}</b><small>{status?.model ?? "checking contextual service"}</small></div>
        </div>
      </header>

      <section className="cr-control-card">
        <label className="cr-field cr-document-picker">
          <span>Source document</span>
          <select value={selected?.id ?? ""} onChange={(event) => actions.select(event.target.value || null)}>
            {documents.map((document) => <option key={document.id} value={document.id}>{document.filename}</option>)}
          </select>
        </label>
        <div className="cr-field cr-run-state">
          <span>Run state</span>
          <div className={`cr-state-box ${status?.status ?? "idle"}`}><b>{status?.status ?? "loading"}</b><em>{status?.completed_pages ?? 0} / {status?.total_pages ?? 0}</em></div>
        </div>
        <button className="cr-run-button" type="button" onClick={run} disabled={!selected || starting || status?.status === "running" || status?.total_pages === 0}>
          {starting || status?.status === "running" ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
          {status?.completed_pages ? "Run again" : isWholeForm ? "Run whole form" : "Run page context"}
        </button>
        <button className="cr-judge-button" type="button" onClick={runJudge} disabled={!selected || isWholeForm || judgeStarting || judgeStatus?.status === "running" || !status?.completed_pages}>
          {judgeStarting || judgeStatus?.status === "running" ? <RefreshCw className="animate-spin" size={16} /> : <ShieldCheck size={16} />}
          {judgeStatus?.completed_pages ? "Run judge again" : "Judge contexts"}
        </button>
        <div className="cr-progress-copy"><span>{isWholeForm ? "Whole-document context and embedding" : status?.current_page ? `Processing page ${status.current_page}` : "Page checkpoint progress"}</span><b>{progress}%</b></div>
        <div className="cr-progress"><span style={{ width: `${progress}%` }} /></div>
        {!isWholeForm && <><div className="cr-progress-copy cr-judge-progress-copy"><span>{judgeStatus?.current_page ? `Judging source + context for page ${judgeStatus.current_page}` : "Independent source/context integrity judge"}</span><b>{judgeStatus?.completed_pages ?? 0}/{judgeStatus?.total_pages ?? 0} · {judgeProgress}%</b></div><div className="cr-progress cr-judge-progress"><span style={{ width: `${judgeProgress}%` }} /></div></>}
      </section>

      {(error || status?.error || judgeStatus?.error) && <div className="cr-error"><TriangleAlert size={15} /><span>{error ?? status?.error ?? judgeStatus?.error}</span></div>}

      <section className="cr-stats">
        <article><span>Source PDFs</span><strong>{documents.length}</strong></article>
        <article><span>Contextualized docs</span><strong>{contextualizedDocuments}/{documents.length}</strong></article>
        <article><span>Retrieval units</span><strong>{completedUnits}</strong></article>
        <article><span>Whole forms indexed</span><strong>{formVectors.length}/{forms.length}</strong></article>
      </section>

      <main className="cr-workspace">
        <section className="cr-panel cr-documents-panel">
          <div className="cr-panel-heading"><div><p className="cr-eyebrow">DOCUMENTS + LIVE PROGRESS</p><h2>Ingestion corpus</h2></div><span className="cr-status-pill">{failedDocuments ? `${failedDocuments} failed` : `${documents.length} sources`}</span></div>
          <div className="cr-state-legend" aria-label="Document status colors">
            <span><i className="cr-document-state" />Queued</span>
            <span><i className="cr-document-state active" />Processing</span>
            <span><i className="cr-document-state extracted" />Extracted</span>
            <span><i className="cr-document-state contextualized" />Contextualized</span>
            <span><i className="cr-document-state judged" />Judged</span>
            <span><i className="cr-document-state indexed" />Indexed</span>
            <span><i className="cr-document-state failed" />Failed</span>
          </div>
          <div className="cr-document-list">
            {documents.map((document) => {
              const wholeForm = document.route === "whole_document_context";
              const indexed = indexedFormIds.has(document.id);
              const active = document.id === selected?.id && status?.status === "running";
              const contextDone = contextualizedStates.has(document.contextStatus ?? "") || indexed;
              const sourceReady = document.stage === "complete"
                || document.sourceExtractionStatus === "complete"
                || Boolean(document.pageManifest);
              const sourcePartial = document.sourceExtractionStatus === "partial";
              const stateClass = active || sourcePartial
                ? "active"
                : document.contextStatus === "failed"
                  ? "failed"
                  : document.contextStatus === "judged"
                    ? "judged"
                    : document.contextStatus === "contextualized" || document.contextStatus === "annotated"
                      ? "contextualized"
                      : indexed
                        ? "indexed"
                        : sourceReady
                          ? "extracted"
                          : "";
              const rowStatus = document.contextStatus === "judged"
                ? "judged"
                : document.contextStatus === "contextualized" || document.contextStatus === "annotated"
                  ? "contextualized"
                  : contextDone
                    ? "indexed"
                : sourceReady
                  ? "extracted"
                  : sourcePartial
                    ? `${document.extractedPages ?? 0}/${document.pages} extracted`
                  : document.contextStatus ?? document.stage;
              const contextSources = Object.entries(document.contextSources ?? {})
                .filter((entry): entry is [string, number] => typeof entry[1] === "number" && entry[1] > 0);
              return (
                <button className={`cr-document-row ${document.id === selected?.id ? "selected" : ""}`} type="button" key={document.id} onClick={() => actions.select(document.id)}>
                  <span title={rowStatus} className={`cr-document-state ${stateClass}`} />
                  <span className="cr-document-name">
                    <b>{document.filename}</b>
                    <small>{wholeForm ? `${document.pages} source pages · 1 unsplit retrieval unit` : `${document.pages} pages · ${document.retrievalUnits ?? document.pages} retrieval units`}</small>
                    {contextSources.length > 0 && <small className="cr-source-engines">
                      <span>Claude source</span>
                      {contextSources.map(([engine, count]) => <em className={`cr-source-engine ${engine}`} key={engine}>{engine} {count}</em>)}
                    </small>}
                  </span>
                  <span className="cr-row-status">{wholeForm && !sourceReady ? "form" : rowStatus}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="cr-panel cr-viewer">
          <div className="cr-panel-heading">
            <div><p className="cr-eyebrow">CONTEXT INSPECTOR</p><h2>{selected?.filename ?? "Select a document"}</h2></div>
            {!isWholeForm && status?.pages.length ? <select value={selectedPage ?? ""} onChange={(event) => setSelectedPage(Number(event.target.value))}>{status.pages.map((page) => <option key={page.page} value={page.page}>Page {page.page} · {page.status === "complete" ? "contextualized" : page.status}</option>)}</select> : <span className="cr-status-pill">{isWholeForm ? "one unsplit form" : "no pages"}</span>}
          </div>

          {selected && <div className="cr-chunk-meta"><code>{selected.id}</code><span>{isWholeForm ? `${status?.source_page_count ?? selected.pages} source pages` : `page ${selectedPage ?? "—"}`}</span><span>{status?.model ?? "Claude"}</span>{status?.source_uri && <a href={status.source_uri} target="_blank" rel="noreferrer">Open source PDF <ExternalLink size={12} /></a>}</div>}

          {!isWholeForm && selectedPage && <div className={`cr-judge-banner ${selectedJudgeStatus?.verdict ?? selectedJudgeStatus?.status ?? "pending"}`}>
            {selectedJudgeStatus?.status === "processing" ? <RefreshCw className="animate-spin" size={15} /> : <ShieldCheck size={15} />}
            <b>{selectedJudgeStatus?.status === "processing" ? `LLM judge is reviewing page ${selectedPage}` : selectedJudgeStatus?.verdict ? `Judge: ${selectedJudgeStatus.verdict}` : "Not judged yet"}</b>
            <span>{selectedJudgeStatus?.verdict ? `${Math.round((selectedJudgeStatus.confidence ?? 0) * 100)}% confidence` : "The judge checks source corruption and context grounding separately."}</span>
          </div>}

          {loadingPage || loadingSource ? <div className="cr-empty-state"><RefreshCw className="animate-spin" size={24} /><h3>Loading extracted evidence</h3></div> : pageResult || sourceText ? (
            <div className="cr-compare-grid">
              <article className={`cr-chunk-card judge-${judgment?.source_integrity ?? "pending"}`}>
                <header><span>01</span><div><b>{isWholeForm ? "Complete extracted form" : "Original extracted page"}</b><small>Preserved source evidence</small></div>{judgment && <em className={`cr-quality-badge ${judgment.source_integrity}`}>{judgment.source_integrity}</em>}</header>
                <pre>{pageResult?.text ?? sourceText}</pre>
              </article>
              <article className={`cr-chunk-card cr-contextual judge-${judgment?.context_grounding ?? "pending"}`}>
                <header><span>02</span><div><b>Claude retrieval context</b><small>Generated from the complete document</small></div>{judgment && <em className={`cr-quality-badge ${judgment.context_grounding}`}>{judgment.context_grounding.replace("_", " ")}</em>}</header>
                {pageResult ? <>
                  <div className="cr-annotation">{pageResult.retrieval_context}</div>
                  <details open><summary>Text used for contextual embedding</summary><pre>{pageResult.contextual_retrieval_text}</pre></details>
                </> : <div className="cr-pending-context"><RefreshCw size={20} /><b>Contextual embedding pending</b><p>The extracted page chunk is available on the left. Run page context to add document-aware Claude retrieval context and an embedding.</p></div>}
              </article>
            </div>
          ) : (
            <div className="cr-empty-state"><div className="cr-empty-mark">Aa</div><h3>Original and contextual evidence appear here</h3><p>{selectedPageStatus?.status === "processing" ? isWholeForm ? "Claude is contextualizing the complete form." : `Claude is contextualizing page ${selectedPage}.` : status?.total_pages ? "Select a completed page or start contextual retrieval." : "Complete ingestion for this document before contextual retrieval."}</p></div>
          )}
          {judgment && <div className={`cr-judge-report ${judgment.verdict}`}>
            <div><ShieldCheck size={18} /><b>{judgment.verdict.toUpperCase()}</b><span>{Math.round(judgment.confidence * 100)}% confidence</span></div>
            <p>{judgment.rationale}</p>
            <section><article><b>Source issues</b>{judgment.source_issues.length ? <ul>{judgment.source_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : <span>None detected</span>}</article><article><b>Context issues</b>{judgment.context_issues.length ? <ul>{judgment.context_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : <span>None detected</span>}</article></section>
          </div>}
        </section>
      </main>

      <section className="cr-panel cr-audit">
        <div className="cr-panel-heading"><div><p className="cr-eyebrow">RETRIEVAL STORAGE</p><h2>{isWholeForm ? "One unsplit form record" : "Page-level checkpoints"}</h2></div><Database size={18} /></div>
        <div className="cr-audit-grid">
          <article><span>Cache created</span><strong>{(status?.cache_creation_input_tokens ?? 0).toLocaleString()}</strong></article>
          <article><span>Cache reads</span><strong>{(status?.cache_read_input_tokens ?? 0).toLocaleString()}</strong></article>
          <article><span>Vector database</span><code>{status?.vector_database ?? "runtime/vector-db/contextual.sqlite3"}</code></article>
          <article><span>Filesystem source</span><code>{status?.source_path ?? `runtime/documents/${selected?.id ?? "—"}/source.pdf`}</code></article>
        </div>
        {!isWholeForm && status?.pages.length ? <div className="cr-page-grid">{status.pages.map((page) => { const judged = judgeStatus?.pages.find((item) => item.page === page.page); const contextLabel = page.status === "complete" ? "contextualized" : page.status; return <button type="button" key={page.page} onClick={() => setSelectedPage(page.page)} title={`Page ${page.page}: context ${contextLabel}; judge ${judged?.verdict ?? judged?.status ?? "pending"}`} className={`${selectedPage === page.page ? "selected" : ""} ${page.status} judge-${judged?.verdict ?? judged?.status ?? "pending"}`}><span>{page.page}</span>{judged?.verdict ? <i className={`cr-judge-dot ${judged.verdict}`} /> : page.status === "complete" && <Check size={9} />}</button>; })}</div> : null}
      </section>
    </section>
  );
}
