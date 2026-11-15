import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import {
  type Cluster,
  type DocChunks,
  type DocStatus,
  type DocumentRow,
  type DupType,
  type Report,
  type Scope,
  type Verdict,
  DocChunks as DocChunksSchema,
  Report as ReportSchema,
  Verdict as VerdictSchema,
  describeIssues,
} from "../lib/schema";

// One store holds the loaded data, the UI selection and the reviewer's
// verdicts, so components read exactly what they need with a selector
// instead of receiving it through props.

export type Tab = "dashboard" | "coverage" | "explorer";
export type ExplorerView = "clusters" | "compare" | "document";

export type Pair = { a: string; b: string };
export const pairKey = (p: Pair) => (p.a < p.b ? `${p.a}|${p.b}` : `${p.b}|${p.a}`);
export const docKeyOf = (uid: string) => uid.slice(0, uid.lastIndexOf(":"));

export type ClusterFilters = {
  types: DupType[];
  scope: "all" | Scope;
  family: string;
  numbersDiffer: boolean;
  review: "all" | "unreviewed" | "reviewed";
  search: string;
  minSize: number;
};

export type CoverageFilters = {
  status: "all" | DocStatus;
  family: string;
  search: string;
  sort: "redundancy" | "name" | "chunks" | "pages";
};

type DocLoad = { state: "loading" } | { state: "ready"; data: DocChunks } | { state: "error"; error: string };

type State = {
  load: { state: "idle" | "loading" | "ready" | "error"; error?: string };
  report: Report | null;
  docs: Record<string, DocumentRow>;
  clusters: Record<string, Cluster>;
  docChunks: Record<string, DocLoad>;

  tab: Tab;
  view: ExplorerView;
  clusterId: string | null;
  pair: Pair | null;
  docKey: string | null;
  focusUid: string | null;
  filters: ClusterFilters;
  coverage: CoverageFilters;
  verdicts: Record<string, Verdict>;

  loadReport: () => Promise<void>;
  loadDoc: (docKey: string) => void;
  setTab: (tab: Tab) => void;
  setView: (view: ExplorerView) => void;
  selectCluster: (id: string | null) => void;
  openPair: (pair: Pair) => void;
  openDocument: (docKey: string, focusUid?: string | null) => void;
  focusChunk: (uid: string | null) => void;
  setFilters: (patch: Partial<ClusterFilters>) => void;
  setCoverage: (patch: Partial<CoverageFilters>) => void;
  setVerdict: (pair: Pair, verdict: Verdict | null) => void;
  importVerdicts: (json: unknown) => number;
};

