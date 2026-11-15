import { useEffect, useMemo, useRef, useState } from "react";
import { useDocChunks } from "../../hooks/useChunk";
import { fmt, pages, pct, shortDoc } from "../../lib/format";
import type { Chunk, Cluster } from "../../lib/schema";
import { pairKey, useStore } from "../../store/useStore";
import { Card, Empty, NumbersFlag, Segmented, StatusBadge, TypeBadge, VerdictBadge } from "../ui";

type Show = "all" | "dups";

export default function DocumentView() {
  const docKey = useStore((s) => s.docKey);
  const documents = useStore((s) => s.report!.documents);
  const openDocument = useStore((s) => s.openDocument);
  const doc = useStore((s) => (docKey ? s.docs[docKey] : undefined));
  const [show, setShow] = useState<Show>("all");

  const options = useMemo(
    () =>
      documents
        .filter((d) => d.chunkCount > 0)
        .sort((a, b) => a.family.localeCompare(b.family) || a.documentId.localeCompare(b.documentId)),
    [documents],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2">
        <label className="flex min-w-0 flex-1 items-center gap-2 text-xs text-ink-2">
          Document
          <select
            value={docKey ?? ""}
            onChange={(e) => openDocument(e.target.value)}
            className="min-w-0 flex-1 rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink"
          >
            {options.map((d) => (
              <option key={d.key} value={d.key}>
                {d.family} / {shortDoc(d.documentId)} ({d.redundant}/{d.chunkCount} redundant)
              </option>
            ))}
          </select>
        </label>
        <Segmented
          label="Chunks to show"
          value={show}
          onChange={setShow}
          options={[
            { value: "all", label: "All chunks" },
            { value: "dups", label: "In a duplicate group" },
          ]}
        />
      </div>
      {doc ? (
        <>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 px-1 text-xs text-ink-2">
            <StatusBadge status={doc.status} />
            <span>
              {fmt(doc.chunkCount)} chunks · {fmt(doc.involved)} in groups · {fmt(doc.redundant)} redundant (
              {pct(doc.redundant, doc.chunkCount)})
            </span>
            {doc.pageCount != null && (
              <span>
                {doc.pagesWithChunks}/{doc.pageCount} pages with chunks
                {doc.missingPages.length > 0 && ` · none on ${doc.missingPages.slice(0, 8).join(", ")}${doc.missingPages.length > 8 ? "…" : ""}`}
              </span>
            )}
            <span className="font-mono text-muted">{doc.selectedRun}</span>
          </div>
          <DocChunks key={doc.key} docKey={doc.key} show={show} />
        </>
      ) : (
        <Empty>Pick a document.</Empty>
      )}
    </div>
  );
}

function DocChunks({ docKey, show }: { docKey: string; show: Show }) {
  const entry = useDocChunks(docKey);
  const focusUid = useStore((s) => s.focusUid);
  const focusChunk = useStore((s) => s.focusChunk);
  const clusters = useStore((s) => s.clusters);

  const chunks = entry?.state === "ready" ? entry.data.chunks : [];
  const visible = show === "dups" ? chunks.filter((c) => c.clusterId) : chunks;
  const focused = chunks.find((c) => c.uid === focusUid) ?? null;

  // Scroll a chunk opened from elsewhere into view.
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!focusUid) return;
    listRef.current?.querySelector(`[data-uid="${CSS.escape(focusUid)}"]`)?.scrollIntoView({ block: "center" });
  }, [focusUid, entry?.state]);

  if (!entry || entry.state === "loading") return <Empty>Loading chunks…</Empty>;
  if (entry.state === "error") return <Empty>Could not load chunks: {entry.error}</Empty>;

  return (
    <div className="grid gap-3 lg:grid-cols-[1fr_minmax(340px,460px)]">
      <div ref={listRef} className="space-y-2">
        {visible.length ? (
          visible.map((c) => (
            <ChunkCard
              key={c.uid}
              chunk={c}
              cluster={c.clusterId ? clusters[c.clusterId] : undefined}
              focused={c.uid === focusUid}
              onFocus={() => focusChunk(c.uid === focusUid ? null : c.uid)}
            />
          ))
        ) : (
          <Empty>No chunk in this document belongs to a duplicate group.</Empty>
        )}
      </div>
      <div className="lg:sticky lg:top-[68px] lg:self-start">
        {focused ? (
          <Matches chunk={focused} cluster={focused.clusterId ? clusters[focused.clusterId] : undefined} />
        ) : (
          <Card>
            <Empty>Select a chunk to see where else its text appears.</Empty>
          </Card>
        )}
      </div>
    </div>
  );
}

