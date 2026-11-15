import { useMemo } from "react";
import { chars, fmt, pct, ratio, shortDoc, STATUS_LABEL, TYPE_HELP, TYPE_LABEL } from "../lib/format";
import { DocStatus, DupType } from "../lib/schema";
import { DEFAULT_FILTERS, useStore } from "../store/useStore";
import { Card, HBarChart, Meter, NumbersFlag, Stat, StatusBadge, TYPE_BG, TypeBadge } from "./ui";

export default function Dashboard() {
  return (
    <div className="space-y-4">
      <Kpis />
      <div className="grid gap-4 lg:grid-cols-2">
        <TypeBreakdown />
        <FamilyBreakdown />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <CoverageSummary />
        <TopDocuments />
      </div>
      <LargestClusters />
      <Method />
    </div>
  );
}

function useReport() {
  return useStore((s) => s.report)!;
}

function Kpis() {
  const { summary: s, clusters } = useReport();
  const verdicts = useStore((st) => st.verdicts);
  const totalPairs = useMemo(() => clusters.reduce((n, c) => n + c.edges.length, 0), [clusters]);
  const reviewed = Object.keys(verdicts).length;
  const processed = s.byStatus.processed + s.byStatus.reviewed;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr_1fr_1fr]">
      <Stat
        emphasis
        label="Redundant chunks"
        value={pct(s.redundantChunks, s.chunks)}
        detail={`${fmt(s.redundantChunks)} of ${fmt(s.chunks)} chunks repeat a chunk kept elsewhere (pairs with differing figures excluded)`}
      />
      <Stat
        label="Chunks in a duplicate group"
        value={pct(s.involvedChunks, s.chunks)}
        detail={`${fmt(s.involvedChunks)} chunks across ${fmt(s.clusters)} groups`}
      />
      <Stat
        label="Redundant text"
        value={pct(s.redundantChars, s.chars)}
        detail={`${chars(s.redundantChars)} of ${chars(s.chars)}`}
      />
      <Stat
        label="Documents processed"
        value={`${processed} / ${s.documents}`}
        detail={
          s.byStatus.failed || s.byStatus.not_processed
            ? `${s.byStatus.failed} failed · ${s.byStatus.not_processed} not processed`
            : "Every source PDF has usable chunks"
        }
      />
      <div className="rounded-xl border border-line bg-surface p-4">
        <div className="text-xs font-medium text-ink-2">Pairs verified by you</div>
        <div className="mt-1 text-2xl font-semibold tracking-tight">
          {fmt(reviewed)} <span className="text-base font-normal text-muted">/ {fmt(totalPairs)}</span>
        </div>
        <div className="mt-2">
          <Meter value={ratio(reviewed, totalPairs)} className="bg-good" />
        </div>
        <div className="mt-1 text-xs text-muted">
          {fmt(s.pairsNumbersDiffer)} look-alike pairs with differing figures to check
        </div>
      </div>
    </div>
  );
}

function TypeBreakdown() {
  const { summary: s } = useReport();
  const setFilters = useStore((st) => st.setFilters);
  const setView = useStore((st) => st.setView);
  const open = (patch: Parameters<typeof setFilters>[0]) => {
    setFilters({ ...DEFAULT_FILTERS, ...patch });
    setView("clusters");
  };
  const typeData = DupType.options.map((t) => ({
    key: t,
    label: TYPE_LABEL[t],
    value: s.byType[t].chunks,
    display: fmt(s.byType[t].chunks),
    colorClass: TYPE_BG[t],
    onClick: () => open({ types: [t] }),
    tooltip: (
      <>
        <div className="font-semibold">{TYPE_LABEL[t]} duplicates</div>
        <div className="text-ink-2">{TYPE_HELP[t]}</div>
        <div className="mt-1">
          {fmt(s.byType[t].chunks)} chunks · {fmt(s.byType[t].pairs)} pairs
        </div>
      </>
    ),
  }));
  const scopeData = (["within-doc", "cross-doc"] as const).map((sc) => ({
    key: sc,
    label: sc === "within-doc" ? "Within one document" : "Across documents",
    value: s.byScope[sc].chunks,
    display: fmt(s.byScope[sc].chunks),
    colorClass: "bg-ink-2",
    onClick: () => open({ scope: sc }),
    tooltip: (
      <>
        <div className="font-semibold">{sc === "within-doc" ? "Repeated inside a document" : "Shared between documents"}</div>
        <div>
          {fmt(s.byScope[sc].chunks)} chunks · {fmt(s.byScope[sc].pairs)} pairs
        </div>
      </>
    ),
  }));
  return (
    <Card title="What kind of duplication" subtitle="Chunks involved in at least one pair of each kind. Click a bar to explore it.">
      <div className="space-y-5 p-4">
        <div>
          <div className="mb-2 flex flex-wrap gap-2">
            {DupType.options.map((t) => (
              <TypeBadge key={t} type={t} />
            ))}
          </div>
          <HBarChart data={typeData} ariaLabel="Chunks by duplicate type" />
        </div>
        <div>
          <div className="mb-1 text-xs font-medium text-ink-2">Where the copies live</div>
          <HBarChart data={scopeData} ariaLabel="Chunks by scope" />
        </div>
        <p className="text-xs text-muted">
          A chunk can be in pairs of more than one kind, so the bars overlap. Pairs found among{" "}
          {fmt(s.candidatePairs)} candidates; {fmt(s.shortChunks)} chunks under the minimum length were only checked
          for exact matches.
        </p>
      </div>
    </Card>
  );
}

