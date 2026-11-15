import { useMemo, useState } from "react";
import { fmt, pct, ratio, shortDoc, STATUS_LABEL } from "../lib/format";
import { DocStatus, type DocumentRow } from "../lib/schema";
import { type CoverageFilters, useStore } from "../store/useStore";
import { Card, Empty, Meter, SearchBox, Segmented, Select, StatusBadge } from "./ui";

export default function Coverage() {
  const report = useStore((s) => s.report)!;
  const f = useStore((s) => s.coverage);
  const setCoverage = useStore((s) => s.setCoverage);

  const rows = useMemo(() => {
    const q = f.search.trim().toLowerCase();
    const list = report.documents.filter(
      (d) =>
        (f.status === "all" || d.status === f.status) &&
        (f.family === "all" || d.family === f.family) &&
        (!q || `${d.documentId} ${d.sourcePath ?? ""}`.toLowerCase().includes(q)),
    );
    const by: Record<CoverageFilters["sort"], (a: DocumentRow, b: DocumentRow) => number> = {
      redundancy: (a, b) => ratio(b.redundant, b.chunkCount) - ratio(a.redundant, a.chunkCount),
      name: (a, b) => a.family.localeCompare(b.family) || a.documentId.localeCompare(b.documentId),
      chunks: (a, b) => b.chunkCount - a.chunkCount,
      pages: (a, b) => b.missingPages.length - a.missingPages.length,
    };
    return list.sort(by[f.sort]);
  }, [report.documents, f]);

  const counts = useMemo(() => {
    const c = Object.fromEntries(DocStatus.options.map((s) => [s, 0])) as Record<DocStatus, number>;
    for (const d of report.documents) if (f.family === "all" || d.family === f.family) c[d.status]++;
    return c;
  }, [report.documents, f.family]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {DocStatus.options.map((s) => (
          <button
            key={s}
            onClick={() => setCoverage({ status: f.status === s ? "all" : s })}
            aria-pressed={f.status === s}
            className={`rounded-xl border bg-surface p-4 text-left transition-colors ${
              f.status === s ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong"
            }`}
          >
            <StatusBadge status={s} />
            <div className="mt-1 text-2xl font-semibold">{counts[s]}</div>
            <div className="text-xs text-muted">{STATUS_HELP[s]}</div>
          </button>
        ))}
      </div>

      <Card
        title={`${rows.length} of ${report.documents.length} documents`}
        subtitle="Every PDF under crawl_dir/raw, plus any run whose source PDF is missing."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              label="Status"
              value={f.status}
              onChange={(status) => setCoverage({ status })}
              options={[{ value: "all", label: "All" }, ...DocStatus.options.map((s) => ({ value: s, label: STATUS_LABEL[s] }))]}
            />
            <Select label="Family" value={f.family} onChange={(family) => setCoverage({ family })}>
              <option value="all">All</option>
              {report.families.map((x) => (
                <option key={x.family} value={x.family}>
                  {x.family} ({x.documents})
                </option>
              ))}
            </Select>
            <Select label="Sort" value={f.sort} onChange={(v) => setCoverage({ sort: v as CoverageFilters["sort"] })}>
              <option value="redundancy">Most redundant</option>
              <option value="name">Name</option>
              <option value="chunks">Most chunks</option>
              <option value="pages">Most pages without chunks</option>
            </Select>
            <div className="w-56">
              <SearchBox value={f.search} onChange={(search) => setCoverage({ search })} placeholder="Search documents" />
            </div>
          </div>
        }
      >
        {rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-xs">
              <thead className="text-left text-muted">
                <tr className="border-b border-line">
                  <th className="w-[26%] px-4 py-2 font-medium">Document</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Selected run</th>
                  <th className="w-40 px-2 py-2 font-medium">Pages with chunks</th>
                  <th className="px-2 py-2 text-right font-medium">Visually verified</th>
                  <th className="px-2 py-2 text-right font-medium">Chunks</th>
                  <th className="w-36 px-4 py-2 font-medium">Redundant</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <CoverageRow key={d.key} d={d} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No documents match these filters.</Empty>
        )}
      </Card>
    </div>
  );
}

const STATUS_HELP: Record<DocStatus, string> = {
  reviewed: "Promoted to reviewed/; used in production",
  processed: "Valid candidate run with chunks; analyzed",
  failed: "Runs exist, but none produced usable chunks",
  not_processed: "Source PDF with no ingestion run yet",
};