function ChunkCard({
  chunk: c,
  cluster,
  focused,
  onFocus,
}: {
  chunk: Chunk;
  cluster?: Cluster;
  focused: boolean;
  onFocus: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const long = c.text.length > 600;
  const role = !cluster ? null : c.canonical ? "Canonical" : c.redundant ? "Redundant copy" : "Look-alike";
  return (
    <article
      data-uid={c.uid}
      className={`rounded-xl border bg-surface ${
        focused ? "border-accent ring-1 ring-accent" : cluster ? "border-line-strong" : "border-line"
      }`}
    >
      <button onClick={onFocus} className="flex w-full flex-wrap items-center gap-2 px-4 pt-3 text-left text-xs">
        <span className="font-semibold">#{c.order + 1}</span>
        <span className="text-muted">
          {pages(c.pages)} · {c.contentType}
        </span>
        {c.section && <span className="max-w-xs truncate text-ink-2">§ {c.section}</span>}
        <span className="ml-auto flex items-center gap-1">
          {cluster && (
            <>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  c.redundant ? "bg-near/15 text-ink" : c.canonical ? "bg-surface-2 text-ink-2" : "bg-warning/20 text-ink"
                }`}
              >
                {role} · {cluster.id} ({cluster.size})
              </span>
              {cluster.types.map((t) => (
                <TypeBadge key={t} type={t} />
              ))}
            </>
          )}
        </span>
      </button>
      <div className="px-4 pt-2 pb-3">
        <div className={`chunk-text text-ink-2 ${!expanded && long ? "line-clamp-6" : ""}`}>{c.text}</div>
      </div>
      {long && (
        <button onClick={() => setExpanded(!expanded)} className="-mt-1 px-4 pb-3 text-xs font-medium text-accent hover:underline">
          {expanded ? "Show less" : `Show all ${fmt(c.text.length)} characters`}
        </button>
      )}
    </article>
  );
}

function Matches({ chunk, cluster }: { chunk: Chunk; cluster?: Cluster }) {
  const docs = useStore((s) => s.docs);
  const openPair = useStore((s) => s.openPair);
  const openDocument = useStore((s) => s.openDocument);
  const selectCluster = useStore((s) => s.selectCluster);
  const setView = useStore((s) => s.setView);
  const verdicts = useStore((s) => s.verdicts);

  if (!cluster)
    return (
      <Card title={`Chunk #${chunk.order + 1}`}>
        <Empty>This chunk is unique: no exact, near or containment match anywhere in the corpus.</Empty>
      </Card>
    );

  const others = cluster.members.filter((m) => m.uid !== chunk.uid);
  const direct = new Map(
    cluster.edges
      .filter((e) => e.a === chunk.uid || e.b === chunk.uid)
      .map((e) => [e.a === chunk.uid ? e.b : e.a, e]),
  );
  return (
    <Card
      title={`Chunk #${chunk.order + 1} appears ${others.length} more time${others.length === 1 ? "" : "s"}`}
      subtitle={
        <span className="flex flex-wrap items-center gap-1">
          Group {cluster.id}
          {cluster.numbersDiffer && <NumbersFlag compact />}
        </span>
      }
      actions={
        <button
          onClick={() => {
            selectCluster(cluster.id);
            setView("clusters");
          }}
          className="text-xs font-medium text-accent hover:underline"
        >
          Open group →
        </button>
      }
    >
      <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
        {others.map((m) => {
          const e = direct.get(m.uid);
          return (
            <li key={m.uid} className="space-y-1 px-4 py-2.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={() => openDocument(m.docKey, m.uid)}
                  className="min-w-0 truncate text-left font-medium text-accent hover:underline"
                  title={docs[m.docKey]?.documentId}
                >
                  {shortDoc(docs[m.docKey]?.documentId ?? m.docKey)} #{m.order + 1}
                </button>
                <span className="shrink-0 text-muted">{pages(m.pages)}</span>
              </div>
              <div className="line-clamp-2 text-ink-2">{m.preview}</div>
              <div className="flex items-center gap-2">
                {e ? <TypeBadge type={e.type} /> : <span className="text-[11px] text-muted">Linked through the group</span>}
                {e && <VerdictBadge verdict={verdicts[pairKey(e)]} />}
                <button
                  onClick={() => openPair({ a: chunk.uid, b: m.uid })}
                  className="ml-auto rounded-md border border-line px-2 py-0.5 font-medium hover:bg-surface-2"
                >
                  Compare
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
