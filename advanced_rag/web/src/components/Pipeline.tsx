import { Check } from "lucide-react";
import { stages, useSelectedDocument } from "../store/ingestion";

const labels: Record<(typeof stages)[number], string> = {
  queued: "Queued",
  uploading: "S3 upload",
  extracting: "Docling",
  routing: "Route",
  reviewing: "Review",
  embedding: "Context",
  indexing: "Index",
  complete: "Ready",
};

export function Pipeline() {
  const document = useSelectedDocument();
  const current = document ? stages.indexOf(document.stage) : -1;
  return (
    <section className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p className="eyebrow">Execution path</p>
          <h2 className="mt-1 text-sm font-medium text-white">Step Functions · document_ingestion</h2>
        </div>
        <span className="status-dot"><span /> Live state</span>
      </div>
      <div className="overflow-x-auto px-5 py-6">
        <div className="flex min-w-[760px] items-start">
          {stages.map((stage, index) => {
            const finished = index < current || document?.stage === "complete";
            const active = index === current && document?.stage !== "complete";
            return (
              <div key={stage} className="flex flex-1 items-start last:flex-none">
                <div className="flex w-16 flex-col items-center gap-2 text-center">
                  <div className={`grid size-7 place-items-center rounded-full border text-[11px] font-semibold transition ${finished ? "border-mint bg-mint text-ink" : active ? "border-citron bg-citron/10 text-citron ring-4 ring-citron/5" : "border-white/20 bg-white/[.03] text-fog"}`}>
                    {finished ? <Check size={14} strokeWidth={3} /> : index + 1}
                  </div>
                  <span className={`text-[10px] uppercase tracking-[.12em] ${active ? "text-citron" : finished ? "text-mint" : "text-fog"}`}>{labels[stage]}</span>
                </div>
                {index < stages.length - 1 && <div className={`mt-3.5 h-px min-w-5 flex-1 ${index < current ? "bg-mint/70" : "bg-white/10"}`} />}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
