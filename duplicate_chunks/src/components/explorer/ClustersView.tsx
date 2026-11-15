import { useEffect, useMemo, useState } from "react";
import { useFilteredClusters } from "../../hooks/useQueue";
import { chars, fmt, pages, score, shortDoc } from "../../lib/format";
import type { Cluster, Member } from "../../lib/schema";
import { pairKey, useStore } from "../../store/useStore";
import { Card, Empty, NumbersFlag, TypeBadge, VerdictBadge } from "../ui";

const PAGE = 80;

export default function ClustersView() {
  const { clusters } = useFilteredClusters();
  const clusterId = useStore((s) => s.clusterId);
  const selectCluster = useStore((s) => s.selectCluster);
  const verdicts = useStore((s) => s.verdicts);
  const [limit, setLimit] = useState(PAGE);
  useEffect(() => setLimit(PAGE), [clusters]);

  // Keep a selection that is visible under the current filters.
  useEffect(() => {
    if (clusters.length && !clusters.some((c) => c.id === clusterId)) selectCluster(clusters[0].id);
  }, [clusters, clusterId, selectCluster]);

  const selected = clusters.find((c) => c.id === clusterId) ?? null;

  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(320px,400px)_1fr]">
      <Card className="lg:sticky lg:top-[68px] lg:max-h-[calc(100vh-200px)] lg:overflow-y-auto">
        {clusters.length ? (
          <ul className="divide-y divide-line">
            {clusters.slice(0, limit).map((c) => {
              const done = c.edges.filter((e) => verdicts[pairKey(e)]).length;
              return (
                <li key={c.id}>
                  <button
                    onClick={() => selectCluster(c.id)}
                    aria-current={c.id === clusterId}
                    className={`block w-full px-3 py-2.5 text-left ${
                      c.id === clusterId ? "bg-accent-soft" : "hover:bg-surface-2"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-semibold">
                        {c.size} chunks <span className="font-normal text-muted">· {c.id}</span>
                      </span>
                      <span className="text-muted">
                        {done}/{c.edges.length} reviewed
                      </span>
                    </div>
                    <div className="mt-1 line-clamp-2 text-xs text-ink-2">{c.members[0].preview}</div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                      {c.types.map((t) => (
                        <TypeBadge key={t} type={t} />
                      ))}
                      <span className="text-[11px] text-muted">
                        {c.scope === "cross-doc" ? `${c.docKeys.length} documents` : "one document"}
                      </span>
                      {c.numbersDiffer && <NumbersFlag compact />}
                    </div>
                  </button>
                </li>
              );
            })}
            {clusters.length > limit && (
              <li className="p-3 text-center">
                <button onClick={() => setLimit(limit + PAGE)} className="text-xs font-medium text-accent hover:underline">
                  Show {Math.min(PAGE, clusters.length - limit)} more of {clusters.length - limit}
                </button>
              </li>
            )}
          </ul>
        ) : (
          <Empty>No duplicate groups match these filters.</Empty>
        )}
      </Card>
      {selected ? <ClusterDetail key={selected.id} cluster={selected} /> : null}
    </div>
  );
}

function ClusterDetail({ cluster: c }: { cluster: Cluster }) {
  const docs = useStore((s) => s.docs);
  const openPair = useStore((s) => s.openPair);
  const openDocument = useStore((s) => s.openDocument);
  const verdicts = useStore((s) => s.verdicts);
  // Start on the pair most worth checking: one whose figures differ, else the first detected pair.
  const first = c.edges.find((e) => e.numbersDiffer) ?? c.edges[0];
  const [a, setA] = useState(first?.a ?? c.members[0].uid);
  const [b, setB] = useState(first?.b ?? c.members[1]?.uid ?? c.members[0].uid);
  const memberByUid = useMemo(() => new Map(c.members.map((m) => [m.uid, m])), [c]);
  const label = (m: Member | undefined) => (m ? `${shortDoc(docs[m.docKey]?.documentId ?? "")} #${m.order + 1}` : "?");

  return (
    <div className="min-w-0 space-y-3">
      <Card
        title={
          <span className="flex flex-wrap items-center gap-2">
            Group {c.id}
            {c.types.map((t) => (
              <TypeBadge key={t} type={t} />
            ))}
            {c.numbersDiffer && <NumbersFlag />}
          </span>
        }
        subtitle={`${c.size} chunks in ${c.docKeys.length} document${c.docKeys.length > 1 ? "s" : ""} (${c.families.join(", ")}) · ${c.redundant} redundant (${chars(c.redundantChars)})${c.size - 1 > c.redundant ? ` · ${c.size - 1 - c.redundant} look-alike${c.size - 2 > c.redundant ? "s" : ""} with different figures` : ""}`}
        actions={
          <button
            onClick={() => openPair({ a, b })}
            disabled={a === b}
            className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
          >
            Compare A ↔ B
          </button>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-xs">
            <thead className="text-left text-muted">
              <tr className="border-b border-line">
                <th className="w-8 px-3 py-2 text-center font-medium">A</th>
                <th className="w-8 px-1 py-2 text-center font-medium">B</th>
                <th className="px-2 py-2 font-medium">Chunk</th>
                <th className="px-2 py-2 font-medium">Text</th>
                <th className="px-3 py-2 text-right font-medium">Size</th>
              </tr>
            </thead>
            <tbody>
              {c.members.map((m, i) => (
                <tr key={m.uid} className="border-b border-line align-top last:border-0">
                  <td className="px-3 py-2 text-center">
                    <input type="radio" name={`a-${c.id}`} checked={a === m.uid} onChange={() => setA(m.uid)} aria-label={`Use ${label(m)} as A`} />
                  </td>
                  <td className="px-1 py-2 text-center">
                    <input type="radio" name={`b-${c.id}`} checked={b === m.uid} onChange={() => setB(m.uid)} aria-label={`Use ${label(m)} as B`} />
                  </td>
                  <td className="w-56 px-2 py-2">
                    <div className="font-medium text-ink">
                      {i === 0 ? "Canonical" : m.redundant ? "Redundant copy" : "Look-alike"} · #{m.order + 1}
                    </div>
                    <button
                      onClick={() => openDocument(m.docKey, m.uid)}
                      className="block max-w-56 truncate text-left text-accent hover:underline"
                      title={docs[m.docKey]?.documentId}
                    >
                      {shortDoc(docs[m.docKey]?.documentId ?? m.docKey)}
                    </button>
                    <div className="text-muted">
                      {pages(m.pages)}
                      {m.section ? ` · ${m.section.slice(0, 40)}` : ""}
                    </div>
                  </td>
                  <td className="px-2 py-2 text-ink-2">
                    <div className="line-clamp-3">{m.preview}</div>
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-muted">{fmt(m.chars)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={`Detected pairs (${c.edges.length})`} subtitle="Each pair the analyzer matched. Open one to verify it side by side.">
        <ul className="divide-y divide-line">
          {c.edges.map((e) => (
            <li key={`${e.a}|${e.b}`}>
              <button
                onClick={() => openPair({ a: e.a, b: e.b })}
                className="grid w-full items-center gap-2 px-4 py-2 text-left text-xs hover:bg-surface-2 md:grid-cols-[7rem_1fr_8rem_7rem]"
              >
                <span>
                  <TypeBadge type={e.type} />
                </span>
                <span className="min-w-0 truncate text-ink-2">
                  {label(memberByUid.get(e.a))} ↔ {label(memberByUid.get(e.b))}
                </span>
                <span className="text-muted">
                  J {score(e.jaccard)} · C {score(e.containment)}
                  {e.numbersDiffer && <span className="ml-1 text-ink">⚠</span>}
                </span>
                <VerdictBadge verdict={verdicts[pairKey(e)]} />
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
