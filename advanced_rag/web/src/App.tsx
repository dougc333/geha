import { BrainCircuit, Files, Route } from "lucide-react";
import { useState } from "react";
import { DocumentTable } from "./components/DocumentTable";
import { ClusterRouter } from "./components/ClusterRouter";
import { ContextualRetrieval } from "./components/ContextualRetrieval";
import { RuntimeContextualRetrieval } from "./components/RuntimeContextualRetrieval";
import { Header } from "./components/Header";
import { Inspector } from "./components/Inspector";
import { PageComparison } from "./components/PageComparison";
import { Pipeline } from "./components/Pipeline";
import { SummaryStrip } from "./components/SummaryStrip";
import { Toolbar } from "./components/Toolbar";
import { useIngestionState } from "./store/ingestion";

type WorkspaceTab = "router" | "ingestion" | "contextual";

export default function App() {
  const state = useIngestionState();
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("router");
  const runtimeOnly = import.meta.env.VITE_DEPLOYMENT_MODE === "runtime";

  return (
    <div className="min-h-screen bg-ink text-white">
      <div className="noise" />
      <div className="relative mx-auto min-h-screen max-w-[1680px]">
        <Header />
        <nav aria-label="Workspace views" className="border-b border-white/10 px-4 lg:px-8">
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setActiveTab("router")}
              aria-current={activeTab === "router" ? "page" : undefined}
              className={`relative flex items-center gap-2 px-4 py-3.5 text-xs font-medium transition ${activeTab === "router" ? "text-mint" : "text-fog hover:text-white"}`}
            >
              <Route size={15} /> Query &amp; Cluster Debugging
              {activeTab === "router" && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-mint" />}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("ingestion")}
              aria-current={activeTab === "ingestion" ? "page" : undefined}
              className={`relative flex items-center gap-2 px-4 py-3.5 text-xs font-medium transition ${activeTab === "ingestion" ? "text-mint" : "text-fog hover:text-white"}`}
            >
              <Files size={15} /> Ingestion
              {activeTab === "ingestion" && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-mint" />}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("contextual")}
              aria-current={activeTab === "contextual" ? "page" : undefined}
              className={`relative flex items-center gap-2 px-4 py-3.5 text-xs font-medium transition ${activeTab === "contextual" ? "text-mint" : "text-fog hover:text-white"}`}
            >
              <BrainCircuit size={15} /> Contextual Retrieval
              {activeTab === "contextual" && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-mint" />}
            </button>
          </div>
        </nav>
        {activeTab === "ingestion" && <SummaryStrip />}
        <main className="px-4 py-5 lg:px-8 lg:py-7">
          {state.error && <div className="mb-5 rounded-xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-xs text-amber-200">Backend: {state.error}. Start the Python API on port 8000.</div>}
          {activeTab === "router" ? (
            <div className="space-y-5">
              <ClusterRouter />
              <p className="pb-6 text-center font-mono text-[9px] uppercase tracking-[.16em] text-fog/60">Query routing debugger · TypeSafe JEV with explicit fallback status</p>
            </div>
          ) : activeTab === "contextual" ? (
            runtimeOnly ? <RuntimeContextualRetrieval /> : <ContextualRetrieval />
          ) : (
            <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
              <div className="min-w-0 space-y-5">
                <Pipeline />
                <Toolbar />
                <DocumentTable />
                <PageComparison />
                <p className="pb-6 text-center font-mono text-[9px] uppercase tracking-[.16em] text-fog/60">Control plane preview · no AWS mutations are made by this local UI</p>
              </div>
              <Inspector />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
