import { Box, Clock3, Database, FileCode2, RotateCcw, ScanText, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { useIngestionActions, useSelectedDocument } from "../store/ingestion";

export function Inspector() {
  const runtimeOnly = import.meta.env.VITE_DEPLOYMENT_MODE === "runtime";
  const document = useSelectedDocument();
  const { select, retry } = useIngestionActions();
  const [hoveredPage, setHoveredPage] = useState<{ page: number; status: string } | null>(null);
  if (!document) return <aside className="panel hidden min-h-[500px] xl:block" />;
  const llamaStatus = document.llamaparseStatus;
  const hasPageProgress = document.stage === "extracting" && Boolean(llamaStatus?.total);
  const doclingPhase = llamaStatus?.phase === "docling";
  const completedPageJobs = doclingPhase
    ? llamaStatus?.doclingProcessed ?? 0
    : (llamaStatus?.doclingAccepted ?? 0) + (llamaStatus?.completed ?? 0);
  const indeterminate = document.status === "running" && document.stage === "extracting" && !hasPageProgress;
  const displayedProgress = hasPageProgress && llamaStatus
    ? Math.round((completedPageJobs / llamaStatus.total) * 100)
    : document.progress;
  const facts = [
    { label: runtimeOnly ? "Index source" : "Local source", value: runtimeOnly ? `s3://indexes/${document.id}.jsonl` : `runtime/documents/${document.id}/source.pdf`, icon: Box },
    { label: "Execution", value: runtimeOnly ? "Read-only serving tier" : `local://${document.id}`, icon: FileCode2 },
    { label: "OCR engine", value: document.ocrEngine ?? "Pending selection", icon: ScanText },
    { label: "Run artifacts", value: document.runDirectory ?? "Created when processing starts", icon: FileCode2 },
    { label: "Classification", value: document.isPolicy === undefined ? "Pending" : document.isPolicy ? "Policy document" : "Non-policy artifact", icon: ShieldCheck },
    { label: "Destination", value: document.route === "policy_rag" ? "OpenSearch · policy-v1" : document.route === "whole_document_context" ? "Local vector DB · forms · 1 whole-document record" : document.route === "generic_artifacts" ? "S3 · generic-artifacts" : "Pending route", icon: Database },
  ];
  return (
    <aside className="panel min-w-0 overflow-hidden xl:sticky xl:top-5">
      <div className="flex items-start justify-between border-b border-white/10 p-5">
        <div className="min-w-0 pr-3">
          <p className="eyebrow">Document inspector</p>
          <h2 className="mt-2 break-words text-base font-semibold leading-snug text-white">{document.filename}</h2>
        </div>
        <button className="icon-button size-8" onClick={() => select(null)} aria-label="Close inspector"><X size={15} /></button>
      </div>
      <div className="p-5">
        <div className="flex items-center justify-between text-xs text-fog"><span className="capitalize">{indeterminate || hasPageProgress ? "Docling-first extraction" : document.stage}</span><span className="font-mono">{indeterminate ? "PROCESSING" : hasPageProgress && llamaStatus ? `${completedPageJobs}/${llamaStatus.total}` : `${document.progress}%`}</span></div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
          {indeterminate ? (
            <div className="h-full w-full animate-pulse rounded-full bg-gradient-to-r from-transparent via-citron to-transparent" />
          ) : (
            <div className="h-full rounded-full bg-gradient-to-r from-mint to-citron" style={{ width: `${displayedProgress}%` }} />
          )}
        </div>
        {llamaStatus && llamaStatus.total > 0 && (
          <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
            <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-[.12em] text-fog">
              <span>Page jobs</span>
              <span className={hoveredPage ? "text-white" : ""}>
                {hoveredPage
                  ? `Page ${hoveredPage.page} · ${hoveredPage.status}`
                  : doclingPhase
                    ? `${llamaStatus.doclingProcessed ?? 0}/${llamaStatus.total} Docling pages · page ${llamaStatus.currentPage ?? "—"} active`
                    : `${llamaStatus.doclingAccepted ?? 0} Docling · ${llamaStatus.completed} fallback · ${llamaStatus.failed} failed`}
              </span>
            </div>
            <div className="mt-3 grid max-h-32 grid-cols-12 gap-1 overflow-y-auto pr-1">
              {Array.from({ length: llamaStatus.total }, (_, index) => {
                const pageNumber = index + 1;
                const pageState = llamaStatus.pages[String(pageNumber)];
                const status = pageState?.status ?? "pending";
                const activelyProcessing = (status === "submitted" || status === "processing") && document.status === "running" && document.stage === "extracting";
                const displayedStatus = status === "submitted" || status === "processing"
                  ? activelyProcessing ? "processing" : "paused"
                  : status;
                const color = status === "completed"
                  ? "bg-mint"
                  : status === "docling"
                    ? "bg-sky-400"
                  : status === "submitted" || status === "processing"
                    ? activelyProcessing ? "animate-pulse bg-violet-400" : "bg-violet-400/45"
                    : status === "fallback"
                      ? "bg-amber-400"
                    : status === "failed"
                      ? "bg-red-400"
                      : "bg-white/10";
                return (
                  <span
                    key={pageNumber}
                    tabIndex={0}
                    title={`Page ${pageNumber}: ${displayedStatus}`}
                    aria-label={`Page ${pageNumber}: ${displayedStatus}`}
                    onMouseEnter={() => setHoveredPage({ page: pageNumber, status: displayedStatus })}
                    onMouseLeave={() => setHoveredPage(null)}
                    onFocus={() => setHoveredPage({ page: pageNumber, status: displayedStatus })}
                    onBlur={() => setHoveredPage(null)}
                    className={`h-2 cursor-help rounded-sm outline-none ring-white transition-transform hover:scale-y-150 focus:scale-y-150 focus:ring-1 ${color}`}
                  />
                );
              })}
            </div>
          </div>
        )}
        <div className="mt-6 space-y-4">
          {facts.map(({ label, value, icon: Icon }) => (
            <div key={label} className="flex gap-3">
              <Icon size={15} className="mt-0.5 shrink-0 text-mint" />
              <div className="min-w-0"><p className="text-[10px] uppercase tracking-[.14em] text-fog">{label}</p><p className="mt-1 break-all font-mono text-[10px] leading-relaxed text-white/80">{value}</p></div>
            </div>
          ))}
        </div>
        <div className="mt-6 grid grid-cols-5 gap-2">
          {[{ label: "Pages", value: document.pages || "—" }, { label: "Chunks", value: document.chunks ?? "—" }, { label: "Tables", value: document.tables ?? "—" }, { label: "Figures", value: document.figures ?? "—" }, { label: "Issues", value: document.reviewIssues ?? "—" }].map((item) => (
            <div key={item.label} className="rounded-xl border border-white/10 bg-white/[.025] p-3"><p className="text-[9px] uppercase tracking-[.13em] text-fog">{item.label}</p><p className="mt-1.5 text-lg font-semibold text-white">{item.value}</p></div>
          ))}
        </div>
        <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4 font-mono text-[10px] leading-relaxed text-fog">
          <div className="flex items-center gap-2 text-white/80"><Clock3 size={13} className="text-citron" /> Latest event</div>
          <p className="mt-2">{document.stage === "reviewing" && document.reviewIssues ? `${document.reviewIssues} figure/table regions require bounded review.` : document.stage === "complete" ? `Canonical manifest written in ${document.duration}.` : `AWS task entered ${document.stage} stage.`}</p>
        </div>
        {!runtimeOnly && <a href={`/api/documents/${document.id}/source`} target="_blank" rel="noreferrer" className="button-secondary mt-5 w-full"><FileCode2 size={15} /> Open source PDF</a>}
        {document.contextArtifact && <a href={`/api/documents/${document.id}/artifacts/${document.contextArtifact}`} target="_blank" rel="noreferrer" className="button-secondary mt-2 w-full"><Database size={15} /> Open contextual form record</a>}
        {document.pageManifest && <a href="#page-comparison" className="button-secondary mt-2 w-full"><ScanText size={15} /> Compare PDF + Markdown</a>}
        {document.visualManifest && <a href={`/api/documents/${document.id}/artifacts/${document.visualManifest}`} target="_blank" rel="noreferrer" className="button-secondary mt-2 w-full"><Database size={15} /> Open visual manifest</a>}
        {!runtimeOnly && <button onClick={() => void retry(document.id)} className="button-secondary mt-2 w-full"><RotateCcw size={15} /> Restart execution</button>}
        {runtimeOnly && <div className="button-secondary mt-5 w-full cursor-default"><Database size={15} /> Precomputed on Mac · served from S3</div>}
      </div>
    </aside>
  );
}
