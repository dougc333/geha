import { diffWordsWithSpace } from "diff";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { type ChunkState, useChunk } from "../../hooks/useChunk";
import { useFilteredClusters } from "../../hooks/useQueue";
import { fmt, pages, score, shortDoc } from "../../lib/format";
import type { Chunk, Edge, Verdict } from "../../lib/schema";
import { numberDiff, similarity } from "../../lib/text";
import { docKeyOf, type Pair, pairKey, useStore } from "../../store/useStore";
import { Card, Empty, Segmented, TypeBadge, VERDICT_STYLE, VerdictBadge } from "../ui";

type Mode = "diff" | "plain";

export default function CompareView() {
  const pair = useStore((s) => s.pair);
  const openPair = useStore((s) => s.openPair);
  const { queue } = useFilteredClusters();

  // Default to the first pair in the queue so the view is never blank.
  useEffect(() => {
    if (!pair && queue.length) openPair({ a: queue[0].a, b: queue[0].b });
  }, [pair, queue, openPair]);

  if (!pair) return <Empty>No pairs match the filters. Pick a group in the Duplicate groups view.</Empty>;
  return <ComparePair pair={pair} queue={queue} />;
}

function ComparePair({ pair, queue }: { pair: Pair; queue: Edge[] }) {
  const [mode, setMode] = useState<Mode>("diff");
  const [autoAdvance, setAutoAdvance] = useState(true);
  const openPair = useStore((s) => s.openPair);
  const setVerdict = useStore((s) => s.setVerdict);
  const verdicts = useStore((s) => s.verdicts);
  const clusters = useStore((s) => s.clusters);
  const a = useChunk(pair.a);
  const b = useChunk(pair.b);

  const key = pairKey(pair);
  const index = queue.findIndex((e) => pairKey(e) === key);
  const edge: Edge | undefined =
    index >= 0
      ? queue[index]
      : Object.values(clusters)
          .flatMap((c) => c.edges)
          .find((e) => pairKey(e) === key);
  const verdict = verdicts[key];

  const go = useCallback(
    (i: number) => {
      const e = queue[(i + queue.length) % queue.length];
      if (e) openPair({ a: e.a, b: e.b });
    },
    [queue, openPair],
  );
  const nextUnreviewed = useCallback(() => {
    for (let step = 1; step <= queue.length; step++) {
      const e = queue[(Math.max(index, -1) + step) % queue.length];
      if (!verdicts[pairKey(e)] && pairKey(e) !== key) return openPair({ a: e.a, b: e.b });
    }
  }, [queue, index, verdicts, key, openPair]);
  const decide = useCallback(
    (v: Verdict) => {
      setVerdict(pair, verdicts[key] === v ? null : v);
      if (autoAdvance && verdicts[key] !== v) setTimeout(nextUnreviewed, 120);
    },
    [setVerdict, pair, verdicts, key, autoAdvance, nextUnreviewed],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, select, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "1") decide("duplicate");
      else if (e.key === "2") decide("distinct");
      else if (e.key === "3") decide("unsure");
      else if (e.key === "ArrowRight" || e.key === "j") go(index + 1);
      else if (e.key === "ArrowLeft" || e.key === "k") go(index - 1);
      else if (e.key === "n") nextUnreviewed();
      else if (e.key === "d") setMode((m) => (m === "diff" ? "plain" : "diff"));
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, go, index, nextUnreviewed]);

  const ready = a?.state === "ready" && b?.state === "ready";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-xs">
        <button onClick={() => go(index - 1)} disabled={!queue.length} className="rounded-md border border-line px-2 py-1 hover:bg-surface-2" title="Previous pair (←)">
          ← Prev
        </button>
        <button onClick={() => go(index + 1)} disabled={!queue.length} className="rounded-md border border-line px-2 py-1 hover:bg-surface-2" title="Next pair (→)">
          Next →
        </button>
        <button onClick={nextUnreviewed} className="rounded-md border border-line px-2 py-1 hover:bg-surface-2" title="Next unreviewed pair (n)">
          Next unreviewed
        </button>
        <span className="text-muted">
          {index >= 0 ? `Pair ${fmt(index + 1)} of ${fmt(queue.length)} in the filtered queue` : "Pair is outside the current filters"}
        </span>
        <span className="ml-auto flex items-center gap-3">
          <button onClick={() => openPair({ a: pair.b, b: pair.a })} className="rounded-md border border-line px-2 py-1 hover:bg-surface-2">
            Swap A/B
          </button>
          <Segmented
            label="Text display"
            value={mode}
            onChange={setMode}
            options={[
              { value: "diff", label: "Show differences" },
              { value: "plain", label: "Plain" },
            ]}
          />
        </span>
      </div>

      {ready ? (
        <Verification a={a.chunk} b={b.chunk} edge={edge} verdict={verdict} onDecide={decide} autoAdvance={autoAdvance} setAutoAdvance={setAutoAdvance} />
      ) : null}

      {ready ? (
        <SideBySide a={a.chunk} b={b.chunk} uidA={pair.a} uidB={pair.b} mode={mode} />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          <Pending state={a} />
          <Pending state={b} />
        </div>
      )}
      <p className="text-center text-[11px] text-muted">
        Keys: 1 duplicate · 2 not duplicate · 3 unsure · ←/→ previous/next · n next unreviewed · d toggle differences
      </p>
    </div>
  );
}