function FamilyBreakdown() {
  const { families } = useReport();
  const setFilters = useStore((st) => st.setFilters);
  const setView = useStore((st) => st.setView);
  const data = [...families]
    .filter((f) => f.chunks > 0)
    .sort((a, b) => ratio(b.redundant, b.chunks) - ratio(a.redundant, a.chunks))
    .map((f) => ({
      key: f.family,
      label: f.family,
      value: ratio(f.redundant, f.chunks),
      display: pct(f.redundant, f.chunks),
      onClick: () => {
        setFilters({ ...DEFAULT_FILTERS, family: f.family });
        setView("clusters");
      },
      tooltip: (
        <>
          <div className="font-semibold">{f.family}</div>
          <div>
            {fmt(f.redundant)} of {fmt(f.chunks)} chunks redundant
          </div>
          <div>
            {pct(f.redundantChars, f.chars)} of text · {f.documents} documents
          </div>
        </>
      ),
    }));
  return (
    <Card title="Redundancy by document family" subtitle="Share of each family's chunks that repeat a chunk kept elsewhere.">
      <div className="p-4">
        <HBarChart data={data} ariaLabel="Redundant share by family" />
      </div>
    </Card>
  );
}

function CoverageSummary() {
  const { summary: s, documents } = useReport();
  const setTab = useStore((st) => st.setTab);
  const setCoverage = useStore((st) => st.setCoverage);
  const statusRows = DocStatus.options.map((st) => ({ st, n: s.byStatus[st] }));
  const pagesMissing = documents.reduce((n, d) => n + d.missingPages.length, 0);
  const docsWithGaps = documents.filter((d) => d.missingPages.length > 0).length;
  return (
    <Card
      title="What is processed"
      subtitle="Source PDFs under crawl_dir/raw and how far each got."
      actions={
        <button onClick={() => setTab("coverage")} className="text-xs font-medium text-accent hover:underline">
          Open coverage →
        </button>
      }
    >
      <div className="space-y-4 p-4">
        <ul className="grid grid-cols-2 gap-2">
          {statusRows.map(({ st, n }) => (
            <li key={st}>
              <button
                onClick={() => {
                  setCoverage({ status: st });
                  setTab("coverage");
                }}
                className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-left hover:bg-surface-2"
              >
                <StatusBadge status={st} />
                <span className="text-sm font-semibold">{n}</span>
              </button>
            </li>
          ))}
        </ul>
        <Progress label="Pages that produced chunks" n={s.pagesWithChunks} d={s.pages} />
        <Progress
          label="Pages visually verified"
          n={s.pagesVisuallyVerified}
          d={s.pages}
          note={s.pagesVisuallyVerified === 0 ? "Every candidate run is still awaiting visual review" : undefined}
        />
        <p className="text-xs text-muted">
          {pagesMissing
            ? `${fmt(pagesMissing)} pages in ${docsWithGaps} documents have no chunk (often blank, cover or image-only pages).`
            : "Every page of every processed document produced at least one chunk."}{" "}
          Statuses: {DocStatus.options.map((st) => STATUS_LABEL[st]).join(" → ")}.
        </p>
      </div>
    </Card>
  );
}

function Progress({ label, n, d, note }: { label: string; n: number; d: number; note?: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-ink-2">{label}</span>
        <span className="font-medium">
          {fmt(n)} / {fmt(d)} · {pct(n, d)}
        </span>
      </div>
      <Meter value={ratio(n, d)} />
      {note && <div className="mt-1 text-xs text-muted">{note}</div>}
    </div>
  );
}