export const DEFAULT_FILTERS: ClusterFilters = {
  types: ["exact", "near", "containment"],
  scope: "all",
  family: "all",
  numbersDiffer: false,
  review: "all",
  search: "",
  minSize: 2,
};

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      load: { state: "idle" },
      report: null,
      docs: {},
      clusters: {},
      docChunks: {},

      tab: "dashboard",
      view: "clusters",
      clusterId: null,
      pair: null,
      docKey: null,
      focusUid: null,
      filters: DEFAULT_FILTERS,
      coverage: { status: "all", family: "all", search: "", sort: "redundancy" },
      verdicts: {},

      loadReport: async () => {
        if (get().load.state === "loading") return;
        set({ load: { state: "loading" } });
        try {
          const res = await fetch(`${import.meta.env.BASE_URL}data/report.json`, { cache: "no-store" });
          if (!res.ok)
            throw new Error(
              res.status === 404
                ? "No analysis found. Run `npm run analyze` to scan crawl_dir, then reload."
                : `Could not load report.json (HTTP ${res.status}).`,
            );
          const parsed = ReportSchema.safeParse(await res.json());
          if (!parsed.success)
            throw new Error(`report.json does not match the expected shape:\n${describeIssues(parsed.error)}`);
          const report = parsed.data;
          set({
            report,
            docs: Object.fromEntries(report.documents.map((d) => [d.key, d])),
            clusters: Object.fromEntries(report.clusters.map((c) => [c.id, c])),
            clusterId: report.clusters[0]?.id ?? null,
            docKey: report.documents.find((d) => d.chunkCount > 0)?.key ?? null,
            docChunks: {},
            load: { state: "ready" },
          });
        } catch (e) {
          set({ load: { state: "error", error: e instanceof Error ? e.message : String(e) } });
        }
      },

      loadDoc: (docKey) => {
        if (get().docChunks[docKey]) return;
        set((s) => ({ docChunks: { ...s.docChunks, [docKey]: { state: "loading" } } }));
        fetch(`${import.meta.env.BASE_URL}data/docs/${docKey}.json`)
          .then((r) => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
          })
          .then((json) => {
            const parsed = DocChunksSchema.safeParse(json);
            if (!parsed.success) throw new Error(describeIssues(parsed.error));
            set((s) => ({ docChunks: { ...s.docChunks, [docKey]: { state: "ready", data: parsed.data } } }));
          })
          .catch((e: unknown) =>
            set((s) => ({
              docChunks: { ...s.docChunks, [docKey]: { state: "error", error: String(e) } },
            })),
          );
      },

      setTab: (tab) => set({ tab }),
      setView: (view) => set({ tab: "explorer", view }),
      selectCluster: (id) => set({ clusterId: id }),
      // The document view follows the pair: switching to it shows chunk A in place.
      openPair: (pair) =>
        set({ pair, tab: "explorer", view: "compare", docKey: docKeyOf(pair.a), focusUid: pair.a }),
      openDocument: (docKey, focusUid = null) =>
        set({ docKey, focusUid, tab: "explorer", view: "document" }),
      focusChunk: (uid) => set({ focusUid: uid }),
      setFilters: (patch) => set((s) => ({ filters: { ...s.filters, ...patch } })),
      setCoverage: (patch) => set((s) => ({ coverage: { ...s.coverage, ...patch } })),
      setVerdict: (pair, verdict) =>
        set((s) => {
          const verdicts = { ...s.verdicts };
          if (verdict) verdicts[pairKey(pair)] = verdict;
          else delete verdicts[pairKey(pair)];
          return { verdicts };
        }),
      importVerdicts: (json) => {
        const entries =
          json && typeof json === "object" && "verdicts" in json
            ? (json as { verdicts: unknown }).verdicts
            : json;
        if (!entries || typeof entries !== "object") return 0;
        const valid: Record<string, Verdict> = {};
        for (const [k, v] of Object.entries(entries)) {
          const parsed = VerdictSchema.safeParse(v);
          if (parsed.success && k.includes("|")) valid[k] = parsed.data;
        }
        set((s) => ({ verdicts: { ...s.verdicts, ...valid } }));
        return Object.keys(valid).length;
      },
    }),
    {
      name: "duplicate-chunks",
      version: 1,
      storage: createJSONStorage(() => localStorage),
      // Only the reviewer's work and their place in the app survive a reload;
      // the data itself is always re-read from disk.
      partialize: (s) => ({ verdicts: s.verdicts, tab: s.tab, view: s.view, filters: s.filters }),
    },
  ),
);

/** Edges of the clusters that pass the current filters. Shared by the
 * cluster list and the compare view's review queue. */
export function filterClusters(
  clusters: Cluster[],
  f: ClusterFilters,
  verdicts: Record<string, Verdict>,
  docs: Record<string, DocumentRow>,
): Cluster[] {
  const q = f.search.trim().toLowerCase();
  return clusters.filter((c) => {
    if (c.size < f.minSize) return false;
    if (!c.types.some((t) => f.types.includes(t))) return false;
    if (f.scope !== "all" && c.scope !== f.scope) return false;
    if (f.family !== "all" && !c.families.includes(f.family)) return false;
    if (f.numbersDiffer && !c.numbersDiffer) return false;
    if (f.review !== "all") {
      const reviewed = c.edges.every((e) => verdicts[pairKey(e)]);
      if (f.review === "reviewed" ? !reviewed : reviewed) return false;
    }
    if (q) {
      const hay = c.members
        .map((m) => `${m.preview} ${m.section ?? ""} ${docs[m.docKey]?.documentId ?? ""}`)
        .join(" ")
        .toLowerCase();
      if (!hay.includes(q) && c.id !== q) return false;
    }
    return true;
  });
}
