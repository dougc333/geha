import { useStore } from "../../store/useStore";
import { Segmented } from "../ui";
import ClustersView from "./ClustersView";
import CompareView from "./CompareView";
import DocumentView from "./DocumentView";
import FilterBar from "./FilterBar";
import VerdictTools from "./VerdictTools";

const VIEWS = [
  { value: "clusters" as const, label: "Duplicate groups" },
  { value: "compare" as const, label: "Side-by-side compare" },
  { value: "document" as const, label: "Document" },
];

export default function Explorer() {
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented label="Explorer view" value={view} onChange={setView} options={VIEWS} />
        <VerdictTools />
      </div>
      {view !== "document" && <FilterBar />}
      {view === "clusters" && <ClustersView />}
      {view === "compare" && <CompareView />}
      {view === "document" && <DocumentView />}
    </div>
  );
}
