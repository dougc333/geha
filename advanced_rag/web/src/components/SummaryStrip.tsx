import { AlertTriangle, CheckCircle2, Files, TimerReset } from "lucide-react";
import { useIngestionState } from "../store/ingestion";

export function SummaryStrip() {
  const { documents, order } = useIngestionState();
  const all = order.map((id) => documents[id]);
  const complete = all.filter((document) => document.stage === "complete").length;
  const attention = all.filter((document) => (document.reviewIssues ?? 0) > 0).length;
  const active = all.filter((document) => document.status === "running").length;
  const items = [
    { label: "Batch size", value: all.length, note: "PDF documents", icon: Files, color: "text-white" },
    { label: "Complete", value: complete, note: `${Math.round((complete / all.length) * 100)}% of batch`, icon: CheckCircle2, color: "text-mint" },
    { label: "In progress", value: active, note: "3 task concurrency", icon: TimerReset, color: "text-citron" },
    { label: "Needs review", value: attention, note: attention ? "Figure/table checks" : "No blockers", icon: AlertTriangle, color: attention ? "text-amber-300" : "text-fog" },
  ];
  return (
    <section className="grid border-b border-white/10 sm:grid-cols-2 xl:grid-cols-4">
      {items.map(({ label, value, note, icon: Icon, color }) => (
        <div key={label} className="flex items-start justify-between border-white/10 px-5 py-5 sm:border-r lg:px-8">
          <div>
            <p className="eyebrow">{label}</p>
            <p className={`mt-2 text-3xl font-semibold tracking-[-.04em] ${color}`}>{String(value).padStart(2, "0")}</p>
            <p className="mt-1 text-xs text-fog">{note}</p>
          </div>
          <Icon size={18} className={color} />
        </div>
      ))}
    </section>
  );
}