function CoverageRow({ d }: { d: DocumentRow }) {
  const openDocument = useStore((s) => s.openDocument);
  const [open, setOpen] = useState(false);
  const canOpen = d.chunkCount > 0;
  return (
    <>
      <tr className="border-b border-line align-top hover:bg-surface-2">
        <td className="max-w-0 px-4 py-2">
          <button onClick={() => setOpen(!open)} className="flex w-full min-w-0 items-start gap-1.5 text-left" aria-expanded={open}>
            <span className="mt-px w-3 text-muted" aria-hidden>
              {open ? "▾" : "▸"}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-medium text-ink" title={d.documentId}>
                {shortDoc(d.documentId)}
              </span>
              <span className="text-muted">{d.family}</span>
            </span>
          </button>
        </td>
        <td className="px-2 py-2">
          <StatusBadge status={d.status} />
          <div className="mt-0.5 text-muted">{d.statusReason}</div>
        </td>
        <td className="px-2 py-2">
          <div className="font-mono text-[11px] text-ink-2">{d.selectedRun ?? "—"}</div>
          <div className="text-muted">
            {d.runCount} run{d.runCount === 1 ? "" : "s"}
          </div>
        </td>
        <td className="px-2 py-2">
          {d.pageCount ? (
            <>
              <div className="mb-1 flex justify-between">
                <span>
                  {d.pagesWithChunks} / {d.pageCount}
                </span>
                {d.missingPages.length > 0 && <span className="text-serious">−{d.missingPages.length}</span>}
              </div>
              <Meter value={ratio(d.pagesWithChunks, d.pageCount)} />
            </>
          ) : (
            <span className="text-muted">—</span>
          )}
        </td>
        <td className="px-2 py-2 text-right">
          {d.pageCount && d.visualPassedPages != null ? pct(d.visualPassedPages, d.pageCount, 0) : "—"}
        </td>
        <td className="px-2 py-2 text-right">{d.chunkCount ? fmt(d.chunkCount) : "—"}</td>
        <td className="px-4 py-2">
          {canOpen ? (
            <button onClick={() => openDocument(d.key)} className="w-full text-left" title="Inspect chunks">
              <div className="mb-1 flex justify-between">
                <span>{fmt(d.redundant)}</span>
                <span className="font-medium">{pct(d.redundant, d.chunkCount, 0)}</span>
              </div>
              <Meter value={ratio(d.redundant, d.chunkCount)} />
            </button>
          ) : (
            <span className="text-muted">Not analyzed</span>
          )}
        </td>
      </tr>
      {open && (
        <tr className="border-b border-line bg-surface-2/60">
          <td colSpan={7} className="px-10 py-3">
            <dl className="grid gap-x-6 gap-y-1.5 text-xs sm:grid-cols-[10rem_1fr]">
              <dt className="text-muted">Document id</dt>
              <dd className="font-mono break-all">{d.documentId}</dd>
              <dt className="text-muted">Source PDF</dt>
              <dd className="font-mono break-all">
                {d.sourcePath ?? "missing from raw/"}
                {d.sourceBytes > 0 && <span className="text-muted"> · {(d.sourceBytes / 1e6).toFixed(1)} MB</span>}
              </dd>
              <dt className="text-muted">QC status</dt>
              <dd>
                {d.qcStatus ?? "—"}
                {d.structuralWarnings ? ` · ${d.structuralWarnings} structural warning(s)` : ""}
              </dd>
              {d.createdAt && (
                <>
                  <dt className="text-muted">Run created</dt>
                  <dd>{new Date(d.createdAt).toLocaleString()}</dd>
                </>
              )}
              <dt className="text-muted">Pages without chunks</dt>
              <dd>{d.missingPages.length ? d.missingPages.join(", ") : "none"}</dd>
              <dt className="text-muted">Chunks in duplicate groups</dt>
              <dd>
                {fmt(d.involved)} ({fmt(d.redundant)} redundant, {pct(d.redundantChars, d.chars)} of text)
              </dd>
            </dl>
            {canOpen && (
              <button onClick={() => openDocument(d.key)} className="mt-3 text-xs font-medium text-accent hover:underline">
                Open in explorer →
              </button>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
