import { Bell, Cloud, LoaderCircle, Play } from "lucide-react";
import { useBatchRunner, useIngestionState } from "../store/ingestion";

export function Header() {
  const { isRunning, run } = useBatchRunner();
  const { order, region, backendConnected } = useIngestionState();
  const runtimeOnly = import.meta.env.VITE_DEPLOYMENT_MODE === "runtime";
  return (
    <header className="flex flex-col gap-5 border-b border-white/10 px-5 py-5 lg:flex-row lg:items-center lg:justify-between lg:px-8">
      <div className="flex items-center gap-4">
        <div className="grid size-11 place-items-center rounded-2xl bg-mint text-ink shadow-[0_0_30px_rgba(100,239,182,.18)]">
          <Cloud size={22} strokeWidth={2.4} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold tracking-tight text-white">{runtimeOnly ? "GEHA Advanced RAG" : "Document ingestion"}</h1>
            <span className="rounded-full border border-mint/25 bg-mint/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[.16em] text-mint">AWS</span>
          </div>
          <p className="mt-0.5 text-sm text-fog">{order.length} {runtimeOnly ? "contextual indexes" : "PDFs"} · {runtimeOnly ? "us-west-2" : region} · {backendConnected ? "Backend connected" : "Connecting…"}</p>
        </div>
      </div>
      {!runtimeOnly && <div className="flex items-center gap-2">
        <button className="icon-button" aria-label="Notifications"><Bell size={18} /></button>
        <button onClick={() => void run()} disabled={isRunning} className={isRunning ? "button-secondary opacity-70" : "button-primary"}>
          {isRunning ? <LoaderCircle size={17} className="animate-spin" /> : <Play size={17} fill="currentColor" />}
          {isRunning ? "Document running" : "Run selected"}
        </button>
      </div>}
    </header>
  );
}