function TopDocuments() {
  const { documents } = useReport();
  const openDocument = useStore((s) => s.openDocument);
  const rows = [...documents]
    .filter((d) => d.chunkCount >= 5)
    .sort((a, b) => ratio(b.redundant, b.chunkCount) - ratio(a.redundant, a.chunkCount))
    .slice(0, 10);
  return (
    <Card title="Most redundant documents" subtitle="Documents with at least 5 chunks. Click a row to inspect its chunks.">
      <table className="w-full text-xs">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className="px-4 py-2 font-medium">Document</th>
            <th className="px-2 py-2 text-right font-medium">Chunks</th>
            <th className="px-2 py-2 text-right font-medium">Redundant</th>
            <th className="w-32 px-4 py-2 font-medium">Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr
              key={d.key}
              onClick={() => openDocument(d.key)}
              className="cursor-pointer border-b border-line last:border-0 hover:bg-surface-2"
            >
              <td className="max-w-0 px-4 py-2">
                <div className="truncate font-medium text-ink" title={d.documentId}>
                  {shortDoc(d.documentId)}
                </div>
                <div className="text-muted">{d.family}</div>
              </td>
              <td className="px-2 py-2 text-right">{fmt(d.chunkCount)}</td>
              <td className="px-2 py-2 text-right">{fmt(d.redundant)}</td>
              <td className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <Meter value={ratio(d.redundant, d.chunkCount)} />
                  <span className="w-11 text-right font-medium">{pct(d.redundant, d.chunkCount, 0)}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function LargestClusters() {
  const { clusters } = useReport();
  const docs = useStore((s) => s.docs);
  const selectCluster = useStore((s) => s.selectCluster);
  const setView = useStore((s) => s.setView);
  const setFilters = useStore((s) => s.setFilters);
  return (
    <Card title="Largest duplicate groups" subtitle="Usually boilerplate: criteria headers, disclaimers, repeated table rows.">
      <ul className="divide-y divide-line">
        {clusters.slice(0, 6).map((c) => (
          <li key={c.id}>
            <button
              onClick={() => {
                setFilters(DEFAULT_FILTERS);
                selectCluster(c.id);
                setView("clusters");
              }}
              className="grid w-full gap-1 px-4 py-2.5 text-left hover:bg-surface-2 md:grid-cols-[5rem_1fr_auto]"
            >
              <span className="text-xs font-semibold">
                {c.size} copies
                <span className="block font-normal text-muted">{c.id}</span>
              </span>
              <span className="min-w-0">
                <span className="line-clamp-1 text-xs text-ink">{c.members[0].preview}</span>
                <span className="text-[11px] text-muted">
                  {c.docKeys.length} document{c.docKeys.length > 1 ? "s" : ""} ·{" "}
                  {c.docKeys
                    .slice(0, 2)
                    .map((k) => shortDoc(docs[k]?.documentId ?? k))
                    .join(", ")}
                  {c.docKeys.length > 2 ? "…" : ""}
                </span>
              </span>
              <span className="flex flex-wrap items-center gap-1">
                {c.types.map((t) => (
                  <TypeBadge key={t} type={t} />
                ))}
                {c.numbersDiffer && <NumbersFlag compact />}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Method() {
  const { params: p, elapsedMs } = useReport();
  return (
    <details className="rounded-xl border border-line bg-surface px-4 py-3 text-xs text-ink-2">
      <summary className="cursor-pointer font-medium text-ink">How duplicates are found</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>
          Only the selected run of each document is used: a promoted <code>reviewed/</code> version if one exists,
          otherwise the newest structurally valid candidate run (the same rule as <code>consumer_paths.py</code>).
          Repeated runs of the same PDF are not counted as duplicates.
        </li>
        <li>Exact: identical after lowercasing and stripping whitespace, markdown and HTML tags.</li>
        <li>
          Near: MinHash ({p.numPerm} permutations, {p.bands} LSH bands) over {p.shingleSize}-word shingles proposes
          candidates; each is confirmed with exact Jaccard ≥ {p.nearThreshold}.
        </li>
        <li>
          Containment: ≥ {p.containmentThreshold * 100}% of the smaller chunk's shingles appear in the larger one. Chunks
          under {p.minTokens} words are only checked for exact matches.
        </li>
        <li>
          Pairs whose figures differ (amounts, percentages, years, ratings such as 2A) are flagged as look-alikes:
          similar wording with different figures is usually a different fact. They stay in the explorer for review
          but are not counted as redundant. Among the remaining pairs, each connected group keeps its longest chunk
          as canonical and counts the rest as redundant.
        </li>
        <li>Analysis took {(elapsedMs / 1000).toFixed(1)}s. Re-run with <code>npm run analyze</code>.</li>
      </ul>
    </details>
  );
}