function Pending({ state }: { state: ChunkState | null }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-6 text-sm text-muted">
      {state?.state === "error" ? `Could not load chunk: ${state.error}` : "Loading chunk…"}
    </div>
  );
}

function Verification({
  a,
  b,
  edge,
  verdict,
  onDecide,
  autoAdvance,
  setAutoAdvance,
}: {
  a: Chunk;
  b: Chunk;
  edge?: Edge;
  verdict?: Verdict;
  onDecide: (v: Verdict) => void;
  autoAdvance: boolean;
  setAutoAdvance: (v: boolean) => void;
}) {
  const shingle = useStore((s) => s.report!.params.shingleSize);
  const sim = useMemo(() => similarity(a.text, b.text, shingle), [a.text, b.text, shingle]);
  const nums = useMemo(() => numberDiff(a.text, b.text), [a.text, b.text]);
  const sameDoc = docKeyOf(a.uid) === docKeyOf(b.uid);
  const hint =
    nums.onlyA.length || nums.onlyB.length
      ? "Wording overlaps but the figures differ. Similar text about a different amount, year or tier is usually a different fact."
      : sim.exact
        ? "Identical after normalization. Safe to keep one copy, with both sources recorded."
        : sim.containment >= 0.9 && sim.jaccard < 0.8
          ? "The smaller chunk is repeated inside the larger one. Check the larger chunk adds nothing the reader needs separately."
          : "Check whether one correct answer drawn from either chunk would be the same.";

  return (
    <Card>
      <div className="grid gap-4 p-4 lg:grid-cols-[1fr_auto]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
            {edge ? <TypeBadge type={edge.type} /> : <span className="text-muted">Not a detected pair</span>}
            <Metric label="Jaccard" value={score(sim.jaccard)} />
            <Metric label="Containment" value={score(sim.containment)} />
            <Metric label="Shared phrases" value={fmt(sim.shared)} />
            <Metric label="Length" value={`${fmt(a.text.length)} / ${fmt(b.text.length)}`} />
            <Metric label="Scope" value={sameDoc ? "Same document" : "Different documents"} />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-ink-2">Figures only in A:</span>
            <Chips values={nums.onlyA} />
            <span className="ml-3 text-ink-2">Only in B:</span>
            <Chips values={nums.onlyB} />
          </div>
          <p className="text-xs text-ink-2">{hint}</p>
        </div>
        <div className="flex flex-col items-start gap-2 lg:items-end">
          <div className="flex items-center gap-2 text-xs text-ink-2">
            Verdict: <VerdictBadge verdict={verdict} />
          </div>
          <div className="flex gap-1.5">
            {(["duplicate", "distinct", "unsure"] as const).map((v, i) => (
              <button
                key={v}
                onClick={() => onDecide(v)}
                aria-pressed={verdict === v}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                  verdict === v ? "border-ink bg-ink text-bg" : "border-line-strong bg-surface hover:bg-surface-2"
                }`}
              >
                <span className={verdict === v ? "" : VERDICT_STYLE[v].cls}>{VERDICT_STYLE[v].icon}</span> {VERDICT_STYLE[v].label}
                <span className="ml-1.5 text-[10px] opacity-60">{i + 1}</span>
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-[11px] text-muted">
            <input type="checkbox" checked={autoAdvance} onChange={(e) => setAutoAdvance(e.target.checked)} />
            Go to next unreviewed pair after a verdict
          </label>
        </div>
      </div>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span>
      <span className="text-muted">{label} </span>
      <span className="font-semibold text-ink">{value}</span>
    </span>
  );
}

function Chips({ values }: { values: string[] }) {
  if (!values.length) return <span className="text-muted">none</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {values.slice(0, 12).map((v) => (
        <span key={v} className="num-flag px-1.5 py-0.5 font-mono text-[11px]">
          {v}
        </span>
      ))}
      {values.length > 12 && <span className="text-muted">+{values.length - 12}</span>}
    </span>
  );
}

function SideBySide({ a, b, uidA, uidB, mode }: { a: Chunk; b: Chunk; uidA: string; uidB: string; mode: Mode }) {
  const parts = useMemo(() => {
    if (mode !== "diff") return null;
    return diffWordsWithSpace(a.text, b.text, { timeout: 1500 }) ?? null;
  }, [a.text, b.text, mode]);
  const nums = useMemo(() => numberDiff(a.text, b.text), [a.text, b.text]);

  const render = (side: "a" | "b", text: string) => {
    if (parts) {
      return parts.map((p, i) => {
        if (p.added) return side === "b" ? <ins key={i} className="diff-ins no-underline">{p.value}</ins> : null;
        if (p.removed) return side === "a" ? <del key={i} className="diff-del">{p.value}</del> : null;
        return <span key={i}>{p.value}</span>;
      });
    }
    return highlightNumbers(text, new Set(side === "a" ? nums.onlyA : nums.onlyB));
  };

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <ChunkPane label="A" uid={uidA} chunk={a} legend={parts ? "Struck through: only in A" : null}>
        {render("a", a.text)}
      </ChunkPane>
      <ChunkPane label="B" uid={uidB} chunk={b} legend={parts ? "Highlighted: only in B" : null}>
        {render("b", b.text)}
      </ChunkPane>
    </div>
  );
}

function highlightNumbers(text: string, flagged: Set<string>): ReactNode {
  if (!flagged.size) return text;
  return text.split(/(\$?\d[\d,]*(?:\.\d+)?(?:%|[A-Z](?![A-Za-z]))?)/g).map((part, i) =>
    i % 2 === 1 && flagged.has(part.replace(/,/g, "")) ? (
      <mark key={i} className="num-flag text-ink">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

function ChunkPane({
  label,
  uid,
  chunk,
  legend,
  children,
}: {
  label: string;
  uid: string;
  chunk: Chunk;
  legend: string | null;
  children: ReactNode;
}) {
  const doc = useStore((s) => s.docs[docKeyOf(uid)]);
  const openDocument = useStore((s) => s.openDocument);
  return (
    <section className="flex min-w-0 flex-col rounded-xl border border-line bg-surface">
      <header className="space-y-1 border-b border-line px-4 py-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="grid size-5 place-items-center rounded bg-ink text-[11px] font-bold text-bg">{label}</span>
          <button
            onClick={() => openDocument(docKeyOf(uid), uid)}
            className="min-w-0 truncate font-semibold text-accent hover:underline"
            title={doc?.documentId}
          >
            {shortDoc(doc?.documentId ?? uid)}
          </button>
          {chunk.canonical && <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-ink-2">Canonical</span>}
        </div>
        <div className="text-muted">
          {doc?.family} · chunk #{chunk.order + 1} · {pages(chunk.pages)} · {chunk.contentType} · {fmt(chunk.tokenCount)} words
        </div>
        {chunk.section && <div className="truncate text-ink-2">§ {chunk.section}</div>}
        <div className="truncate font-mono text-[10px] text-muted">{chunk.chunkId}</div>
      </header>
      <div className="chunk-text max-h-[60vh] overflow-y-auto px-4 py-3 text-ink">{children}</div>
      {legend && <footer className="border-t border-line px-4 py-1.5 text-[11px] text-muted">{legend}</footer>}
    </section>
  );
}
