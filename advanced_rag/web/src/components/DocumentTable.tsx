import { AlertTriangle, ChevronRight, CircleCheck, Clock3, FileText, LoaderCircle } from "lucide-react";
import { type Stage, useIngestionActions, useIngestionState, useVisibleDocuments } from "../store/ingestion";

const stageStyle: Record<Stage, string> = {
  queued: "text-fog bg-white/5 border-white/10",
  uploading: "text-sky-300 bg-sky-400/10 border-sky-400/20",
  extracting: "text-violet-300 bg-violet-400/10 border-violet-400/20",
  routing: "text-blue-300 bg-blue-400/10 border-blue-400/20",
  reviewing: "text-amber-300 bg-amber-400/10 border-amber-400/20",
  embedding: "text-citron bg-citron/10 border-citron/20",
  indexing: "text-teal-300 bg-teal-400/10 border-teal-400/20",
  complete: "text-mint bg-mint/10 border-mint/20",
};

export function DocumentTable() {
  const documents = useVisibleDocuments();
  const { selectedId } = useIngestionState();
  const { select } = useIngestionActions();
  return (
    <div className="panel overflow-hidden">
      <div className="hidden grid-cols-[minmax(260px,1fr)_105px_110px_110px_36px] border-b border-white/10 px-4 py-3 text-[10px] uppercase tracking-[.15em] text-fog md:grid">
        <span>Document</span><span>Stage</span><span>Progress</span><span>Route</span><span />
      </div>
      <div className="divide-y divide-white/[.07]">
        {documents.map((document) => {
          const selected = document.id === selectedId;
          const issue = (document.reviewIssues ?? 0) > 0;
          const running = document.status === "running";
          const llamaStatus = document.llamaparseStatus;
          const hasPageProgress = document.stage === "extracting" && Boolean(llamaStatus?.total);
          const doclingPhase = llamaStatus?.phase === "docling";
          const completedPageJobs = doclingPhase
            ? llamaStatus?.doclingProcessed ?? 0
            : (llamaStatus?.doclingAccepted ?? 0) + (llamaStatus?.completed ?? 0);
          const pageJobsActive = hasPageProgress && llamaStatus
            ? completedPageJobs + llamaStatus.failed < llamaStatus.total
            : false;
          const indeterminate = running && document.stage === "extracting" && !hasPageProgress;
          const pageProgress = hasPageProgress && llamaStatus
            ? Math.round((completedPageJobs / llamaStatus.total) * 100)
            : document.progress;
          const failed = document.status === "failed";
          const displayedStage = failed ? "failed" : document.stage;
          const displayedStageStyle = failed
            ? "text-red-300 bg-red-400/10 border-red-400/20"
            : stageStyle[document.stage];
          return (
            <button key={document.id} onClick={() => select(document.id)} className={`grid w-full grid-cols-[1fr_auto] items-center gap-3 px-4 py-3.5 text-left transition md:grid-cols-[minmax(260px,1fr)_105px_110px_110px_36px] ${selected ? "bg-mint/[.07] shadow-[inset_2px_0_0_#64efb6]" : "hover:bg-white/[.035]"}`}>
              <div className="flex min-w-0 items-center gap-3">
                <div className={`grid size-9 shrink-0 place-items-center rounded-xl border ${issue ? "border-amber-400/25 bg-amber-400/10 text-amber-300" : "border-white/10 bg-white/[.04] text-fog"}`}>
                  {issue ? <AlertTriangle size={16} /> : <FileText size={16} />}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">{document.filename}</p>
                  <p className="mt-1 font-mono text-[10px] text-fog">{document.sizeMb} MB · {document.pages || "—"} pages · {document.id}</p>
                </div>
              </div>
              <span className={`hidden w-fit rounded-full border px-2 py-1 text-[10px] font-medium capitalize md:block ${displayedStageStyle}`}>{displayedStage}</span>
              <div className="hidden pr-5 md:block">
                <div className="mb-1 flex items-center justify-between font-mono text-[9px] text-fog">
                  <span>{indeterminate ? "PROCESSING" : hasPageProgress && llamaStatus ? `${completedPageJobs}/${llamaStatus.total}` : `${document.progress}%`}</span>
                  {document.stage === "complete" ? (
                    <CircleCheck size={11} className="text-mint" />
                  ) : running || pageJobsActive ? (
                    <LoaderCircle size={11} className="animate-spin text-citron" />
                  ) : failed || document.status === "needs_review" ? (
                    <AlertTriangle size={11} className="text-amber-300" />
                  ) : (
                    <Clock3 size={11} className="text-fog/70" />
                  )}
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-white/10">
                  {indeterminate ? (
                    <div className="h-full w-full animate-pulse rounded-full bg-gradient-to-r from-transparent via-citron to-transparent" />
                  ) : (
                    <div style={{ width: `${pageProgress}%` }} className="h-full rounded-full bg-mint" />
                  )}
                </div>
              </div>
              <span className="hidden font-mono text-[10px] text-fog md:block">{document.route === "policy_rag" ? "POLICY_RAG" : document.route === "whole_document_context" ? "FORM · 1 UNIT" : document.route === "generic_artifacts" ? "GENERIC" : "PENDING"}</span>
              <ChevronRight size={16} className={selected ? "text-mint" : "text-fog"} />
            </button>
          );
        })}
        {!documents.length && <div className="px-5 py-14 text-center text-sm text-fog">No documents match this view.</div>}
      </div>
    </div>
  );
}
